#!/usr/bin/env python3
"""Prueba de reconvergencia EVPN-VXLAN ante caida de un spine (objetivo < 1 s).

Lanza un ping de alta frecuencia host1 -> host3, 'apaga' el spine indicado
(bajando todas sus interfaces de fabric) y estima el tiempo de caida con los
paquetes perdidos. Restaura el spine al final.

Uso: python3 convergence_test.py --fail spine1
"""
import argparse
import re
import time
from datetime import datetime

from common import ROOT, connect, load_topology


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="host1")
    ap.add_argument("--dst", default="10.10.0.13")
    ap.add_argument("--fail", default="spine1")
    ap.add_argument("--interval", type=float, default=0.01)
    ap.add_argument("--count", type=int, default=1500)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()

    topo = load_topology()
    results = []
    for run in range(1, a.runs + 1):
        host, spine = connect(topo, a.src), connect(topo, a.fail)
        ifaces = [f"eth{i}" for i in range(len(topo["leafs"]))]
        host.send_command(f"ping -i {a.interval} -c {a.count} -q {a.dst} > /tmp/ping.out 2>&1 &")
        time.sleep(3)
        for i in ifaces:
            spine.send_command(f"ip link set {i} down")
        time.sleep(int(a.interval * a.count) + 5)
        out = host.send_command("cat /tmp/ping.out")
        for i in ifaces:
            spine.send_command(f"ip link set {i} up")
        m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received", out)
        if m:
            lost = int(m.group(1)) - int(m.group(2))
            down = lost * a.interval
            results.append(down)
            print(f"Corrida {run}: perdidos={lost}  caida estimada={down:.2f} s  "
                  f"{'CUMPLE' if down < 1 else 'NO CUMPLE'} (<1 s)")
        else:
            print(f"Corrida {run}: no se pudo leer el resultado:\n{out}")
        host.disconnect(); spine.disconnect()
        time.sleep(15)  # dejar reconverger antes de la siguiente corrida

    if results:
        rep = (f"# Reconvergencia - {datetime.now():%Y-%m-%d %H:%M}\nFallo: {a.fail}\n"
               f"Corridas (s): {[round(r, 2) for r in results]}\nPromedio: {sum(results)/len(results):.2f} s\n")
        (ROOT / "evidence" / f"convergencia_{datetime.now():%Y%m%d_%H%M%S}.txt").write_text(rep)
        print(rep)


if __name__ == "__main__":
    main()
