#!/usr/bin/env python3
"""Agrega la Entrega 3 (Zero Trust) al proyecto GNS3 'netcloud': 2 nodos nuevos en el segmento de
servicios OT (VNI 10050), usando puertos libres de switches existentes (no cambia adaptadores de nodos
actuales, asi que no hace falta rehacer la topologia). Idempotente.
Uso (PowerShell, en la carpeta del repo):  python gns3\\agregar_entrega3.py
"""
import sys

from crear_topologia_gns3 import API

PROJECT = "netcloud"
# nombre: (imagen, adaptadores, x, y). eth0 = servicios OT, eth1 = gestion
DOCKER = {
    "dbsrv":   ("gsm-vnf:1.0", 2, -950, 820),
    "pc-corp": ("gsm-vnf:1.0", 2, -1150, 820),
}
# (nodo, adaptador, puerto) <-> (switch, 0, puerto libre)
LINKS = [
    (("dbsrv", 0, 0),   ("SW-SVC", 0, 0)),     # servicios OT (VNI 10050)
    (("pc-corp", 0, 0), ("SW-SVC", 0, 6)),
    (("dbsrv", 1, 0),   ("MGMT-SW2", 0, 12)),  # gestion
    (("pc-corp", 1, 0), ("MGMT-SW2", 0, 13)),
]


def main():
    api = API("http://127.0.0.1:3080/v2")
    vm = next((c for c in api.call("GET", "/computes") if c["compute_id"] == "vm"), None)
    if not vm or not vm.get("connected"):
        sys.exit("La GNS3 VM no esta conectada: abre GNS3 y espera el indicador verde.")
    proj = next(p for p in api.call("GET", "/projects") if p["name"] == PROJECT)
    pid = proj["project_id"]
    api.call("POST", f"/projects/{pid}/open")
    n = {x["name"]: x for x in api.call("GET", f"/projects/{pid}/nodes")}

    for name, (image, adapters, x, y) in DOCKER.items():
        if name not in n:
            api.call("POST", f"/projects/{pid}/nodes", {
                "name": name, "node_type": "docker", "compute_id": "vm", "x": x, "y": y,
                "symbol": ":/symbols/docker_guest.svg",
                "properties": {"image": image, "adapters": adapters, "console_type": "telnet"}})
            print(f"  + {name} ({image})")
    n = {x["name"]: x for x in api.call("GET", f"/projects/{pid}/nodes")}

    used = {(e["node_id"], e["adapter_number"], e["port_number"])
            for l in api.call("GET", f"/projects/{pid}/links") for e in l["nodes"]}
    creados = 0
    for a, b in LINKS:
        ends = [{"node_id": n[x]["node_id"], "adapter_number": ad, "port_number": pt} for x, ad, pt in (a, b)]
        if any((e["node_id"], e["adapter_number"], e["port_number"]) in used for e in ends):
            continue
        api.call("POST", f"/projects/{pid}/links", {"nodes": ends})
        creados += 1
    print(f"  {creados} enlaces nuevos. Listo: ejecuta scripts\\levantar_lab.ps1")


if __name__ == "__main__":
    main()
