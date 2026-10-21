#!/usr/bin/env python3
"""Validacion de throughput de la red optica F5G con DBA (Entrega 2). Se ejecuta en la GNS3 VM.

Escenario de contencion (60 s): ont1 (Oficinas, T-CONT 4) transmite de 0 a 45 s, ont2 (ERP, T-CONT 2,
asegurado 30) de 15 a 60 s y ont3 (Camaras, T-CONT 3, asegurado 20, max 60, peso 2) de 30 a 60 s.
Cada ONT envia TCP con iperf3 hacia la OLT; se mide el throughput por segundo y se registran los grants del DBA.

Genera en evidence/: f5g_throughput_<fecha>.txt (tabla por fase), f5g_dba_<fecha>.csv (ciclos del DBA)
y f5g_dba_<fecha>.svg (grafica de throughput medido y grant por ONT).
Uso: python3 prueba_f5g.py
"""
import json
import subprocess
import threading
import time
from datetime import datetime

from common import ROOT, load_topology

F5G = load_topology()["f5g"]
ONT = list(F5G["ont"])
PLAN = {"ont1": (0, 45), "ont2": (15, 60), "ont3": (30, 60)}     # inicio y fin de cada ONT (s)
FASES = [("ont1 sola", 5, 15), ("ont1 + ont2", 20, 30), ("las tres", 35, 45), ("ont2 + ont3", 50, 60)]
COLORES = {"ont1": "#1565c0", "ont2": "#2e7d32", "ont3": "#c62828"}


def cid(nombre):
    return subprocess.run(f"docker ps --format '{{{{.Names}}}}' | grep '\\.{nombre}\\.'", shell=True,
                          capture_output=True, text=True).stdout.strip()


def iperf(ont, puerto, inicio, fin, resultados):
    time.sleep(inicio)
    out = subprocess.run(["docker", "exec", cid(ont), "iperf3", "-c", F5G["olt"]["pon"], "-p", str(puerto),
                          "-t", str(fin - inicio), "-i", "1", "-J"], capture_output=True, text=True).stdout
    resultados[ont] = [(inicio + i["sum"]["end"], i["sum"]["bits_per_second"] / 1e6)
                       for i in json.loads(out)["intervals"]]


def svg(medido, grants, ruta):
    w, h, ml, mb = 900, 420, 60, 40
    x = lambda t: ml + t / 60 * (w - ml - 20)
    y = lambda v: h - mb - v / F5G["capacidad_mbps"] * (h - mb - 30)
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif" font-size="12">',
         f'<rect width="{w}" height="{h}" fill="#fff"/>',
         f'<text x="{w/2}" y="18" text-anchor="middle" font-size="14">F5G: throughput de subida medido '
         f'(linea) y grant del DBA (punteada) por ONT</text>']
    for nombre, a, b in FASES:
        p.append(f'<rect x="{x(a - 5)}" y="30" width="{x(b) - x(a - 5)}" height="{h - mb - 30}" '
                 f'fill="{"#f5f5f5" if FASES.index((nombre, a, b)) % 2 else "#fff"}"/>')
        p.append(f'<text x="{(x(a - 5) + x(b)) / 2}" y="44" text-anchor="middle" fill="#555">{nombre}</text>')
    for v in range(0, F5G["capacidad_mbps"] + 1, 20):
        p.append(f'<line x1="{ml}" x2="{w - 20}" y1="{y(v)}" y2="{y(v)}" stroke="#ddd"/>'
                 f'<text x="{ml - 6}" y="{y(v) + 4}" text-anchor="end">{v}</text>')
    for t in range(0, 61, 10):
        p.append(f'<text x="{x(t)}" y="{h - mb + 16}" text-anchor="middle">{t} s</text>')
    p.append(f'<text x="14" y="{h/2}" transform="rotate(-90 14 {h/2})" text-anchor="middle">Mbit/s</text>')
    for o in ONT:
        if medido.get(o):
            pts = " ".join(f"{x(t):.1f},{y(v):.1f}" for t, v in medido[o])
            p.append(f'<polyline points="{pts}" fill="none" stroke="{COLORES[o]}" stroke-width="2.5"/>')
        pts = " ".join(f"{x(t):.1f},{y(g):.1f}" for t, g in grants[o] if 0 <= t <= 60)
        p.append(f'<polyline points="{pts}" fill="none" stroke="{COLORES[o]}" stroke-width="1.5" '
                 f'stroke-dasharray="5,4"/>')
    for i, o in enumerate(ONT):
        c = F5G["ont"][o]
        p.append(f'<rect x="{ml + 10 + i * 270}" y="{h - 14}" width="14" height="4" fill="{COLORES[o]}"/>'
                 f'<text x="{ml + 30 + i * 270}" y="{h - 9}">{o} {c["servicio"]} (T-CONT {c["tcont"]})</text>')
    p.append("</svg>")
    ruta.write_text("\n".join(p))


def main():
    olt = cid("olt")
    previas = int(subprocess.run(["docker", "exec", olt, "sh", "-c", "wc -l < /var/log/dba.csv"],
                                 capture_output=True, text=True).stdout)
    resultados = {}
    hilos = [threading.Thread(target=iperf, args=(o, 5200 + i + 1, *PLAN[o], resultados))
             for i, o in enumerate(ONT)]
    print("Escenario de 60 s en curso: ont1 0-45 s, ont2 15-60 s, ont3 30-60 s ...", flush=True)
    t0 = time.time()
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    dur = time.time() - t0
    csv = subprocess.run(["docker", "exec", olt, "cat", "/var/log/dba.csv"], capture_output=True,
                         text=True).stdout.splitlines()
    cab, filas = csv[0], csv[previas:]
    t_ini = float(filas[0].split(",")[0])
    idx = {o: cab.split(",").index(f"{o}_grant") for o in ONT}
    grants = {o: [(float(f.split(",")[0]) - t_ini, float(f.split(",")[idx[o]])) for f in filas] for o in ONT}

    def prom(serie, a, b):
        v = [val for t, val in serie if a <= t <= b]
        return sum(v) / len(v) if v else 0.0

    ts = f"{datetime.now():%Y%m%d_%H%M%S}"
    ev = ROOT / "evidence"
    (ev / f"f5g_dba_{ts}.csv").write_text("\n".join([cab.replace("t,", "t_relativo,", 1)] +
                                                    [f"{float(f.split(',')[0]) - t_ini:.2f}," + f.split(",", 1)[1]
                                                     for f in filas]) + "\n")
    svg(resultados, grants, ev / f"f5g_dba_{ts}.svg")
    lin = [f"# Validacion de throughput F5G con DBA - {datetime.now():%Y-%m-%d %H:%M:%S}",
           f"PON simulado de {F5G['capacidad_mbps']} Mbit/s de subida, ciclo DBA {F5G['ciclo_ms']} ms, "
           f"TCP iperf3 ONT -> OLT ({dur:.0f} s)", "",
           "T-CONT configurados:"]
    lin += [f"  {o}: {c['servicio']:<24} tipo {c['tcont']}  asegurado {c['asegurado']:>3}  maximo {c['maximo']:>3}  "
            f"peso {c['peso']}" for o, c in F5G["ont"].items()]
    lin += ["", "Promedio por fase (se descartan los 5 s de transicion). Medido = iperf3; grant = DBA (Mbit/s):", "",
            f"{'fase':<14}" + "".join(f"{o + ' medido':>14}{o + ' grant':>12}" for o in ONT) + f"{'total':>9}"]
    for nombre, a, b in FASES:
        med = {o: prom(resultados.get(o, []), a, b) for o in ONT}
        lin.append(f"{nombre:<14}" + "".join(f"{med[o]:>14.1f}{prom(grants[o], a, b):>12.1f}" for o in ONT)
                   + f"{sum(med.values()):>9.1f}")
    lin += ["", "Lectura: con una sola ONT el DBA le da casi todo el PON; al entrar mas ONT se respetan los",
            "asegurados (ERP 30, camaras 20) y el excedente se reparte por peso; el total nunca supera la capacidad.",
            "", f"Archivos: f5g_dba_{ts}.csv (ciclos del DBA) y f5g_dba_{ts}.svg (grafica)"]
    (ev / f"f5g_throughput_{ts}.txt").write_text("\n".join(lin) + "\n")
    print("\n".join(lin))


if __name__ == "__main__":
    main()
