#!/usr/bin/env python3
"""Agrega la Entrega 2 (5G, NFV, F5G) al proyecto GNS3 'netcloud' de la Entrega 1, via API REST.
Solo libreria estandar. Es idempotente: si un nodo o enlace ya existe, lo deja como esta.

Requisitos: GNS3 abierto, GNS3 VM en verde, imagenes gsm-5gc, gsm-ran, gsm-vnf y mongo:6.0 en la VM.
Uso (PowerShell, en la carpeta del repo):  python gns3\\agregar_entrega2.py
Detiene todos los nodos (los leafs cambian de numero de adaptadores); despues ejecuta scripts\\levantar_lab.ps1.
"""
import sys
import urllib.request

from crear_topologia_gns3 import API

PROJECT = "netcloud"
# Puertos de acceso nuevos en los leafs: la gestion pasa a la interfaz de mayor numero (start.sh)
LEAF_ADAPTERS = {"leaf1": 5, "leaf2": 6, "leaf3": 5, "leaf4": 5}

# nombre: (imagen, adaptadores, x, y)  -- la ultima interfaz es gestion, salvo mongo
DOCKER = {
    "mongo":  ("mongo:6.0", 1, -1100, -200),
    "core5g": ("gsm-5gc:1.0", 4, -850, -200),
    "fw1":    ("gsm-vnf:1.0", 3, -1050, 250),
    "fw2":    ("gsm-vnf:1.0", 3, -850, 250),
    "lb":     ("gsm-vnf:1.0", 2, -1100, 550),
    "srv1":   ("gsm-vnf:1.0", 2, -950, 650),
    "srv2":   ("gsm-vnf:1.0", 2, -800, 650),
    "gnb":    ("gsm-ran:1.0", 3, 800, -200),
    "ue":     ("gsm-ran:1.0", 2, 1050, -200),
    "olt":    ("gsm-vnf:1.0", 3, 800, 250),
    "ont1":   ("gsm-vnf:1.0", 2, 1200, 120),
    "ont2":   ("gsm-vnf:1.0", 2, 1200, 270),
    "ont3":   ("gsm-vnf:1.0", 2, 1200, 420),
}
BUILTIN = {"SW-N6": ("ethernet_switch", -700, 100), "SW-SVC": ("ethernet_switch", -700, 450),
           "HUB-ODN": ("ethernet_hub", 1000, 250), "MGMT-SW2": ("ethernet_switch", 250, 450)}
# GNS3 no permite agregar puertos a un switch con enlaces: la gestion nueva va a MGMT-SW2 (16 puertos),
# en cascada con MGMT-SW (puerto 15 de ambos)
SW2_PORTS = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1, "ethertype": ""}
             for i in range(16)]

# (nodo, adaptador, puerto) <-> (nodo, adaptador, puerto); en switches/hub el adaptador es 0
LINKS = [
    (("core5g", 0, 0), ("leaf1", 3, 0)),     # N2/N3  VNI 10030
    (("core5g", 1, 0), ("SW-N6", 0, 0)),     # N6     VNI 10040
    (("core5g", 2, 0), ("mongo", 0, 0)),     # base de datos de abonados
    (("fw1", 0, 0), ("SW-N6", 0, 1)), (("fw2", 0, 0), ("SW-N6", 0, 2)),
    (("fw1", 1, 0), ("SW-SVC", 0, 1)), (("fw2", 1, 0), ("SW-SVC", 0, 2)),
    (("lb", 0, 0), ("SW-SVC", 0, 3)), (("srv1", 0, 0), ("SW-SVC", 0, 4)), (("srv2", 0, 0), ("SW-SVC", 0, 5)),
    (("SW-N6", 0, 7), ("leaf2", 3, 0)),      # VNI 10040
    (("SW-SVC", 0, 7), ("leaf2", 4, 0)),     # VNI 10050
    (("gnb", 0, 0), ("leaf3", 3, 0)),        # N2/N3  VNI 10030 (sitio Planta)
    (("gnb", 1, 0), ("ue", 0, 0)),           # interfaz de radio simulada
    (("olt", 0, 0), ("leaf4", 3, 0)),        # uplink F5G  VNI 10060
    (("olt", 1, 0), ("HUB-ODN", 0, 0)),      # PON (splitter pasivo)
    (("ont1", 0, 0), ("HUB-ODN", 0, 1)), (("ont2", 0, 0), ("HUB-ODN", 0, 2)), (("ont3", 0, 0), ("HUB-ODN", 0, 3)),
    (("MGMT-SW2", 0, 15), ("MGMT-SW", 0, 15)),
]
# gestion: interfaz de mayor numero -> puerto del MGMT-SW2
MGMT = {"core5g": 0, "gnb": 1, "ue": 2, "fw1": 3, "fw2": 4, "lb": 5, "srv1": 6, "srv2": 7,
        "olt": 8, "ont1": 9, "ont2": 10, "ont3": 11}
MONGO_NET = "auto eth0\niface eth0 inet static\n\taddress 10.33.0.2\n\tnetmask 255.255.255.252\n"


def main():
    api = API("http://127.0.0.1:3080/v2")
    vm = next((c for c in api.call("GET", "/computes") if c["compute_id"] == "vm"), None)
    if not vm or not vm.get("connected"):
        sys.exit("La GNS3 VM no esta conectada: abre GNS3 y espera el indicador verde.")
    proj = next(p for p in api.call("GET", "/projects") if p["name"] == PROJECT)
    pid = proj["project_id"]
    api.call("POST", f"/projects/{pid}/open")
    nodes = lambda: {n["name"]: n for n in api.call("GET", f"/projects/{pid}/nodes")}

    print("Deteniendo nodos...")
    api.call("POST", f"/projects/{pid}/nodes/stop", {})
    n = nodes()

    sw = n["MGMT-SW"]

    # Leafs: mas adaptadores y gestion movida a la interfaz de mayor numero
    links = api.call("GET", f"/projects/{pid}/links")
    for leaf, adapters in LEAF_ADAPTERS.items():
        node = n[leaf]
        if node["properties"]["adapters"] == adapters:
            continue
        mgmt_link = next(l for l in links if {e["node_id"] for e in l["nodes"]} == {node["node_id"], sw["node_id"]})
        sw_port = next(e for e in mgmt_link["nodes"] if e["node_id"] == sw["node_id"])["port_number"]
        api.call("DELETE", f"/projects/{pid}/links/{mgmt_link['link_id']}")
        api.call("PUT", f"/projects/{pid}/nodes/{node['node_id']}", {"properties": {"adapters": adapters}})
        api.call("POST", f"/projects/{pid}/links", {"nodes": [
            {"node_id": node["node_id"], "adapter_number": adapters - 1, "port_number": 0},
            {"node_id": sw["node_id"], "adapter_number": 0, "port_number": sw_port}]})
        print(f"  {leaf}: {adapters} adaptadores, gestion en eth{adapters - 1}")

    # Nodos nuevos
    for name, (image, adapters, x, y) in DOCKER.items():
        if name not in n:
            api.call("POST", f"/projects/{pid}/nodes", {
                "name": name, "node_type": "docker", "compute_id": "vm", "x": x, "y": y,
                "symbol": ":/symbols/docker_guest.svg",
                "properties": {"image": image, "adapters": adapters, "console_type": "telnet"}})
            print(f"  + {name} ({image})")
    for name, (ntype, x, y) in BUILTIN.items():
        if name not in n:
            body = {"name": name, "node_type": ntype, "compute_id": "vm", "x": x, "y": y}
            if name == "MGMT-SW2":
                body["properties"] = {"ports_mapping": SW2_PORTS}
            api.call("POST", f"/projects/{pid}/nodes", body)
            print(f"  + {name} ({ntype})")
    n = nodes()

    # IP fija de mongo (imagen oficial, sin SSH): la aplica el init de GNS3 al arrancar
    req = urllib.request.Request(f"{api.base}/projects/{pid}/nodes/{n['mongo']['node_id']}/files/etc/network/interfaces",
                                 data=MONGO_NET.encode(), method="POST")
    urllib.request.urlopen(req, timeout=60).read()

    # Enlaces
    used = {(e["node_id"], e["adapter_number"], e["port_number"])
            for l in api.call("GET", f"/projects/{pid}/links") for e in l["nodes"]}
    todo = LINKS + [((name, DOCKER[name][1] - 1, 0), ("MGMT-SW2", 0, port)) for name, port in MGMT.items()]
    created = 0
    for a, b in todo:
        ends = [{"node_id": n[x]["node_id"], "adapter_number": ad, "port_number": pt} for x, ad, pt in (a, b)]
        if any((e["node_id"], e["adapter_number"], e["port_number"]) in used for e in ends):
            continue
        api.call("POST", f"/projects/{pid}/links", {"nodes": ends})
        created += 1
    print(f"  {created} enlaces nuevos. Listo: ejecuta scripts\\levantar_lab.ps1")


if __name__ == "__main__":
    main()
