#!/usr/bin/env python3
"""Crea la topologia de la Entrega 1 en GNS3 a traves de su API REST.
Solo usa la libreria estandar de Python (no requiere pip).

Requisitos:
  - GNS3 abierto en Windows con el proyecto (por defecto 'netcloud') VACIO.
  - GNS3 VM encendida (indicador verde en Servers Summary).
  - Templates gsm-spine (5 adaptadores), gsm-leaf (4) y gsm-host (2).

Uso (PowerShell):
  python crear_topologia_gns3.py
  python crear_topologia_gns3.py --start        # ademas inicia todos los nodos
"""
import argparse
import base64
import json
import sys
import urllib.error
import urllib.request

COMPUTE = "vm"  # la GNS3 VM


class API:
    def __init__(self, base, user=None, password=None):
        self.base = base.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if user:
            tok = base64.b64encode(f"{user}:{password}".encode()).decode()
            self.headers["Authorization"] = f"Basic {tok}"

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            sys.exit(f"\nERROR HTTP {e.code} en {method} {path}:\n{e.read().decode()[:600]}")
        except urllib.error.URLError as e:
            sys.exit(f"\nNo se pudo conectar con GNS3 en {self.base}: {e.reason}\n"
                     "Verifica que GNS3 este abierto y el puerto (Edit > Preferences > Server).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:3080/v2")
    ap.add_argument("--project", default="netcloud")
    ap.add_argument("--user")
    ap.add_argument("--password")
    ap.add_argument("--start", action="store_true")
    a = ap.parse_args()
    api = API(a.server, a.user, a.password)

    print("Conectando con GNS3...")
    ver = api.call("GET", "/version")
    print(f"  GNS3 {ver.get('version')}")

    computes = {c["compute_id"]: c for c in api.call("GET", "/computes")}
    if COMPUTE not in computes:
        sys.exit("La GNS3 VM no aparece como servidor. Habilitala en Edit > Preferences > GNS3 VM.")
    if not computes[COMPUTE].get("connected"):
        sys.exit("La GNS3 VM existe pero no esta conectada. Espera el indicador verde en Servers Summary.")

    tpl = {t["name"]: t["template_id"] for t in api.call("GET", "/templates")}
    need = ["gsm-spine", "gsm-leaf", "gsm-host", "NAT", "Ethernet switch"]
    missing = [n for n in need if n not in tpl]
    if missing:
        sys.exit(f"Faltan templates: {missing}\nDisponibles: {sorted(tpl)}")

    proj = next((p for p in api.call("GET", "/projects") if p["name"] == a.project), None)
    if proj is None:
        proj = api.call("POST", "/projects", {"name": a.project})
        print(f"  Proyecto '{a.project}' creado")
    elif proj.get("status") != "opened":
        api.call("POST", f"/projects/{proj['project_id']}/open", {})
    pid = proj["project_id"]
    if api.call("GET", f"/projects/{pid}/nodes"):
        sys.exit(f"El proyecto '{a.project}' ya tiene nodos. Usa un proyecto vacio "
                 "(File > New blank project) o borra los nodos y reintenta.")

    nodes = {}

    def add(template, name, x, y):
        n = api.call("POST", f"/projects/{pid}/templates/{tpl[template]}",
                     {"x": x, "y": y, "compute_id": COMPUTE})
        if name != template:
            api.call("PUT", f"/projects/{pid}/nodes/{n['node_id']}", {"name": name})
        nodes[name] = n["node_id"]
        print(f"  + {name}")

    print("Creando nodos...")
    for i, x in enumerate((-150, 150), 1):
        add("gsm-spine", f"spine{i}", x, -250)
    for i, x in enumerate((-450, -150, 150, 450), 1):
        add("gsm-leaf", f"leaf{i}", x, -50)
    for i, x in enumerate((-450, -150, 150, 450), 1):
        add("gsm-host", f"host{i}", x, 150)
    add("Ethernet switch", "MGMT-SW", 0, 330)
    add("NAT", "NAT", 0, 450)

    # El switch por defecto trae 8 puertos; se necesitan 11 (10 nodos + NAT)
    ports = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1} for i in range(16)]
    api.call("PUT", f"/projects/{pid}/nodes/{nodes['MGMT-SW']}", {"properties": {"ports_mapping": ports}})

    def link(n1, p1, n2, p2):
        api.call("POST", f"/projects/{pid}/links", {"nodes": [
            {"node_id": nodes[n1], "adapter_number": p1[0], "port_number": p1[1]},
            {"node_id": nodes[n2], "adapter_number": p2[0], "port_number": p2[1]}]})
        print(f"  {n1}:{'eth'+str(p1[0]) if n1 != 'MGMT-SW' else 'sw'+str(p1[1])} <-> "
              f"{n2}:{'eth'+str(p2[0]) if n2 != 'MGMT-SW' else 'sw'+str(p2[1])}")

    print("Creando enlaces del fabric (spine-leaf)...")
    for s in (1, 2):
        for l in (1, 2, 3, 4):
            link(f"spine{s}", (l - 1, 0), f"leaf{l}", (s - 1, 0))
    print("Creando enlaces leaf-host...")
    for n in (1, 2, 3, 4):
        link(f"leaf{n}", (2, 0), f"host{n}", (0, 0))
    print("Creando enlaces de gestion...")
    sw = 0
    for name, eth in [("spine1", 4), ("spine2", 4), ("leaf1", 3), ("leaf2", 3), ("leaf3", 3),
                      ("leaf4", 3), ("host1", 1), ("host2", 1), ("host3", 1), ("host4", 1)]:
        link(name, (eth, 0), "MGMT-SW", (0, sw))
        sw += 1
    link("NAT", (0, 0), "MGMT-SW", (0, sw))

    print("\nTopologia creada: 10 nodos + switch + NAT, 23 enlaces.")
    if a.start:
        print("Iniciando nodos...")
        api.call("POST", f"/projects/{pid}/nodes/start", {})
        print("Orden de inicio enviada (espera 1-2 minutos).")
    else:
        print("Inicia todo con el boton verde de Play en GNS3.")


if __name__ == "__main__":
    main()
