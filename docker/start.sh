#!/bin/sh
# Asigna IP de gestion segun el hostname (nombre del nodo en GNS3), levanta sshd y FRR.
# Compartido por todas las imagenes del laboratorio (gsm-frr, gsm-5gc, gsm-ran, gsm-vnf).
H=$(hostname | tr 'A-Z' 'a-z')
ROLE=frr
case "$H" in
  spine1) IP=192.168.122.11 ;;
  spine2) IP=192.168.122.12 ;;
  leaf1)  IP=192.168.122.21 ;;
  leaf2)  IP=192.168.122.22 ;;
  leaf3)  IP=192.168.122.23 ;;
  leaf4)  IP=192.168.122.24 ;;
  host1)  IP=192.168.122.31; ROLE=host ;;
  host2)  IP=192.168.122.32; ROLE=host ;;
  host3)  IP=192.168.122.33; ROLE=host ;;
  host4)  IP=192.168.122.34; ROLE=host ;;
  # Entrega 2: 5G, NFV y F5G
  core5g) IP=192.168.122.41; ROLE=host ;;
  gnb)    IP=192.168.122.42; ROLE=host ;;
  ue)     IP=192.168.122.43; ROLE=host ;;
  fw1)    IP=192.168.122.51; ROLE=host ;;
  fw2)    IP=192.168.122.52; ROLE=host ;;
  lb)     IP=192.168.122.53; ROLE=host ;;
  srv1)   IP=192.168.122.54; ROLE=host ;;
  srv2)   IP=192.168.122.55; ROLE=host ;;
  olt)    IP=192.168.122.61; ROLE=host ;;
  ont1)   IP=192.168.122.62; ROLE=host ;;
  ont2)   IP=192.168.122.63; ROLE=host ;;
  ont3)   IP=192.168.122.64; ROLE=host ;;
  # Entrega 3: Zero Trust
  dbsrv)   IP=192.168.122.71; ROLE=host ;;
  pc-corp) IP=192.168.122.72; ROLE=host ;;
  *) echo "hostname desconocido: $H (renombra el nodo en GNS3)"; IP=""; ROLE=host ;;
esac
# Levantar todas las interfaces ethX
for i in /sys/class/net/eth*; do ip link set "$(basename "$i")" up; done
# La interfaz de gestion es la de mayor numero
MGMT=$(ls /sys/class/net | grep '^eth' | sort -V | tail -1)
[ -n "$IP" ] && ip addr add "$IP/24" dev "$MGMT"
mkdir -p /run/sshd
ssh-keygen -A >/dev/null 2>&1
/usr/sbin/sshd
if [ "$ROLE" = "frr" ]; then exec /usr/lib/frr/docker-start; else exec tail -f /dev/null; fi
