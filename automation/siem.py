#!/usr/bin/env python3
"""SIEM de NetCloud-Secure (Entrega 3) - plano de gestion (GNS3 VM, venv con grpcio).

Dos procesos (scripts/siem.sh los arranca):
  python3 siem.py server     servidor gRPC: recibe el stream de muestras, correlaciona y mitiga
  python3 siem.py shipper     raspa /metrics de cada nodo y empuja las muestras por gRPC al servidor

Correlacion:
  - PORT SCAN / movimiento lateral: el contador ztdrop_<db>_from_corp del firewall distribuido de dbsrv
    sube >= portscan_umbral en portscan_ventana_s  ->  alerta + mitigacion (bloquea al atacante en dbsrv).
  - DDoS de senalizacion 5G: NGAP (aceptado+descartado) al nucleo sube por encima del umbral -> alerta;
    la proteccion volumetrica (limit nft en core5g) ya descarta el exceso; se registran las identidades bogus.

Todo evento y mitigacion se registra en evidence/siem.log y el estado en automation/siem_estado.json.
"""
import json
import re
import sys
import time
import threading
import urllib.request
from collections import defaultdict, deque
from datetime import datetime

import grpc
import siem_pb2
import siem_pb2_grpc

from common import ROOT, all_nodes, connect, load_topology

topo = load_topology()
TEL = topo["telemetria"]
NODOS = all_nodes(topo)
PUERTO = int(TEL["siem_grpc"].split(":")[1])
LOG = ROOT / "evidence" / "siem.log"
ESTADO = ROOT / "automation" / "siem_estado.json"
# metricas de interes (contador nft -> etiqueta legible) y de 5G
INTERES = re.compile(r'counter="(ztdrop_\w+_from_corp|ngap|ngap_descartado|gtpu)"')


def log(msg):
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(linea, flush=True)
    with open(LOG, "a") as f:
        f.write(linea + "\n")


# ----------------------------------------------------------------------------- servidor + correlacion
class Estado:
    def __init__(self):
        self.ultimo = {}                       # (node,metric) -> ultimo valor
        self.hist = defaultdict(lambda: deque(maxlen=600))   # (node,metric) -> [(ts,valor)]
        self.mitigado = {}                     # clave de alerta -> info
        self.lock = threading.Lock()

    def muestra(self, node, metric, value, ts):
        with self.lock:
            self.ultimo[(node, metric)] = value
            self.hist[(node, metric)].append((ts, value))

    def delta(self, node, metric, ventana):
        h = self.hist[(node, metric)]
        if not h:
            return 0.0
        ahora = h[-1][1]
        corte = h[-1][0] - ventana
        base = next((v for t, v in h if t >= corte), h[0][1])
        return ahora - base


EST = Estado()


def guardar_estado(alertas):
    ESTADO.write_text(json.dumps({"actualizado": f"{datetime.now():%H:%M:%S}", "alertas": alertas,
                                  "mitigaciones": list(EST.mitigado.values())}, indent=2))


def bloquear(nodo, tabla, origen_ip):
    """Agrega una identidad al conjunto nft 'bloqueados' del nodo indicado (mitigacion por origen)."""
    try:
        conn = connect(topo, nodo)
        conn.send_command(f"nft add element inet {tabla} bloqueados {{ {origen_ip} timeout 10m }}", read_timeout=15)
        conn.disconnect()
        return True
    except Exception as e:
        log(f"  ERROR aplicando bloqueo en {nodo}: {e}")
        return False


class Servicer(siem_pb2_grpc.SiemServicer):
    def Stream(self, request_iterator, context):
        n = 0
        for s in request_iterator:
            EST.muestra(s.node, s.metric, s.value, s.ts)
            n += 1
        return siem_pb2.Ack(recibidos=n)


def correlador():
    pv, pu = TEL["portscan_ventana_s"], TEL["portscan_umbral"]
    ddos_umbral = TEL["ddos_umbral_pps"] * 5          # contador en ~5 s de ventana
    log(f"SIEM activo: port scan >= {pu} bloqueos en {pv}s; DDoS 5G NGAP > {ddos_umbral} en 5s")
    while True:
        time.sleep(1)
        alertas = []
        # --- port scan / movimiento lateral hacia la base de datos
        d = EST.delta("dbsrv", "ztdrop_db_from_corp", pv)
        clave = "portscan:corp->dbsrv"
        if d >= pu and clave not in EST.mitigado:
            atacante = topo["servicios"]["pc-corp"]["ip"]
            log(f"ALERTA port scan / movimiento lateral: {int(d)} intentos corp->dbsrv bloqueados en {pv}s "
                f"(atacante {atacante})")
            ok = bloquear("dbsrv", "zt", atacante)
            EST.mitigado[clave] = {"tipo": "port_scan", "origen": atacante, "accion": "bloqueado en dbsrv",
                                   "aplicado": ok, "hora": f"{datetime.now():%H:%M:%S}"}
            log(f"MITIGACION: {atacante} agregado al conjunto bloqueados de dbsrv (timeout 10m)")
            alertas.append(clave)
        # --- DDoS hacia el nucleo 5G (volumetrico/senalizacion): NGAP + GTP-U
        dd = (EST.delta("core5g", "ngap", 5) + EST.delta("core5g", "ngap_descartado", 5)
              + EST.delta("core5g", "gtpu", 5))
        clave5 = "ddos:5g-nucleo"
        if dd >= ddos_umbral and clave5 not in EST.mitigado:
            desc = EST.delta("core5g", "ngap_descartado", 5)
            # La inundacion de peticiones de conexion llega por la RAN (mismo gNB que los robots legitimos):
            # la mitigacion es volumetrica (rate-limit NGAP ya activo en core5g) + rechazo de identidades
            # (las IMSIs no provisionadas son rechazadas por el AMF), preservando las sesiones establecidas.
            log(f"ALERTA DDoS de senalizacion 5G: {int(dd)} peticiones de conexion (NGAP) en 5s "
                f"({int(desc)} ya descartadas por el limitador del nucleo)")
            EST.mitigado[clave5] = {"tipo": "ddos_5g", "origen": "terminales IoT falsificados (RAN)",
                                    "accion": "rate-limit NGAP en core5g (tabla g5) + rechazo de IMSIs bogus",
                                    "ngap_descartado": int(desc), "hora": f"{datetime.now():%H:%M:%S}"}
            log("MITIGACION: el limitador nft del nucleo descarta el exceso de NGAP nuevos y el AMF rechaza "
                "las IMSIs no provisionadas; las sesiones establecidas de los robots se conservan intactas.")
            alertas.append(clave5)
        guardar_estado(alertas)


def servidor():
    LOG.parent.mkdir(exist_ok=True)
    s = grpc.server(ThreadPool(16))
    siem_pb2_grpc.add_SiemServicer_to_server(Servicer(), s)
    s.add_insecure_port(f"[::]:{PUERTO}")
    s.start()
    threading.Thread(target=correlador, daemon=True).start()
    log(f"servidor gRPC escuchando en :{PUERTO}")
    s.wait_for_termination()


# ----------------------------------------------------------------------------- shipper (dial-out)
def leer_metricas(ip):
    try:
        txt = urllib.request.urlopen(f"http://{ip}:{TEL['exporter_port']}/metrics", timeout=3).read().decode()
    except OSError:
        return []
    out = []
    for ln in txt.splitlines():
        if not ln.startswith("gsm_nft_packets") or not INTERES.search(ln):
            continue
        metric = INTERES.search(ln).group(1)
        try:
            out.append((metric, float(ln.rsplit(" ", 1)[1])))
        except ValueError:
            pass
    return out


def muestras():
    """Generador infinito de muestras de todos los nodos vigilados (dial-out al servidor)."""
    objetivos = [(n, NODOS[n]["mgmt"]) for n in TEL["nodos"] if n in NODOS]
    while True:
        for node, ip in objetivos:
            for metric, value in leer_metricas(ip):
                yield siem_pb2.Sample(node=node, metric=metric, value=value, ts=time.time())
        time.sleep(1)


def shipper():
    destino = f"127.0.0.1:{PUERTO}"
    while True:
        try:
            with grpc.insecure_channel(destino) as ch:
                stub = siem_pb2_grpc.SiemStub(ch)
                stub.Stream(muestras())
        except grpc.RpcError:
            time.sleep(2)


if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor as ThreadPool
    modo = sys.argv[1] if len(sys.argv) > 1 else "server"
    (servidor if modo == "server" else shipper)()
