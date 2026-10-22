#!/bin/bash
# Arranque dentro de la GNS3 VM: red de gestion, comprobacion de nodos y despliegue completo (Entregas 1 y 2)
# 1) Red de gestion: quitar duplicado en gns3br0, asegurar la IP en virbr0 y olvidar MACs viejas
sudo ip addr del 192.168.122.1/24 dev gns3br0 2>/dev/null
ip -br a show virbr0 | grep -q "192.168.122.1/24" || sudo ip addr add 192.168.122.1/24 dev virbr0
sudo ip neigh flush dev virbr0
# DNS estable para descargas (el stub de systemd-resolved es intermitente)
grep -q 8.8.8.8 /etc/resolv.conf 2>/dev/null || sudo bash -c 'rm -f /etc/resolv.conf; printf "nameserver 8.8.8.8
nameserver 1.1.1.1
" > /etc/resolv.conf'
# 2) SCTP para la interfaz N2 (gNodeB <-> AMF)
sudo modprobe sctp
# 3) Comprobar los nodos (fabric, hosts, 5G, VNFs y F5G)
FALLAS=0
for ip in 11 12 21 22 23 24 31 32 33 34 41 42 43 51 52 53 54 55 61 62 63 64 71 72; do
  if ping -c2 -W1 192.168.122.$ip >/dev/null; then echo "$ip OK"; else echo "$ip FALLA"; FALLAS=1; fi
done
if [ $FALLAS -eq 1 ]; then echo "Hay nodos sin respuesta: revisa la ruta con: ip route get 192.168.122.21"; exit 1; fi
# 4) Desplegar todo: fabric primero, luego nucleo 5G, gNodeB y UEs
cd ~/netcloud-secure/automation && . venv/bin/activate && python3 deploy.py
