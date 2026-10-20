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
    for group in ("spines", "leafs", "hosts"):
        nodes.update(topo[group])
    return nodes


def build_contexts(topo):
    """Calcula direccionamiento: enlace spine s <-> leaf l = 10.1.s.(2*(l-1))/31."""
    asn, hm = topo["asn"], topo["hello_multiplier"]
    spines, leafs, vlans = topo["spines"], topo["leafs"], topo["vlans"]
    ctx = {}
    for sname, s in spines.items():
        sn = int(sname.replace("spine", ""))
        links = [{"iface": f"eth{int(ln.replace('leaf', '')) - 1}",
                  "ip": f"10.1.{sn}.{2 * (int(ln.replace('leaf', '')) - 1)}",
                  "peer": ln} for ln in leafs]
        ctx[sname] = {"role": "spine", "name": sname, "loopback": s["loopback"], "asn": asn,
                      "hello_multiplier": hm, "links": links,
                      "neighbors": [{"ip": l["loopback"], "name": n} for n, l in leafs.items()]}
    for lname, l in leafs.items():
        ln = int(lname.replace("leaf", ""))
        links = [{"iface": f"eth{int(sp.replace('spine', '')) - 1}",
                  "ip": f"10.1.{int(sp.replace('spine', ''))}.{2 * (ln - 1) + 1}",
                  "peer": sp} for sp in spines]
        ctx[lname] = {"role": "leaf", "name": lname, "loopback": l["loopback"], "asn": asn,
                      "hello_multiplier": hm, "links": links, "vlans": vlans,
                      "spines": [{"ip": s["loopback"], "name": n} for n, s in spines.items()],
                      "access_port": l["access_port"], "access_vlan": l["vlan"]}
    for hname, h in topo["hosts"].items():
        ctx[hname] = {"role": "host", "name": hname, "iface": "eth0", "ip": h["ip"]}
    return ctx


# Al arrancar el contenedor zebra puede caer y watchfrr tarda ~60 s en revivirlo;
# sin zebra, vtysh -f falla en silencio. Se espera hasta 100 s antes de aplicar.
FRR_APPLY = ("for i in $(seq 100); do pgrep -x zebra >/dev/null && break; sleep 1; done; "
             "vtysh -f /etc/frr/frr.conf")

# rol -> lista de (plantilla, ruta remota, comando de aplicacion)
PLAN = {
    "spine": [("spine.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh"),
              ("spine.frr.j2", "/etc/frr/frr.conf", FRR_APPLY)],
    "leaf": [("leaf.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh"),
             ("leaf.frr.j2", "/etc/frr/frr.conf", FRR_APPLY)],
    "host": [("host.linux.j2", "/tmp/setup.sh", "sh /tmp/setup.sh")],
}


def jinja_env():
    return Environment(loader=FileSystemLoader(str(TEMPLATES)), undefined=StrictUndefined,
                       trim_blocks=True, lstrip_blocks=True)


def connect(topo, name):
    from netmiko import ConnectHandler  # import tardio: permite --dry-run sin netmiko
    node = all_nodes(topo)[name]
    cred = topo["credentials"]
    return ConnectHandler(device_type="linux", host=node["mgmt"], username=cred["username"],
                          password=cred["password"], conn_timeout=30, auth_timeout=30,
                          banner_timeout=30)
