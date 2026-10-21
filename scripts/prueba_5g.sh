#!/bin/bash
# Evidencias 5G de la Entrega 2 (ejecutar en la GNS3 VM con el laboratorio desplegado):
#   evidence/5g_registro_<fecha>.txt      registro de abonados y sesiones PDU con su QoS (logs AMF/SMF/UPF/gNB/UE)
#   evidence/5g_latencia_sfc_<fecha>.txt  latencia UE -> servidor (< 10 ms) y cadena UPF -> vFW -> vLB -> servidores
cd ~/netcloud-secure/automation && . venv/bin/activate
TS=$(date +%Y%m%d_%H%M%S)
REG=~/netcloud-secure/evidence/5g_registro_$TS.txt
LAT=~/netcloud-secure/evidence/5g_latencia_sfc_$TS.txt
cid(){ docker ps --format "{{.Names}}" | grep "\.$1\."; }
C=$(cid core5g); G=$(cid gnb); U=$(cid ue)
LOG=/opt/open5gs/var/log/open5gs
FW=$(python3 -c "import json;print(json.load(open('nfv_estado.json'))['activo'])" 2>/dev/null || echo fw1)

{
echo "# Registro de abonados 5G - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Nucleo Open5GS 2.7.2 (core5g, DC1) <- N2/N3 por EVPN VNI 10030 -> gNodeB UERANSIM (Planta)"
echo; echo "===== Abonados en la UDR (MongoDB) con la QoS de su DNN ====="
docker exec $C python3 -c "
from pymongo import MongoClient
for s in MongoClient('mongodb://10.33.0.2/').open5gs.subscribers.find({}, {'_id': 0}).sort('imsi'):
    x = s['slice'][0]['session'][0]
    print(f\"IMSI {s['imsi']}  DNN {x['name']:<5}  5QI {x['qos']['index']:<2}  ARP {x['qos']['arp']['priority_level']}  \"
          f\"AMBR {x['ambr']['downlink']['value']} Mbit/s\")"
echo; echo "===== gNodeB: establecimiento de N2 (NG Setup con el AMF) ====="
docker exec $G grep -E "SCTP association|NG Setup" /var/log/gnb.log
echo; echo "===== AMF: registro de cada UE ====="
docker exec $C grep -E "InitialUEMessage|Registration request|\[imsi-[0-9]+\]|Number of (gNBs|AMF-UEs)" $LOG/amf.log | tail -40
echo; echo "===== SMF: sesiones PDU (IMSI, DNN e IP asignada) ====="
docker exec $C grep -E "UE SUPI|Number of SMF-(UEs|Sessions)" $LOG/smf.log | tail -20
echo; echo "===== UPF: sesiones del plano de usuario ====="
docker exec $C grep -E "Number of UPF-Sessions|PFCP associated" $LOG/upf.log | tail -8
echo; echo "===== UEs (UERANSIM): registro y sesion PDU ====="
for f in $(docker exec $U sh -c "ls /var/log/ue-*.log"); do
  echo "--- $(basename $f .log)"
  docker exec $U grep -E "Initial Registration is successful|PDU Session establishment is successful|TUN interface" $f
done
echo; echo "===== nr-cli: estado de un UE ====="
docker exec $U nr-cli imsi-001010000000001 -e status
} > "$REG" 2>&1

# imsi/abonado -> interfaz tun e IP, a partir del log de cada UE
mapfile -t TUNS < <(docker exec $U sh -c 'for f in /var/log/ue-*.log; do n=$(basename $f .log); grep -o "TUN interface\[[a-z0-9]*, [0-9.]*\]" $f | tail -1 | sed "s/TUN interface\[\(.*\), \(.*\)\]/$n \1 \2/"; done')
{
echo "# Latencia 5G extremo a extremo y cadena de servicios (SFC) - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Camino: UE -> gNodeB -> GTP-U por EVPN (VNI 10030) -> UPF -> N6 (VNI 10040) -> vFW $FW -> servicios OT (VNI 10050)"
echo; echo "===== Latencia de cada UE IoT hacia srv1 (20 pings, objetivo < 10 ms) ====="
printf "%-20s %-10s %-12s %-14s %s\n" UE interfaz IP "RTT prom (ms)" veredicto
for l in "${TUNS[@]}"; do
  set -- $l
  case $3 in 10.46.*) continue ;; esac
  avg=$(docker exec $U ping -I $2 -c 20 -i 0.2 -W1 10.50.0.11 | awk -F/ '/rtt/{print $5}')
  ok=$(python3 -c "print('CUMPLE' if ${avg:-999} < 10 else 'NO CUMPLE')")
  printf "%-20s %-10s %-12s %-14s %s\n" "$1" "$2" "$3" "${avg:-sin respuesta}" "$ok"
done
IOT=$(printf "%s\n" "${TUNS[@]}" | grep " 10.45" | head -1 | awk '{print $2}')
ADM=$(printf "%s\n" "${TUNS[@]}" | grep " 10.46" | head -1 | awk '{print $2}')
echo; echo "===== SFC: 6 peticiones de telemetria de un robot al servicio publicado por el balanceador ====="
for i in 1 2 3 4 5 6; do docker exec $U curl -s -m 3 --interface $IOT http://10.50.0.100/telemetria; echo; done
echo; echo "===== Politica del firewall: la tablet administrativa (DNN admin) no puede llegar a OT ====="
docker exec $U curl -s -m 3 --interface $ADM http://10.50.0.100/ && echo "(PERMITIDO: revisar politica)" || echo "BLOQUEADO por el vFW (timeout)"
echo; echo "===== Contadores nftables del firewall activo ($FW) ====="
docker exec $(cid $FW) nft list counters
echo; echo "===== Balanceador (HAProxy): estado de los servidores y sesiones atendidas ====="
curl -s "http://192.168.122.53:8404/;csv" | awk -F, 'NR==1 || $1=="servidores_industriales" {print $1, $2, $18, "sesiones="$8}'
} > "$LAT" 2>&1

cat "$REG" | head -30; echo "..."; cat "$LAT"
echo; echo "Evidencias: $REG"; echo "            $LAT"
