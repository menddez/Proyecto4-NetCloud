#!/usr/bin/env python3
"""Entrega 1 - Despliegue masivo de configuraciones (Netmiko + Jinja2).

Uso:
  python3 deploy.py --dry-run          # solo genera las configs en ../build/
  python3 deploy.py                    # despliega en todos los nodos
  python3 deploy.py --nodes leaf1 leaf3
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import ROOT, PLAN, build_contexts, connect, jinja_env, load_topology


def push_text(conn, text, path):
    """Escribe texto en el nodo en trozos base64 (evita el limite de linea del TTY)."""
    b64 = base64.b64encode(text.encode()).decode()
    tmp = f"{path}.b64"
    conn.send_command(f"rm -f {tmp}")
    for i in range(0, len(b64), 400):
        conn.send_command(f"echo -n '{b64[i:i+400]}' >> {tmp}")
    conn.send_command(f"base64 -d {tmp} > {path} && rm -f {tmp}")


def render_all(topo):
    env, ctxs, out = jinja_env(), build_contexts(topo), {}
    for name, ctx in ctxs.items():
        out[name] = [(env.get_template(t).render(**ctx), remote, cmd) for t, remote, cmd in PLAN[ctx["role"]]]
    return out


def deploy_node(topo, name, steps):
    log = [f"[{name}]"]
    conn = connect(topo, name)
    for text, remote, cmd in steps:
        push_text(conn, text, remote)
        res = conn.send_command(cmd, read_timeout=150).strip()
        log.append(f"  $ {cmd}" + (f"\n{res}" if res else "  (ok)"))
    conn.disconnect()
    return "\n".join(log)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--nodes", nargs="*")
    args = ap.parse_args()

    topo = load_topology()
    rendered = render_all(topo)
    if args.nodes:
        rendered = {n: s for n, s in rendered.items() if n in args.nodes}

    if args.dry_run:
        for name, steps in rendered.items():
            d = ROOT / "build" / name
            d.mkdir(parents=True, exist_ok=True)
            for text, remote, _ in steps:
                (d / remote.split("/")[-1]).write_text(text)
        print(f"Configuraciones generadas en {ROOT / 'build'}")
        return

    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(deploy_node, topo, n, s): n for n, s in rendered.items()}
        for f in as_completed(futs):
            try:
                print(f.result())
            except Exception as e:
                print(f"[{futs[f]}] ERROR: {e}")


if __name__ == "__main__":
    main()
