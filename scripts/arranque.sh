#!/bin/bash
# 1) Red de gestion: quitar duplicado en gns3br0 y asegurar la IP en virbr0
sudo ip addr del 192.168.122.1/24 dev gns3br0 2>/dev/null
ip -br a show virbr0 | grep -q "192.168.122.1/24" || sudo ip addr add 192.168.122.1/24 dev virbr0
# 2) Comprobar los 10 nodos
FALLAS=0
for ip in 11 12 21 22 23 24 31 32 33 34; do
  if ping -c1 -W1 192.168.122.$ip >/dev/null; then echo "$ip OK"; else echo "$ip FALLA"; FALLAS=1; fi
done
if [ $FALLAS -eq 1 ]; then echo "Hay nodos sin respuesta: revisa la ruta con: ip route get 192.168.122.21"; exit 1; fi
# 3) Reconfigurar el tejido
cd ~/netcloud-secure/automation && . venv/bin/activate && python3 deploy.py
