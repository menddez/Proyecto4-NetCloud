"""Prueba de los comandos que el orquestador NFV envia al firewall (no requiere laboratorio).
Uso: python3 test_nfv.py"""
import shutil
import subprocess

from orquestador_nfv import NFV, comandos_vip

for activar in (True, False):
    cmd = comandos_vip(activar)
    assert "&;" not in cmd, cmd                       # error real que dejaba al respaldo sin VIPs
    assert NFV["vip_outside"] in cmd and NFV["vip_inside"] in cmd, cmd
    if shutil.which("sh"):
        assert subprocess.run(["sh", "-n", "-c", cmd]).returncode == 0, f"sintaxis invalida: {cmd}"
assert "arping" in comandos_vip(True) and "arping" not in comandos_vip(False)
print("OK: comandos del orquestador NFV")
