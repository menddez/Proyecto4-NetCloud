#!/bin/bash
# Prueba Zero Trust / microsegmentacion (PDF secciones 6 y 7): un equipo corporativo comprometido (pc-corp)
# NO puede escanear los puertos del servidor de base de datos critico (dbsrv) ni moverse lateralmente a los
# servidores de aplicacion; el servidor de aplicacion autorizado SI alcanza el puerto del DB. El SIEM detecta
# el escaneo por streaming gRPC y bloquea al atacante. Evidencia en evidence/zerotrust_*.txt
cd ~/netcloud-secure/automation && . venv/bin/activate
EV=~/netcloud-secure/evidence/zerotrust_$(date +%Y%m%d_%H%M%S).txt
cid(){ docker ps --format "{{.Names}}" | grep "\.$1\."; }
DB=10.50.0.20; PUERTOS="22 80 443 3306 5432 6379 8080 9100 27017"

# Asegura SIEM arriba
curl -s -m 2 http://127.0.0.1:9090/-/ready >/dev/null 2>&1 || true
pgrep -f "siem.py server" >/dev/null || sh ~/netcloud-secure/scripts/siem.sh >/dev/null 2>&1
sleep 2
N0=$(wc -l < ~/netcloud-secure/evidence/siem.log 2>/dev/null || echo 0)

exec > >(tee "$EV") 2>&1
echo "# Prueba Zero Trust / microsegmentacion - $(date '+%Y-%m-%d %H:%M:%S')"
echo "Segmento de servicios OT 10.50.0.0/24 con firewall distribuido (nft tabla zt). Matriz: app->db:5432."
echo
echo "===== 1) Acceso AUTORIZADO: srv1 (app, 10.50.0.11) -> dbsrv:5432 ====="
docker exec -i $(cid srv1) python3 - "$DB" <<'PY'
import socket,sys
s=socket.socket(); s.settimeout(2)
try:
    s.connect((sys.argv[1],5432)); print("  5432/tcp  CONECTADO:", s.recv(80).decode().strip()[:60]);
except Exception as e: print("  5432/tcp  ERROR:",e)
PY

echo
echo "===== 2) ATAQUE: port scan desde pc-corp (comprometido, 10.50.0.30) -> dbsrv ====="
echo "Puertos escaneados: $PUERTOS"
docker exec -i $(cid pc-corp) python3 - "$DB" $PUERTOS <<'PY'
import socket,sys
ip=sys.argv[1]; abiertos=[]
for p in map(int,sys.argv[2:]):
    s=socket.socket(); s.settimeout(1.5)
    try:
        s.connect((ip,p)); abiertos.append(p); print(f"  {p}/tcp  ABIERTO")
    except Exception:
        print(f"  {p}/tcp  filtrado (bloqueado)")
    finally: s.close()
print(f"RESULTADO escaneo: {len(abiertos)} puertos abiertos de {len(sys.argv)-2} (microsegmentacion {'FALLO' if abiertos else 'OK: todo bloqueado'})")
PY

echo
echo "===== 3) ATAQUE: movimiento lateral pc-corp -> srv1:8080 (aplicacion) ====="
docker exec -i $(cid pc-corp) python3 - <<'PY'
import socket
s=socket.socket(); s.settimeout(2)
try: s.connect(("10.50.0.11",8080)); print("  8080/tcp  CONECTADO (microsegmentacion FALLO)")
except Exception as e: print("  8080/tcp  bloqueado (OK):",type(e).__name__)
PY

echo
echo "===== 4) Contadores de la microsegmentacion en dbsrv (intentos bloqueados por origen) ====="
docker exec $(cid dbsrv) nft list counters table inet zt

echo
echo "===== 5) Deteccion y mitigacion automatica del SIEM (telemetria gRPC) ====="
for i in $(seq 25); do tail -n +$((N0+1)) ~/netcloud-secure/evidence/siem.log 2>/dev/null | grep -q "MITIGACION.*dbsrv" && break; sleep 1; done
tail -n +$((N0+1)) ~/netcloud-secure/evidence/siem.log 2>/dev/null | grep -E "ALERTA|MITIGACION" || echo "  (sin alerta todavia; revisa que el SIEM este corriendo)"
echo
echo "pc-corp en el conjunto bloqueados de dbsrv tras la mitigacion:"
docker exec $(cid dbsrv) nft list set inet zt bloqueados

echo
echo "===== 6) Mitigacion quirurgica: el usuario corporativo legitimo -> balanceador (10.50.0.100:80) sigue OK ====="
docker exec -i $(cid pc-corp) python3 - <<'PY'
import socket
s=socket.socket(); s.settimeout(3)
try:
    s.connect(("10.50.0.100",80)); s.send(b"GET /telemetria HTTP/1.0\r\n\r\n")
    print("  lb:80  CONECTADO (el bloqueo es solo hacia el DB, no afecta el trafico autorizado)")
except Exception as e: print("  lb:80  ERROR:",type(e).__name__,e)
PY
echo
echo "Evidencia: $EV"
