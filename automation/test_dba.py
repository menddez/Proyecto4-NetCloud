"""Prueba del algoritmo DBA de la OLT (no requiere laboratorio): renderiza la plantilla y prueba asignar().
Uso: python3 test_dba.py"""
from common import build_contexts, jinja_env, load_topology

ctx = build_contexts(load_topology())["olt"]
codigo = jinja_env().get_template("f5g/olt_dba.py.j2").render(**ctx)
ns = {"__name__": "dba"}
exec(codigo, ns)
asignar, CAP = ns["asignar"], ns["CAP"]
sin = {"rate": 0.0, "backlog": 0}
lleno = lambda tasa: {"rate": tasa, "backlog": 30000}

# Solo ont1 (best effort) transmite: se lleva casi todo el PON
g = asignar({"ont1": lleno(2), "ont2": sin, "ont3": sin}, {})
assert g["ont1"] >= CAP - 2 * 2 - 0.5 and sum(g.values()) <= CAP + 0.5, g

# Las tres saturadas: asegurados respetados, ont3 limitada a su maximo, nunca se excede la capacidad
g = asignar({"ont1": lleno(30), "ont2": lleno(30), "ont3": lleno(30)}, {})
assert g["ont2"] >= 30 and g["ont3"] >= 20 and g["ont3"] <= 60, g
assert abs(sum(g.values()) - CAP) < 0.5, g
assert g["ont3"] > g["ont1"], g          # peso 2 contra peso 1

# ont2 sin trafico: no reserva su asegurado (tipo 2), queda en el piso
g = asignar({"ont1": lleno(50), "ont2": sin, "ont3": lleno(40)}, {})
assert g["ont2"] == 2.0 and g["ont3"] <= 60, g

print("OK: algoritmo DBA")
