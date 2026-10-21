"""Funciones comunes: carga de topologia, contextos Jinja2 y conexion Netmiko."""
from pathlib import Path
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"


def load_topology():
    with open(ROOT / "topology" / "topology.yaml") as f:
        return yaml.safe_load(f)


def all_nodes(topo):
    nodes = {}
    for group in ("spines", "leafs", "hosts", "servicios"):
        nodes.update(topo.get(group, {}))
    return nodes


def node_num(node):
    """Numero de nodo para SRv6 = ultimo octeto del loopback (spine1=1, leaf3=13)."""
    return int(node["loopback"].split(".")[-1])


def build_contexts(topo):
    """Calcula direccionamiento: enlace spine s <-> leaf l = 10.1.s.(2*(l-1))/31."""
    asn, hm = topo["asn"], topo["hello_multiplier"]
    spines, leafs, vlans = topo["spines"], topo["leafs"], topo["vlans"]
    sr = topo["srv6_prefix"]
    ctx = {}
    for sname, s in spines.items():
        sn = int(sname.replace("spine", ""))
        links = [{"iface": f"eth{int(ln.replace('leaf', '')) - 1}",
                  "ip": f"10.1.{sn}.{2 * (int(ln.replace('leaf', '')) - 1)}",
                  "peer": ln} for ln in leafs]
        ctx[sname] = {"role": "spine", "name": sname, "loopback": s["loopback"], "asn": asn,
                      "sr": sr, "n": node_num(s),
                      "hello_multiplier": hm, "links": links,
                      "neighbors": [{"ip": l["loopback"], "name": n} for n, l in leafs.items()]}
    for lname, l in leafs.items():
        ln = int(lname.replace("leaf", ""))
        links = [{"iface": f"eth{int(sp.replace('spine', '')) - 1}",
                  "ip": f"10.1.{int(sp.replace('spine', ''))}.{2 * (ln - 1) + 1}",
                  "peer": sp} for sp in spines]
        ctx[lname] = {"role": "leaf", "name": lname, "loopback": l["loopback"], "asn": asn,
                      "sr": sr, "n": node_num(l),
                      "hello_multiplier": hm, "links": links, "vlans": vlans,
                      "spines": [{"ip": s["loopback"], "name": n} for n, s in spines.items()],
                      "access": l["access"]}
    for hname, h in topo["hosts"].items():
        ctx[hname] = {"role": "host", "name": hname, "iface": "eth0", "ip": h["ip"]}
    # Entrega 2: cada equipo ve su propia definicion y las secciones globales de 5G, NFV y F5G
    for name, n in topo.get("servicios", {}).items():
        ctx[name] = {**n, "name": name, "c5g": topo["nucleo5g"], "nfv": topo["nfv"], "f5g": topo["f5g"],
                     "ont": topo["f5g"]["ont"].get(name), "abonados": topo["nucleo5g"]["abonados"],
                     "servidores": {k: v["ip"] for k, v in topo["servicios"].items() if v["role"] == "srv"}}
    return ctx


# Al arrancar el contenedor zebra puede caer y watchfrr tarda ~60 s en revivirlo;
# sin zebra, vtysh -f falla en silencio. Se espera hasta 100 s antes de aplicar.
FRR_APPLY = ("for i in $(seq 100); do pidof zebra >/dev/null && break; sleep 1; done; "
             "vtysh -f /etc/frr/frr.conf")

NF_5GC = ["nrf", "scp", "ausf", "udm", "udr", "pcf", "nssf", "bsf", "amf", "smf", "upf"]
SETUP = "/tmp/setup.sh", "sh /tmp/setup.sh"

# rol -> lista de (plantilla, ruta remota, comando de aplicacion[, variables extra])
# Una funcion en lugar de lista genera los pasos segun el contexto (p. ej. un archivo por abonado).
PLAN = {
    "spine": [("spine.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh"),
              ("spine.frr.j2", "/etc/frr/frr.conf", FRR_APPLY)],
    "leaf": [("leaf.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh"),
             ("leaf.frr.j2", "/etc/frr/frr.conf", FRR_APPLY)],
    "host": [("host.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh")],
    # Entrega 2
    "core5g": [("5g/core5g.linux.j2", *SETUP)]
              + [(f"5g/{nf}.yaml.j2" if nf in ("amf", "smf", "upf") else "5g/nf.yaml.j2",
                  f"/etc/gsm5g/{nf}.yaml", "true", {"nf": nf}) for nf in NF_5GC]
              + [("5g/abonados.py.j2", "/etc/gsm5g/abonados.py", "true"),
                 ("5g/core5g.iniciar.j2", "/etc/gsm5g/iniciar.sh", "bash /etc/gsm5g/iniciar.sh")],
    "gnb": [("5g/gnb.linux.j2", *SETUP), ("5g/gnb.yaml.j2", "/etc/gsm5g/gnb.yaml", "true"),
            ("5g/gnb.iniciar.j2", "/etc/gsm5g/iniciar.sh", "bash /etc/gsm5g/iniciar.sh")],
    "ue": lambda ctx: [("5g/ue.linux.j2", *SETUP)]
                      + [("5g/ue.yaml.j2", f"/etc/gsm5g/ue-{a['nombre']}.yaml", "true", {"a": a})
                         for a in ctx["abonados"]]
                      + [("5g/ue.iniciar.j2", "/etc/gsm5g/iniciar.sh", "bash /etc/gsm5g/iniciar.sh")],
    "fw": [("nfv/fw.nft.j2", "/etc/gsm/fw.nft", "true"), ("nfv/fw.linux.j2", *SETUP)],
    "lb": [("nfv/haproxy.cfg.j2", "/etc/gsm/haproxy.cfg", "true"), ("nfv/lb.linux.j2", *SETUP)],
    "srv": [("nfv/srv.py.j2", "/etc/gsm/srv.py", "true"), ("nfv/srv.linux.j2", *SETUP)],
    "olt": [("f5g/olt_dba.py.j2", "/etc/gsm/olt_dba.py", "true"), ("f5g/olt.linux.j2", *SETUP)],
    "ont": [("f5g/onu_agent.py.j2", "/etc/gsm/onu_agent.py", "true"), ("f5g/ont.linux.j2", *SETUP)],
}
# Orden de despliegue: el gNB necesita el nucleo arriba y los UEs necesitan el gNB
ETAPAS = [None, {"core5g"}, {"gnb"}, {"ue"}]   # None = todos los demas, en paralelo


def jinja_env():
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                       trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)


def connect(topo, name):
    from netmiko import ConnectHandler  # import tardio: permite --dry-run sin netmiko
    node = all_nodes(topo)[name]
    cred = topo["credentials"]
    return ConnectHandler(device_type="linux", host=node["mgmt"], username=cred["username"],
                          password=cred["password"], conn_timeout=30, auth_timeout=30,
                          banner_timeout=30)
