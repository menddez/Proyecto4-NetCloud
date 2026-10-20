#!/bin/sh
# Asigna IP de gestion segun el hostname (nombre del nodo en GNS3), levanta sshd y FRR.
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
  *) echo "hostname desconocido: $H (renombra el nodo en GNS3)"; IP=""; ROLE=host ;;
esac
# Levantar todas las interfaces ethX
for i in /sys/class/net/eth*; do ip link set "$(basename "$i")" up; done
# La interfaz de gestion es la de mayor numero
MGMT=$(ls /sys/class/net | grep '^eth' | sort -V | tail -1)
[ -n "$IP" ] && ip addr add "$IP/24" dev "$MGMT"
ssh-keygen -A >/dev/null 2>&1
/usr/sbin/sshd
if [ "$ROLE" = "frr" ]; then exec /usr/lib/frr/docker-start; else exec tail -f /dev/null; fi
