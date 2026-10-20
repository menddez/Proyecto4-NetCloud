#!/bin/bash
# Demostracion SDN/IBN + SRv6 (ejecutar en la GNS3 VM con el controlador corriendo).
#  1. Crea la intencion "ot-produccion": VXLAN leaf2<->leaf4 con RTT <= 10 ms.
#  2. Captura en el spine elegido el VXLAN (VNI 10020) encapsulado en SRv6/SRH.
#  3. Apaga los enlaces de fabric de ese spine y mide cuanto tarda el controlador
#     en reprogramar la ruta por el otro spine, y cuantos pings host2->host4 se pierden.
#  4. Restaura el spine. Todo queda en evidence/ibn_<fecha>.txt
API=localhost:8181
EV=~/netcloud-secure/evidence/ibn_$(date +%Y%m%d_%H%M%S).txt
cid(){ docker ps --format "{{.Names}}" | grep "\.$1\."; }
spine_of(){ curl -s $API/api/intents | python3 -c "import json,sys;print(json.load(sys.stdin).get('ot-produccion',{}).get('spine'))"; }

exec > >(tee "$EV") 2>&1
echo "# Prueba SDN/IBN + SRv6 - $(date '+%Y-%m-%d %H:%M:%S')"
curl -s -X DELETE $API/api/intents/ot-produccion >/dev/null
echo; echo "===== POST /api/intents ====="
curl -s -X POST $API/api/intents -d '{"name":"ot-produccion","src":"leaf2","dst":"leaf4","max_rtt_ms":10}'
SP=$(spine_of); OTRO=$([ "$SP" = spine1 ] && echo spine2 || echo spine1)
echo; echo "===== leaf2# ip rule / ip route show table 100 ====="
docker exec $(cid leaf2) sh -c "ip rule | grep 'lookup 100'; ip route show table 100"

echo; echo "===== $SP eth1 (hacia leaf2): tcpdump durante ping host2 -> host4 ====="
docker exec $(cid $SP) timeout 6 tcpdump -nvi eth1 -c 2 ip6 proto 43 2>&1 &
docker exec $(cid $OTRO) sh -c "timeout 6 tcpdump -ni eth1 -c 50 udp port 4789 2>&1 | tail -3" > /tmp/otro.txt &
sleep 1; docker exec $(cid host2) ping -c4 -i 0.3 10.20.0.14 | tail -2; wait
echo; echo "===== $OTRO eth1, mismo intervalo (no debe ver el VXLAN de la intencion) ====="; cat /tmp/otro.txt

echo; echo "===== FALLA: apagando enlaces de fabric de $SP ====="
docker exec $(cid host2) sh -c "rm -f /tmp/falla.out; ping -i 0.05 -c 1200 -W1 10.20.0.14 > /tmp/falla.out 2>&1 &"
sleep 2
T0=$(date +%s.%N)
for i in 0 1 2 3; do docker exec $(cid $SP) ip link set eth$i down; done
echo "$(date +%T) $SP aislado"
for i in $(seq 120); do [ "$(spine_of)" = "$OTRO" ] && break; sleep 0.5; done
echo "$(date +%T) controlador reprogramo la intencion via $(spine_of) en $(python3 -c "import time;print(round(time.time()-$T0,1))") s"
for i in $(seq 120); do docker exec $(cid host2) grep -q transmitted /tmp/falla.out && break; sleep 1; done
echo; echo "===== host2: ping -i 0.05 a host4 durante la falla (1200 paquetes, ~60 s) ====="
docker exec $(cid host2) tail -2 /tmp/falla.out
for i in 0 1 2 3; do docker exec $(cid $SP) ip link set eth$i up; done
echo "$(date +%T) $SP restaurado"
echo; echo "===== GET /api/intents ====="; curl -s $API/api/intents
echo; echo "===== evidence/controller.log (ultimas lineas) ====="; tail -8 ~/netcloud-secure/evidence/controller.log
echo; echo "Evidencia: $EV"
