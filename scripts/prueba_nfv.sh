#!/bin/bash
# Escenario de falla del PDF (seccion 7): "interrupcion forzada del contenedor que aloja el cortafuegos virtual
# perimetral; el orquestador NFV debe re-instanciar la funcion en un nodo de respaldo en menos de 5 s".
#  1. Un robot 5G envia telemetria (ping cada 50 ms) a srv1 a traves de la cadena UPF -> vFW -> servicios.
#  2. Se mata a la fuerza (docker kill) el contenedor del firewall ACTIVO.
#  3. Se mide cuanto tarda el respaldo en tomar el trafico y la re-instanciacion del contenedor caido.
# Requiere el orquestador corriendo (scripts/orquestador.sh). Evidencia en evidence/nfv_failover_<fecha>.txt
cd ~/netcloud-secure/automation && . venv/bin/activate
EV=~/netcloud-secure/evidence/nfv_failover_$(date +%Y%m%d_%H%M%S).txt
cid(){ docker ps -a --format "{{.Names}}" | grep "\.$1\."; }
activo(){ python3 -c "import json;print(json.load(open('nfv_estado.json'))['activo'])"; }

exec > >(tee "$EV") 2>&1
echo "# Prueba de falla NFV (firewall virtual) - $(date '+%Y-%m-%d %H:%M:%S')"
FW=$(activo); RESP=$([ "$FW" = fw1 ] && echo fw2 || echo fw1)
echo; echo "===== Estado inicial: $FW ACTIVO, $RESP RESPALDO ====="
cat nfv_estado.json

UE=$(cid ue)
docker exec $UE sh -c "rm -f /tmp/nfv.out; ping -I uesimtun0 -i 0.05 -c 600 -W1 10.50.0.11 > /tmp/nfv.out 2>&1 &"
sleep 3
N0=$(wc -l < ../evidence/nfv_eventos.log)
echo; echo "===== FALLA INTENCIONAL: docker kill del contenedor de $FW ($(date +%T.%3N)) ====="
docker kill "$(cid $FW)" >/dev/null
for i in $(seq 100); do [ "$(activo)" = "$RESP" ] && break; sleep 0.1; done
for i in $(seq 120); do tail -n +$((N0+1)) ../evidence/nfv_eventos.log | grep -q "RE-INSTANCIA\|ERROR re-instanciando" && break; sleep 1; done
for i in $(seq 60); do docker exec $UE grep -q transmitted /tmp/nfv.out && break; sleep 1; done

echo; echo "===== Eventos del orquestador ====="
tail -n +$((N0+1)) ../evidence/nfv_eventos.log
echo; echo "===== Robot (uesimtun0): ping cada 50 ms a srv1 durante la falla ====="
docker exec $UE tail -2 /tmp/nfv.out
read TX RX < <(docker exec $UE grep transmitted /tmp/nfv.out | awk '{print $1, $4}')
echo; echo "===== Trafico despues de la conmutacion ====="
for i in 1 2; do docker exec $UE curl -s -m 3 --interface uesimtun0 http://10.50.0.100/telemetria; echo; done
docker exec "$(cid $RESP)" nft list counter inet sfc iot_a_servicios | grep packets
echo; echo "===== RESULTADO ====="
CONM=$(tail -n +$((N0+1)) ../evidence/nfv_eventos.log | grep -o "[0-9.]* s despues" | head -1)
echo "Conmutacion al respaldo: ${CONM:-?} del primer sondeo fallido (objetivo < 5 s)"
echo "Interrupcion vista por el robot: $((TX-RX)) de $TX pings perdidos = $(python3 -c "print(round(($TX-$RX)*0.05,2))") s"
echo "$FW fue re-instanciado por la API de GNS3 y quedo como RESPALDO; $RESP es el nuevo ACTIVO"
echo; python3 orquestador_nfv.py diagrama | tail -8
echo; echo "Evidencia: $EV"
