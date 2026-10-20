#!/usr/bin/env python3
"""Controlador SDN / IBN ligero (Entrega 1).

API REST (solo libreria estandar) que traduce intenciones de negocio en politicas
SRv6 y servicios VXLAN, y las programa en el tejido con Netmiko. Lazo cerrado:
cada 10 s comprueba que el spine elegido para cada intencion siga vivo y, si no,
recalcula la ruta y la reprograma.

Una intencion fija el camino del trafico VXLAN entre dos leafs:
  leaf origen --SRv6 [End en spine elegido, End.DX4 en leaf destino]--> leaf destino
El spine se elige midiendo RTT (ping IPv6 a los locators), respetando
restricciones de latencia (max_rtt_ms) y de exclusion (avoid).

Uso (en la GNS3 VM):   python3 controller.py        ->  http://192.168.56.102:8181
  GET    /api/topology          estado OSPFv2/OSPFv3/BGP EVPN de cada nodo
  GET    /api/intents           intenciones y ruta elegida
  POST   /api/intents           {"name": "ot", "src": "leaf2", "dst": "leaf4",
                                 "avoid": ["spine1"], "max_rtt_ms": 10}
  DELETE /api/intents/<name>
  POST   /api/reconcile         recalcula todas las intenciones ahora
  POST   /api/services          {"vlan": 30, "vni": 10030, "name": "Video-Analitica"}
Sin autenticacion: solo escucha en la red host-only del laboratorio.
"""
import json
import re
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from common import ROOT, build_contexts, connect, jinja_env, load_topology, node_num
from deploy import push_text

PORT = 8181
TABLE = 100          # tabla de politicas SRv6: zebra no la gestiona
CHECK_EVERY = 5      # segundos entre comprobaciones del lazo cerrado
STATE_FILE = ROOT / "automation" / "controller_state.json"
LOG_FILE = ROOT / "evidence" / "controller.log"
NAME_RE = re.compile(r"^[\w-]{1,40}$")
# ponytail: un lock global serializa todo Netmiko; suficiente para 10 nodos de laboratorio
LOCK = threading.Lock()
# Una operacion completa sobre intenciones (programar src y dst) es atomica frente al monitor
INTENTS_LOCK = threading.RLock()

topo = load_topology()
state = {"intents": {}, "services": []}


def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def save():
    STATE_FILE.write_text(json.dumps(state, indent=2))


def run(node, cmds, timeout=30):
    with LOCK:
        conn = connect(topo, node)
        try:
            return [conn.send_command(c, read_timeout=timeout) for c in cmds]
        finally:
            conn.disconnect()


def sid(node, func):
    """Direccion SRv6 de un nodo: func '1' (loopback IPv6), 'e' (End), 'd4' (End.DX4)."""
    nodes = {**topo["spines"], **topo["leafs"]}
    return f"{topo['srv6_prefix']}:{node_num(nodes[node])}::{func}"


def parse_rtt(ping_out):
    """RTT promedio (ms) de la salida de ping, o None si no hubo respuesta."""
    m = re.search(r"= [\d.]+/([\d.]+)/", ping_out)
    return float(m.group(1)) if m else None


def choose_spine(rtts, avoid, max_rtt):
    """rtts: {spine: rtt_ms o None}. Spine permitido de menor RTT, o None si ninguno cumple."""
    ok = {s: r for s, r in rtts.items()
          if r is not None and s not in avoid and (max_rtt is None or r <= max_rtt)}
    return min(ok, key=ok.get) if ok else None


def measure(src, dst):
    """RTT del camino src->spine->dst para cada spine (suma de ambos tramos)."""
    spines = list(topo["spines"])
    pings = [f"ping -6 -c 3 -i 0.2 -W 1 {sid(s, '1')}" for s in spines]
    a, b = run(src, pings), run(dst, pings)
    rtts = {}
    for s, oa, ob in zip(spines, a, b):
        ra, rb = parse_rtt(oa), parse_rtt(ob)
        rtts[s] = round(ra + rb, 2) if ra is not None and rb is not None else None
    return rtts


def guard_pid(lb):
    return f"/tmp/srv6-guard-{lb}.pid"


def steer_cmds(local, remote, spine):
    """Comandos en `local` para enviar su VXLAN hacia `remote` via `spine` con SRv6.

    Incluye un guardian local (proteccion tipo BFD/TI-LFA): sondea el spine cada
    100 ms y, tras 2 fallos (~0.8 s), retira la politica para que el trafico caiga
    al ECMP de OSPF, que ya reconvergio. Luego el controlador reoptimiza."""
    lb = topo["leafs"][remote]["loopback"]
    uplink = f"eth{int(spine.replace('spine', '')) - 1}"   # convencion: leaf ethN-1 -> spineN
    guard = (f"(f=0; while sleep 0.1; do if ping -6 -c1 -W 0.3 {sid(spine, '1')} >/dev/null 2>&1; "
             f"then f=0; else f=$((f+1)); fi; if [ $f -ge 2 ]; then ip rule del to {lb}/32 table {TABLE}; "
             f"break; fi; done) </dev/null >/dev/null 2>&1 & echo $! > {guard_pid(lb)}")
    return [f"kill $(cat {guard_pid(lb)} 2>/dev/null) 2>/dev/null; "
            f"ip rule del to {lb}/32 table {TABLE} 2>/dev/null; ip rule add to {lb}/32 table {TABLE} pref 100",
            f"ip route replace {lb}/32 table {TABLE} encap seg6 mode encap "
            f"segs {sid(spine, 'e')},{sid(remote, 'd4')} dev {uplink}",
            guard]


def unsteer_cmds(local, remote):
    lb = topo["leafs"][remote]["loopback"]
    return [f"kill $(cat {guard_pid(lb)} 2>/dev/null) 2>/dev/null; "
            f"ip rule del to {lb}/32 table {TABLE} 2>/dev/null; "
            f"ip route del {lb}/32 table {TABLE} 2>/dev/null; true"]


def policy_ok(local, remote):
    """True si la politica de `local` hacia `remote` sigue instalada (el guardian no la retiro)."""
    lb = topo["leafs"][remote]["loopback"]
    return run(local, [f"ip rule | grep -c 'to {lb} lookup {TABLE}'"])[0].strip() not in ("", "0")


def apply_intent(name):
    with INTENTS_LOCK:
        return _apply_intent(name)


def _apply_intent(name):
    it = state["intents"][name]
    rtts = measure(it["src"], it["dst"])
    spine = choose_spine(rtts, it["avoid"], it["max_rtt_ms"])
    if spine is None:            # histeresis: dejar asentar OSPFv3 (dead 3 s) y medir otra vez
        time.sleep(4)
        rtts = measure(it["src"], it["dst"])
        spine = choose_spine(rtts, it["avoid"], it["max_rtt_ms"])
    it.update(rtts=rtts, updated=f"{datetime.now():%H:%M:%S}")
    if spine is None:
        run(it["src"], unsteer_cmds(it["src"], it["dst"]))
        run(it["dst"], unsteer_cmds(it["dst"], it["src"]))
        it.update(spine=None, segments=None, status="SIN-RUTA (fallback OSPF ECMP)")
        log(f"[{name}] ninguna ruta cumple la intencion {rtts}; trafico vuelve a OSPF ECMP")
    else:
        run(it["src"], steer_cmds(it["src"], it["dst"], spine))
        run(it["dst"], steer_cmds(it["dst"], it["src"], spine))
        segs = f"{sid(spine, 'e')},{sid(it['dst'], 'd4')}"
        if spine != it.get("spine"):
            log(f"[{name}] {it['src']}<->{it['dst']} via {spine} (RTT {rtts[spine]} ms) segs [{segs}]")
        it.update(spine=spine, segments=segs, status="ACTIVA")
    save()
    return it


def monitor():
    """Lazo cerrado IBN: si el spine elegido deja de responder, recalcula."""
    while True:
        time.sleep(CHECK_EVERY)
        for name in list(state["intents"]):
            try:
                with INTENTS_LOCK:
                    check_intent(name)
            except Exception as e:
                log(f"[{name}] error en el monitor: {e}")


def check_intent(name):
    it = state["intents"].get(name)
    if it is None:          # eliminada mientras el monitor esperaba el candado
        return
    if it.get("spine"):
        guards = policy_ok(it["src"], it["dst"]) and policy_ok(it["dst"], it["src"])
        # dos sondeos separados: una sola muestra perdida no dispara un cambio de ruta
        probe = f"ping -6 -c 2 -i 0.2 -W 1 {sid(it['spine'], '1')}"
        if guards and parse_rtt(run(it["src"], [probe])[0]) is not None:
            return
        time.sleep(2)
        if guards and parse_rtt(run(it["src"], [probe])[0]) is not None:
            return
        why = "no responde" if guards else "proteccion local retiro la politica"
        log(f"[{name}] {it['spine']} {why}: recalculando")
    apply_intent(name)


def node_status(node):
    out = run(node, ['vtysh -c "show ip ospf neighbor" 2>/dev/null',
                     'vtysh -c "show ipv6 ospf6 neighbor" 2>/dev/null',
                     'vtysh -c "show bgp l2vpn evpn summary json" 2>/dev/null'])
    return {"ospf_full": out[0].count("Full"), "ospf6_full": out[1].count("Full"),
            "evpn_established": len(re.findall(r'"state":\s*"Established"', out[2]))}


def add_service(svc):
    if any(v["id"] == svc["vlan"] or v["vni"] == svc["vni"] for v in topo["vlans"]):
        raise ValueError("la VLAN o el VNI ya existen")
    topo["vlans"].append({"id": svc["vlan"], "vni": svc["vni"], "name": svc["name"]})
    ctxs, tpl = build_contexts(topo), jinja_env().get_template("leaf.linux.j2")
    for leaf in topo["leafs"]:
        with LOCK:
            conn = connect(topo, leaf)
            try:
                push_text(conn, tpl.render(**ctxs[leaf]), "/tmp/setup.sh")
                conn.send_command("sh /tmp/setup.sh", read_timeout=60)
            finally:
                conn.disconnect()
    state["services"].append(svc)
    save()
    log(f"[servicio] VLAN {svc['vlan']} -> VNI {svc['vni']} ({svc['name']}) aprovisionado en {list(topo['leafs'])}")


def validate_intent(d):
    leafs, spines = set(topo["leafs"]), set(topo["spines"])
    if not NAME_RE.match(str(d.get("name", ""))):
        raise ValueError("name: 1-40 caracteres [A-Za-z0-9_-]")
    if d.get("src") not in leafs or d.get("dst") not in leafs or d["src"] == d["dst"]:
        raise ValueError(f"src y dst deben ser leafs distintos de {sorted(leafs)}")
    avoid = d.get("avoid", [])
    if not isinstance(avoid, list) or not set(avoid) <= spines:
        raise ValueError(f"avoid debe ser una lista de {sorted(spines)}")
    mx = d.get("max_rtt_ms")
    if mx is not None and (not isinstance(mx, (int, float)) or mx <= 0):
        raise ValueError("max_rtt_ms debe ser un numero positivo")
    return {"name": d["name"], "src": d["src"], "dst": d["dst"], "avoid": avoid, "max_rtt_ms": mx}


def validate_service(d):
    vlan, vni, name = d.get("vlan"), d.get("vni"), str(d.get("name", ""))
    if not isinstance(vlan, int) or not 2 <= vlan <= 4094:
        raise ValueError("vlan: entero 2-4094")
    if not isinstance(vni, int) or not 1 <= vni <= 16777215:
        raise ValueError("vni: entero 1-16777215")
    if not NAME_RE.match(name):
        raise ValueError("name: 1-40 caracteres [A-Za-z0-9_-]")
    return {"vlan": vlan, "vni": vni, "name": name}


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body):
        data = json.dumps(body, indent=2, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 10_000:
            raise ValueError("cuerpo demasiado grande")
        return json.loads(self.rfile.read(n) or b"{}")

    def handle_any(self, method):
        try:
            p = self.path.rstrip("/")
            if method == "GET" and p == "/api/topology":
                nodes = list(topo["spines"]) + list(topo["leafs"])
                return self.reply(200, {n: node_status(n) for n in nodes})
            if method == "GET" and p == "/api/intents":
                return self.reply(200, state["intents"])
            if method == "POST" and p == "/api/intents":
                it = validate_intent(self.body())
                with INTENTS_LOCK:
                    state["intents"][it["name"]] = it
                    return self.reply(201, apply_intent(it["name"]))
            if method == "DELETE" and p.startswith("/api/intents/"):
                with INTENTS_LOCK:
                    it = state["intents"].pop(p.rsplit("/", 1)[1], None)
                    if not it:
                        return self.reply(404, {"error": "no existe"})
                    run(it["src"], unsteer_cmds(it["src"], it["dst"]))
                    run(it["dst"], unsteer_cmds(it["dst"], it["src"]))
                    save()
                log(f"[{it['name']}] eliminada; trafico vuelve a OSPF ECMP")
                return self.reply(200, {"deleted": it["name"]})
            if method == "POST" and p == "/api/reconcile":
                return self.reply(200, {n: apply_intent(n) for n in list(state["intents"])})
            if method == "POST" and p == "/api/services":
                svc = validate_service(self.body())
                add_service(svc)
                return self.reply(201, svc)
            self.reply(404, {"error": "ruta desconocida"})
        except (ValueError, json.JSONDecodeError) as e:
            self.reply(400, {"error": str(e)})
        except Exception as e:
            log(f"error {method} {self.path}: {e}")
            self.reply(500, {"error": str(e)})

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_DELETE(self):
        self.handle_any("DELETE")


def main():
    if STATE_FILE.exists():
        state.update(json.loads(STATE_FILE.read_text()))
        for svc in state["services"]:
            topo["vlans"].append({"id": svc["vlan"], "vni": svc["vni"], "name": svc["name"]})
    for name in list(state["intents"]):
        apply_intent(name)       # reprograma lo persistido (los nodos pueden haber reiniciado)
    threading.Thread(target=monitor, daemon=True).start()
    log(f"controlador escuchando en :{PORT} ({len(state['intents'])} intenciones)")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
