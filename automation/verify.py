#!/usr/bin/env python3
"""Entrega 1 - Verificacion: tablas EVPN, VNIs y conectividad L2 extendida.
Guarda la evidencia en ../evidence/verify_<fecha>.txt"""
from datetime import datetime

from common import ROOT, connect, load_topology

VTY = {
    "spine": ["show ip ospf neighbor", "show bgp l2vpn evpn summary", "show ipv6 ospf6 neighbor", "show bfd peers brief"],
    "leaf": ["show ip ospf neighbor", "show bgp l2vpn evpn summary", "show evpn vni",
             "show ipv6 ospf6 neighbor", "show ipv6 route ospf6", "show bfd peers brief",
             "show bgp l2vpn evpn route type macip", "show bgp l2vpn evpn route type multicast"],
}
PINGS = [("host1", "10.10.0.13", "VLAN10 DC1 -> Planta (L2 extendida)"),
         ("host2", "10.20.0.14", "VLAN20 DC1 -> Planta (L2 extendida)"),
         ("host3", "10.10.0.11", "VLAN10 Planta -> DC1"),
         ("host4", "10.20.0.12", "VLAN20 Planta -> DC1")]


def main():
    topo = load_topology()
    lines = [f"# Verificacion Entrega 1 - {datetime.now():%Y-%m-%d %H:%M:%S}\n"]
    for group, key in (("spines", "spine"), ("leafs", "leaf")):
        for name in topo[group]:
            conn = connect(topo, name)
            for cmd in VTY[key]:
                lines.append(f"\n===== {name}# {cmd} =====")
                lines.append(conn.send_command(f'vtysh -c "{cmd}"', read_timeout=30))
            lines.append(f"\n===== {name}# SIDs SRv6 locales (ip -6 route | seg6local) =====")
            lines.append(conn.send_command("ip -6 route show | grep seg6local"))
            if key == "leaf":
                lines.append(f"\n===== {name}# bridge fdb show (entradas VXLAN) =====")
                lines.append(conn.send_command("bridge fdb show | grep -i vxlan | head -30"))
            conn.disconnect()
    for src, dst, desc in PINGS:
        conn = connect(topo, src)
        lines.append(f"\n===== {src}: ping {dst}  [{desc}] =====")
        lines.append(conn.send_command(f"ping -c 4 -W 2 {dst}", read_timeout=30))
        conn.disconnect()
    out = ROOT / "evidence" / f"verify_{datetime.now():%Y%m%d_%H%M%S}.txt"
    out.write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nEvidencia guardada en {out}")


if __name__ == "__main__":
    main()
