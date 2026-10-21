# Entrega 2 – Núcleo 5G privado, F5G y NFV: diseño

## Intención
Integrar sobre el fabric EVPN/VXLAN de la Entrega 1 una red móvil privada 5G para IoT industrial, una red
óptica de acceso F5G con DBA y funciones de red virtualizadas (firewall + balanceador) encadenadas, y producir
las evidencias que pide el PDF: logs de registro de abonados 5G, diagrama de estado de VNFs activas y
validación de throughput en la red óptica. El estudiante quiere mínima intervención: todo se despliega y
prueba con scripts; él solo toma capturas al final.

## Alcance
**Incluye** (actividades de la Entrega 2 + lo que la rúbrica califica de estas piezas):
- Open5GS 2.7.2 (5GC completo) + MongoDB (UDR) + gNodeB y UEs con UERANSIM 3.2.6.
- Registro de UEs y sesiones PDU en dos DNN con QoS distinta: `iot` (telemetría robótica, 5QI prioritario)
  y `admin` (5QI 9, best effort). Prueba de latencia extremo a extremo < 10 ms (sección 6 del PDF).
- VNFs: firewall nftables (fw1 activo, fw2 respaldo) y balanceador HAProxy frente a dos servidores
  industriales. Service Function Chaining: UE → UPF (N6) → vFW → vLB → servidor.
- Orquestador NFV (Python) que vigila las VNFs, activa el respaldo en < 5 s cuando el contenedor del firewall
  se interrumpe a la fuerza (sección 7) y re-instancia el contenedor caído vía la API de GNS3.
- Red óptica F5G simulada: OLT + splitter (hub) + 3 ONT con T-CONT distintos y un DBA por reporte de estado.
**No incluye** (Entrega 3): DDoS al plano 5G, Zero Trust/microsegmentación, telemetría gRPC.

## Restricciones
- Todo dentro del proyecto GNS3 `netcloud` existente, nodos Docker en la GNS3 VM (8 GB RAM, 4 vCPU,
  sin KVM anidado). Hyper-V apagado en Windows.
- No existe emulador libre de GPON: la capa física óptica se **simula** (se declara en el informe).
  La capacidad del PON se escala a 100 Mbit/s de subida (GPON real: 1.244 Gbit/s).
- Reusar la automatización existente (topology.yaml + Jinja2 + Netmiko + deploy/verify).

## Arquitectura (decisiones del diseñador)
| Segmento | VLAN/VNI | Subred | Quién |
|---|---|---|---|
| Transporte 5G N2/N3 | 30 / 10030 | 10.30.0.0/24 | core5g .10 (leaf1), gnb .20 (leaf3): L2 extendido DC1↔Planta por EVPN |
| N6 (salida UPF) | 40 / 10040 | 10.40.0.0/24 | core5g .10, VIP fw .1, fw1 .2, fw2 .3 (switch SW-N6 → leaf2) |
| Servicios OT | 50 / 10050 | 10.50.0.0/24 | VIP fw .1, fw1 .2, fw2 .3, lb .4, VIP lb .100, srv1 .11, srv2 .12 (SW-SVC → leaf2) |
| F5G corporativo | 60 / 10060 | 10.60.0.0/24 | olt uplink .1 (leaf4) |
| PON (ODN) | — | 10.61.0.0/24 | olt .1, ont1-3 .11-.13 vía HUB-ODN (splitter pasivo) |
| Radio (simulada) | — | 10.99.0.0/24 | gnb .1 ↔ ue .2 (enlace directo) |
| UE pools | — | 10.45.0.0/16 (`iot`), 10.46.0.0/16 (`admin`) | ogstun/ogstun2 en el UPF |
| Base de datos | — | 10.33.0.0/30 | core5g .1 ↔ mongo .2 (enlace directo) |

- Leafs ganan puertos de acceso (leaf1 +1, leaf2 +2, leaf3 +1, leaf4 +1); la gestión se mueve a la interfaz
  de mayor número (convención de `start.sh`). Gestión de nodos nuevos: 192.168.122.41-64.
- Imágenes: `gsm-5gc` (gradiant/open5gs + sshd), `gsm-ran` (gradiant/ueransim + sshd),
  `gsm-vnf` (Alpine + nftables + HAProxy + iperf3 + sshd), `mongo:6.0` tal cual. Todas comparten `start.sh`.
- Open5GS todo-en-uno en un contenedor (SBI en 127.0.0.x, NGAP/GTP-U en 10.30.0.10). PLMN 001/01, TAC 1, SST 1.
- Abonados se dan de alta con un script Python (pymongo) con el esquema de Open5GS.
- Firewall: política por defecto *drop*; permite `iot` → VIP lb tcp/80 e ICMP, bloquea `admin` → OT y lo cuenta.
- HA del firewall: respaldo caliente (reglas cargadas, sin VIPs). El orquestador sondea fw1 cada 0.3 s; tras
  2 fallos mueve las VIPs a fw2 con ARP gratuito, y re-instancia fw1 como nuevo respaldo.
- DBA: cada ONT moldea su subida con HTB (su T-CONT) y reporta cola/uso por UDP a la OLT cada 250 ms; la OLT
  calcula *grants* (asegurado primero, excedente proporcional al peso entre ONT con cola) y los envía por UDP.
  T-CONT: ont1 oficinas tipo 4 best effort; ont2 ERP tipo 2 asegurado 30 Mbit/s; ont3 cámaras tipo 3
  asegurado 20 + no asegurado hasta 60.

## Evidencias que se generarán
- `5g_registro_*.txt`: logs AMF/SMF/UPF de registro y sesión PDU de cada UE, con su QoS.
- `5g_latencia_*.txt`: RTT UE → servidor a través de la cadena (< 10 ms).
- `nfv_estado_*.md/svg`: diagrama de estado de VNFs activas (generado por el orquestador) + `nfv_failover_*.txt`.
- `sfc_*.txt`: contadores nftables y reparto del balanceador.
- `f5g_dba_*.csv/svg` y `f5g_throughput_*.txt`: grants del DBA y iperf3 por ONT en escenarios de contención.

## Queda a criterio del constructor
Valores exactos de 5QI/ARP, nombres de logs, forma del gráfico, tiempos de sondeo dentro de los límites.
