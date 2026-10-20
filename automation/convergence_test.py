#!/usr/bin/env python3
"""Prueba de reconvergencia EVPN-VXLAN ante caida de un spine (objetivo < 1 s).

Lanza un ping de alta frecuencia host1 -> host3, provoca la falla del spine indicado
y estima el tiempo de caida con los paquetes perdidos. Restaura el spine al final.

Modos de falla (se ejecuta dentro de la GNS3 VM, que tiene acceso a Docker):
  crash  (por defecto) apagado del spine: se congela su plano de control
         (docker pause, FRR no puede avisar a nadie) y se bajan sus interfaces
         con nsenter (deja de reenviar). Los leafs lo detectan por BFD/OSPF.
  links  caida de los enlaces del spine con el plano de control vivo: el spine
         alcanza a inundar LSAs, por lo que la convergencia es casi inmediata.

Uso: python3 convergence_test.py --fail spine1 [--mode links]
"""
import argparse
import re
import subprocess
import time
from datetime import datetime

from common import ROOT, connect, load_topology


def sh(cmd):
    return subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True).stdout.strip()


def fail_spine(name, mode, ifaces, up):
    """Aplica (up=False) o revierte (up=True) la falla del spine."""
    c = sh(f"docker ps --format '{{{{.Names}}}}' | grep '\\.{name}\\.'")
    pid = sh(f"docker inspect -f '{{{{.State.Pid}}}}' {c}")
    if mode == "crash" and not up:
        sh(f"docker pause {c}")
    state = "up" if up else "down"
    sh(" && ".join(f"sudo -n nsenter -t {pid} -n ip link set {i} {state}" for i in ifaces))
    if mode == "crash" and up:
        sh(f"docker unpause {c}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="host1")
    ap.add_argument("--dst", default="10.10.0.13")
    ap.add_argument("--fail", default="spine1")
    ap.add_argument("--mode", choices=["crash", "links"], default="crash")
    ap.add_argument("--interval", type=float, default=0.01)
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()

    topo = load_topology()
    ifaces = [f"eth{i}" for i in range(len(topo["leafs"]))]
    results = []
    for run in range(1, a.runs + 1):
        host = connect(topo, a.src)
        host.send_command(f"rm -f /tmp/ping.out; ping -i {a.interval} -c {a.count} -q {a.dst} > /tmp/ping.out 2>&1 &")
        time.sleep(2)
        fail_spine(a.fail, a.mode, ifaces, up=False)
        time.sleep(int(a.interval * a.count))
        for _ in range(60):   # esperar el resumen del ping (puede tardar mas que interval*count)
            out = host.send_command("cat /tmp/ping.out")
            if "packets transmitted" in out:
                break
            time.sleep(1)
        fail_spine(a.fail, a.mode, ifaces, up=True)
        m = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received", out)
        if m:
            lost = int(m.group(1)) - int(m.group(2))
            down = lost * a.interval
            results.append(down)
            print(f"Corrida {run}: perdidos={lost}  caida estimada={down:.2f} s  "
                  f"{'CUMPLE' if down < 1 else 'NO CUMPLE'} (<1 s)")
        else:
            print(f"Corrida {run}: no se pudo leer el resultado:\n{out}")
        host.disconnect()
        time.sleep(20)  # dejar reconverger (OSPF, BFD y BGP) antes de la siguiente corrida

    if results:
        rep = (f"# Reconvergencia - {datetime.now():%Y-%m-%d %H:%M}\nFallo: {a.fail} (modo {a.mode})\n"
               f"Ping {a.src} -> {a.dst} cada {a.interval * 1000:.0f} ms\n"
               f"Corridas (s): {[round(r, 2) for r in results]}\nPromedio: {sum(results)/len(results):.2f} s\n")
        (ROOT / "evidence" / f"convergencia_{a.mode}_{a.fail}_{datetime.now():%Y%m%d_%H%M%S}.txt").write_text(rep)
        print(rep)


if __name__ == "__main__":
    main()
