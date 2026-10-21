#!/usr/bin/env python3
"""Orquestador NFV (MANO ligero) de la cadena firewall -> balanceador (Entrega 2).

Vigila la instancia ACTIVA del firewall virtual cada `nfv.sondeo_s` segundos. Tras `nfv.fallos` sondeos
fallidos activa la instancia de RESPALDO (le asigna las IP virtuales de puerta de enlace y lo anuncia con
ARP gratuito) y re-instancia el contenedor caido a traves de la API de GNS3, configurandolo como el nuevo
respaldo. Cada evento queda en evidence/nfv_eventos.log y el estado en automation/nfv_estado.json.

Uso (en la GNS3 VM):
  python3 orquestador_nfv.py              # demonio (normalmente via scripts/orquestador.sh)
  python3 orquestador_nfv.py diagrama     # escribe el diagrama de estado de las VNFs en evidence/
"""
import json
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime

from common import ROOT, build_contexts, connect, jinja_env, load_topology
from deploy import push_text

topo = load_topology()
NFV, SRV = topo["nfv"], topo["servicios"]
FWS = [n for n, v in SRV.items() if v["role"] == "fw"]
EVENTOS = ROOT / "evidence" / "nfv_eventos.log"
ESTADO = ROOT / "automation" / "nfv_estado.json"
IDS = ROOT / "automation" / "gns3_ids.json"          # lo escribe scripts/levantar_lab.ps1
COMPUTE = "http://127.0.0.1/v2/compute"              # API de GNS3 dentro de la VM


def log(msg):
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S.%f}"[:-3] + f" {msg}"
    print(linea, flush=True)
    with open(EVENTOS, "a") as f:
        f.write(linea + "\n")


def vivo(nodo, timeout=0.25):
    """Sondeo de salud: el plano de gestion de la VNF acepta conexiones (cae con el contenedor)."""
    try:
        socket.create_connection((SRV[nodo]["mgmt"], 22), timeout=timeout).close()
        return True
    except OSError:
        return False


def comandos_vip(activar):
    accion = "replace" if activar else "del"
    cmds = [f"ip addr {accion} {NFV['vip_outside']}/24 dev eth0", f"ip addr {accion} {NFV['vip_inside']}/24 dev eth1"]
    if activar:
        # nohup: el ARP gratuito debe sobrevivir al cierre inmediato de la sesion SSH
        cmds += [f"nohup arping -U -c 3 -I eth0 {NFV['vip_outside']} >/dev/null 2>&1 &",
                 f"nohup arping -U -c 3 -I eth1 {NFV['vip_inside']} >/dev/null 2>&1 &"]
    # los comandos en segundo plano ya terminan en "&": no llevan ";" detras (seria error de sintaxis)
    return " ".join(c if c.endswith("&") else c + ";" for c in cmds) + " true"


def configurar(nodo, activo):
    """Instancia (o re-instancia) la configuracion completa de un firewall con el rol indicado."""
    ctx = {**build_contexts(topo)[nodo], "activo": activo}
    env = jinja_env()
    conn = connect(topo, nodo)
    try:
        push_text(conn, env.get_template("nfv/fw.nft.j2").render(**ctx), "/etc/gsm/fw.nft")
        push_text(conn, env.get_template("nfv/fw.linux.j2").render(**ctx), "/tmp/setup.sh")
        conn.send_command("sh /tmp/setup.sh", read_timeout=30)
    finally:
        conn.disconnect()


def tiene_vip(nodo):
    conn = connect(topo, nodo)
    try:
        return NFV["vip_outside"] in conn.send_command("ip -br addr show eth0")
    finally:
        conn.disconnect()


class Orquestador:
    def __init__(self):
        activos = [f for f in FWS if vivo(f, 1) and tiene_vip(f)]
        self.activo = activos[0] if activos else next(f for f in FWS if SRV[f].get("activo"))
        self.respaldo = next(f for f in FWS if f != self.activo)
        self.estado = {f: "ACTIVO" if f == self.activo else "RESPALDO" for f in FWS}
        self.sesion = None            # sesion SSH abierta de antemano con el respaldo (conmutacion rapida)
        if vivo(self.respaldo, 1):
            configurar(self.respaldo, activo=False)     # el respaldo siempre listo y sin VIPs
        else:
            self.estado[self.respaldo] = "CAIDO"
        self.guardar()

    def guardar(self):
        ESTADO.write_text(json.dumps({"activo": self.activo, "respaldo": self.respaldo, "instancias": self.estado,
                                      "actualizado": f"{datetime.now():%H:%M:%S}"}, indent=2))

    def preparar_sesion(self):
        try:
            if self.sesion is None or not self.sesion.is_alive():
                self.sesion = connect(topo, self.respaldo)
        except Exception:
            self.sesion = None

    def conmutar(self, t_falla):
        caido, nuevo = self.activo, self.respaldo
        self.estado[caido] = "CAIDO"
        self.preparar_sesion()
        self.sesion.send_command(comandos_vip(True), read_timeout=10)
        self.activo, self.respaldo = nuevo, caido
        self.estado[nuevo] = "ACTIVO"
        self.sesion.disconnect()
        self.sesion = None
        log(f"CONMUTACION: {nuevo} es ACTIVO (VIP {NFV['vip_outside']} / {NFV['vip_inside']}) "
            f"{time.time() - t_falla:.2f} s despues del primer sondeo fallido de {caido}")
        self.guardar()
        threading.Thread(target=self.reinstanciar, args=(caido,), daemon=True).start()

    def reinstanciar(self, nodo):
        self.estado[nodo] = "REINSTANCIANDO"
        self.guardar()
        t0 = time.time()
        try:
            ids = json.loads(IDS.read_text())
            base = f"{COMPUTE}/projects/{ids['project_id']}/docker/nodes/{ids['nodes'][nodo]}"
            # Docker reinicia el contenedor muerto pero sin sus interfaces de GNS3: se mata y se hace un
            # ciclo stop/start completo por la API, que recrea el contenedor con sus enlaces
            subprocess.run(f"docker kill $(docker ps -q -f name=GNS3.{nodo}.)", shell=True, capture_output=True)
            for accion in ("stop", "start"):
                urllib.request.urlopen(urllib.request.Request(f"{base}/{accion}", data=b"{}", method="POST"),
                                       timeout=60).read()
            while not vivo(nodo, 1):
                time.sleep(0.5)
            configurar(nodo, activo=False)
            self.estado[nodo] = "RESPALDO"
            log(f"RE-INSTANCIA: {nodo} recreado por la API de GNS3 y configurado como RESPALDO "
                f"en {time.time() - t0:.1f} s")
        except Exception as e:
            self.estado[nodo] = "CAIDO"
            log(f"ERROR re-instanciando {nodo}: {e}")
        self.guardar()

    def ejecutar(self):
        log(f"orquestador iniciado: activo={self.activo}, respaldo={self.respaldo}, "
            f"sondeo {NFV['sondeo_s']} s x {NFV['fallos']} fallos")
        fallos, t_falla = 0, 0.0
        ultimo_ok = 0.0
        while True:
            if vivo(self.activo):
                fallos = 0
                if time.time() - ultimo_ok > 30 and self.estado[self.respaldo] == "RESPALDO":
                    self.preparar_sesion()       # mantiene lista la sesion con el respaldo
                    ultimo_ok = time.time()
            else:
                fallos += 1
                if fallos == 1:
                    t_falla = time.time()
                    log(f"sondeo fallido de {self.activo}")
                if fallos >= NFV["fallos"] and self.estado[self.respaldo] == "RESPALDO":
                    try:
                        self.conmutar(t_falla)
                    except Exception as e:
                        log(f"ERROR en la conmutacion: {e}")
                    fallos = 0
            time.sleep(NFV["sondeo_s"])


def diagrama():
    """Diagrama de estado de las VNFs activas (Mermaid, se ve en GitHub/VS Code) + tabla de estado."""
    est = json.loads(ESTADO.read_text()) if ESTADO.exists() else {"instancias": {}}
    inst = {f: est["instancias"].get(f, "?") if vivo(f, 1) else "CAIDO" for f in FWS}
    try:
        csv = urllib.request.urlopen(f"http://{SRV['lb']['mgmt']}:8404/;csv", timeout=3).read().decode()
        backends = {c[1]: c[17] for c in (l.split(",") for l in csv.splitlines()[1:]) if c[1] in ("srv1", "srv2")}
    except Exception:
        backends = {}
    color = {"ACTIVO": "#2e7d32", "RESPALDO": "#1565c0", "UP": "#2e7d32", "CAIDO": "#c62828",
             "REINSTANCIANDO": "#ef6c00"}
    nodos = [("upf", "UPF (core5g)<br/>N6 10.40.0.10", "ACTIVO")]
    nodos += [(f, f"vFW {f}<br/>{inst[f]}", inst[f]) for f in FWS]
    nodos += [("lb", f"vLB HAProxy<br/>VIP {NFV['vip_lb']}", "ACTIVO" if vivo("lb", 1) else "CAIDO")]
    nodos += [(s, f"{s}<br/>{backends.get(s, '?')}", backends.get(s, "?")) for s in ("srv1", "srv2")]
    act = next((f for f in FWS if inst[f] == "ACTIVO"), FWS[0])
    lineas = ["flowchart LR"]
    lineas += [f'  {n}["{t}"]' for n, t, _ in nodos]
    lineas += [f"  upf ==>|N6 VIP {NFV['vip_outside']}| {act}",
               f"  {act} ==>|VIP {NFV['vip_inside']}| lb", "  lb --> srv1", "  lb --> srv2"]
    lineas += [f"  upf -.->|respaldo| {f}" for f in FWS if f != act]
    lineas += [f"  style {n} fill:{color.get(e, '#757575')},color:#fff" for n, _, e in nodos]
    md = [f"# Estado de las VNFs - {datetime.now():%Y-%m-%d %H:%M:%S}", "",
          "Cadena de servicios (SFC): UE -> UPF -> vFW activo -> vLB -> servidores industriales.", "",
          "```mermaid", *lineas, "```", "", "| VNF | Rol / estado | Gestion |", "|---|---|---|"]
    md += [f"| {f} (nftables) | {inst[f]} | {SRV[f]['mgmt']} |" for f in FWS]
    md += [f"| lb (HAProxy) | {'ACTIVO' if vivo('lb', 1) else 'CAIDO'} | {SRV['lb']['mgmt']} |"]
    md += [f"| {s} (servidor) | {backends.get(s, '?')} | {SRV[s]['mgmt']} |" for s in ("srv1", "srv2")]
    out = ROOT / "evidence" / f"nfv_estado_{datetime.now():%Y%m%d_%H%M%S}.md"
    out.write_text("\n".join(md) + "\n")
    # Version HTML: se abre con doble clic y el navegador dibuja el diagrama (mermaid desde CDN)
    filas = "".join("<tr>" + "".join(f"<td>{c.strip()}</td>" for c in l.strip("|").split("|")) + "</tr>"
                    for l in md if l.startswith("| ") and not l.startswith("| VNF"))
    out.with_suffix(".html").write_text(
        f"<!doctype html><meta charset='utf-8'><title>Estado de las VNFs</title>"
        f"<body style='font-family:sans-serif;margin:24px'><h2>{md[0][2:]}</h2><p>{md[2]}</p>"
        f"<pre class='mermaid'>{chr(10).join(lineas)}</pre>"
        f"<table border='1' cellpadding='6' style='border-collapse:collapse'>"
        f"<tr><th>VNF</th><th>Rol / estado</th><th>Gestion</th></tr>{filas}</table>"
        f"<script src='https://cdn.jsdelivr.net/npm/mermaid@10.9.1/dist/mermaid.min.js'></script>"
        f"<script>mermaid.initialize({{startOnLoad: true}});</script></body>\n")
    print("\n".join(md))
    print(f"\nDiagrama guardado en {out} y {out.with_suffix('.html').name}")


if __name__ == "__main__":
    if sys.argv[1:] == ["diagrama"]:
        diagrama()
    else:
        Orquestador().ejecutar()
