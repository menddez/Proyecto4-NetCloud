#!/bin/sh
# Resumen rapido del 5G: sesiones PDU de cada UE (interfaz e IP) y estado del orquestador NFV
U=$(docker ps --format "{{.Names}}" | grep "\.ue\.")
for f in $(docker exec $U sh -c "ls /var/log/ue-*.log"); do
  printf "  %-22s %s\n" "$(basename $f .log)" "$(docker exec $U grep -o 'TUN interface\[.*\]' $f | tail -1)"
done
echo "  NFV: $(tr -d '\n ' < ~/netcloud-secure/automation/nfv_estado.json 2>/dev/null)"
