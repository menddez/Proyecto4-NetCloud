"""Prueba de la logica de decision del controlador (no requiere laboratorio).
Uso: python3 test_controller.py"""
from controller import choose_spine, parse_rtt, sid, steer_cmds, validate_intent

PING_OK = "3 packets transmitted, 3 received, 0% packet loss\nrtt min/avg/max/mdev = 1.1/2.50/3.9/0.4 ms"
PING_KO = "3 packets transmitted, 0 received, 100% packet loss"

assert parse_rtt(PING_OK) == 2.5
assert parse_rtt(PING_KO) is None

rtts = {"spine1": 4.0, "spine2": 6.0}
assert choose_spine(rtts, [], None) == "spine1"                       # menor latencia
assert choose_spine(rtts, ["spine1"], None) == "spine2"               # exclusion
assert choose_spine(rtts, [], 5) == "spine1"                          # cumple el umbral
assert choose_spine({"spine1": None, "spine2": 6.0}, [], None) == "spine2"   # spine caido
assert choose_spine(rtts, ["spine1"], 5) is None                      # nada cumple

assert sid("spine2", "e") == "fc00:0:2::e" and sid("leaf4", "d4") == "fc00:0:14::d4"
assert "segs fc00:0:2::e,fc00:0:14::d4 dev eth1" in steer_cmds("leaf2", "leaf4", "spine2")[1]

for bad in ({"name": "x y", "src": "leaf1", "dst": "leaf2"},
            {"name": "a", "src": "leaf1", "dst": "leaf1"},
            {"name": "a", "src": "leaf1", "dst": "leaf2", "avoid": ["spine9"]},
            {"name": "a", "src": "leaf1", "dst": "leaf2", "max_rtt_ms": -1}):
    try:
        validate_intent(bad)
        raise AssertionError(f"debio rechazar {bad}")
    except ValueError:
        pass

print("OK: logica del controlador")
