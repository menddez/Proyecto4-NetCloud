# Entrega 3 – Zero Trust, telemetría gRPC, SIEM y pruebas de ataque: diseño

## Intención
Cerrar el proyecto añadiendo la capa de seguridad y observabilidad sobre el laboratorio de las Entregas 1 y 2,
y producir las evidencias que pide el PDF: bitácora de pruebas de seguridad, tableros de telemetría en tiempo real
e informe técnico final en APA 7 (Word). El estudiante solo toma capturas al final; todo se despliega y prueba con
scripts, igual que en las entregas anteriores.

## Alcance
**Incluye** (actividades Entrega 3 + pruebas de las secciones 6 y 7 que faltaban + rúbrica de seguridad/telemetría):
- **Microsegmentación Zero Trust** por identidad (tags) en el segmento de servicios OT (VNI 10050), con firewall
  distribuido (nftables por host) rendido desde una política central y aplicado por Netmiko (plano SDN).
  Default-deny este-oeste; solo los flujos autorizados rol→rol.
- **Prueba de port scanning (PDF §6):** un equipo corporativo comprometido (`pc-corp`) no puede escanear los puertos
  del servidor de base de datos crítico (`dbsrv`); desde el servidor de aplicación autorizado sí se alcanza el puerto DB.
- **Prueba de movimiento lateral / exfiltración (PDF §7):** `pc-corp` no puede saltar a los servidores de aplicación
  ni extraer datos del DB; los intentos se bloquean y se registran.
- **Telemetría en streaming + Prometheus + Grafana:** exportadores stdlib en los nodos (interfaz, contadores nft,
  sesiones 5G, DBA), Prometheus y Grafana como contenedores en la GNS3 VM, tableros provisionados.
- **SIEM gRPC:** pipeline de eventos de seguridad en streaming por gRPC (plano de gestión). Correlaciona port scan y
  DDoS, levanta alertas y dispara mitigación automática.
- **DDoS en el plano 5G (PDF §7):** terminales IoT falsificados inundan el núcleo con registros/señalización bogus;
  el SIEM detecta el flujo y bloquea las identidades infractoras preservando a los robots legítimos (latencia < 10 ms).
- **Informe técnico APA 7 (.docx)** cubriendo las tres entregas: arquitectura, análisis matemático de latencia,
  bitácoras de automatización y de seguridad.
**No incluye:** nada nuevo; cierra el proyecto.

## Restricciones
- Dentro del proyecto GNS3 `netcloud`; nodos Docker en la GNS3 VM (8 GB/4 vCPU). Reusa automatización existente.
- Las imágenes de los nodos (Alpine 3.20 / Debian 9-11) no llevan grpcio con facilidad → **gRPC solo en el plano de
  gestión** (venv de la VM, Python 3 con pip e internet). Los nodos exportan métricas con la librería estándar.
- Prometheus y Grafana corren como contenedores **en la GNS3 VM** (infraestructura de analítica, no del plano de datos),
  accesibles desde Windows en `http://192.168.56.102:3000` (Grafana) y `:9090` (Prometheus).

## Arquitectura (decisiones del diseñador)
### Nodos nuevos (segmento de servicios OT, VNI 10050)
| Nodo | IP | Imagen | Rol | Puerto GNS3 |
|---|---|---|---|---|
| `dbsrv` | 10.50.0.20 | gsm-vnf | Base de datos crítica (listeners 5432/3306/6379/27017) | SW-SVC:0, MGMT-SW2:12 |
| `pc-corp` | 10.50.0.30 | gsm-vnf | Estación corporativa comprometida (escáner + generador) | SW-SVC:6, MGMT-SW2:13 |

Solo se agregan nodos y enlaces a puertos libres de switches existentes (sin cambiar adaptadores de nodos actuales).

### Microsegmentación (tag-based, política en topology.yaml → nftables por host)
Roles por IP de origen: `db` (dbsrv), `app` (srv1,srv2), `lb` (lb), `corp` (pc-corp), más las subredes 5G `iot`/`admin`.
Matriz de permitidos (todo lo demás este-oeste = drop + log, contado para el SIEM):
- `app` → `db` : tcp 5432 (único acceso al DB)
- `lb`  → `app`: tcp 8080
- `iot` → `lb` : tcp 80 (telemetría publicada; ya existía en el perímetro)
- `corp`→ `lb` : tcp 80 (usuario corporativo normal)
- `corp`→ `db`/`app` puertos: **denegado** (port scan y movimiento lateral bloqueados)

`microseg.py` renderiza y aplica las reglas (Netmiko). `dbsrv` y `pc-corp` reciben plantillas `seg/*.nft.j2`.

### Telemetría
- `telemetria/exporter.py` (stdlib): se despliega en fw activo, core5g, olt, leafs y dbsrv; expone `:9100/metrics`
  (texto Prometheus) y `:9101/events` (cola de eventos de seguridad para el shipper gRPC).
- `prometheus` + `grafana` (contenedores en la VM), con `scripts/monitoreo.sh` para levantarlos; scrape cada 2 s;
  datasource y dashboards provisionados por archivo.
### SIEM gRPC (plano de gestión, venv de la VM)
- `telemetria/siem.proto` → `StreamEvents` (bidi). `siem_server.py` (gRPC server) recibe eventos y correlaciona.
- `siem_shipper.py`: un stream por nodo vigilado; lee `/events` del exportador y **empuja los eventos por gRPC** en
  tiempo real al SIEM. (Dial-out en el plano de gestión; se documenta y se contrasta con SNMP para la pregunta 10.5.)
- Reglas de correlación: **port scan** = ≥N puertos denegados distintos desde un origen en ventana T; **DDoS 5G** =
  tasa de registros/señalización bogus sobre umbral. Al disparar: mitigación automática (nft blocklist del origen en
  dbsrv/fw o en core5g) y alerta en `evidence/siem_*.log`.

### DDoS en el plano 5G
`prueba_ddos5g.sh`: desde `ue` se lanzan en bucle UEs bogus (IMSIs no provisionados → tormenta de autenticación en el
AMF) y una inundación UDP hacia el AMF/UPF (NGAP 38412 / GTP-U 2152) en 10.30.0.10, mientras un robot legítimo mantiene
su sesión. El SIEM detecta el pico (métricas del exportador de core5g por el stream) y aplica nft en core5g para
bloquear el origen bogus; se comprueba que el robot conserva su sesión y latencia < 10 ms.

## Evidencias que se generarán
- `zerotrust_portscan_*.txt`: escaneo de `pc-corp`→`dbsrv` bloqueado; `app`→`dbsrv`:5432 permitido; contadores nft + alerta SIEM.
- `zerotrust_lateral_*.txt`: movimiento lateral/exfiltración bloqueados.
- `siem_*.log`: eventos en streaming y mitigaciones.
- `ddos5g_*.txt`: flood detectado, identidades bloqueadas, sesión y latencia del robot legítimo intactas.
- `grafana_*` y `prometheus_*`: capturas de los tableros (las toma el estudiante).
- **Informe APA 7 (.docx)** en `informe/` cubriendo las tres entregas.

## Queda a criterio del constructor
Umbrales y ventanas de detección, puertos exactos del DB, forma de los tableros, redacción del informe.
