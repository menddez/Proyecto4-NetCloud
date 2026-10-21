# Guía de evidencias y demostración – Entrega 2 (5G privado, F5G y NFV)

Igual que en la Entrega 1: todo desde **PowerShell normal** en tu laptop; los comandos de red corren dentro de la
GNS3 VM a través de `ssh`. Diseño completo: `docs/superpowers/specs/2026-10-21-entrega2-design.md`.

## Qué se construyó
| Pieza | Implementación | Dónde |
|---|---|---|
| Núcleo 5G privado | Open5GS 2.7.2 (AMF, SMF, UPF, NRF, SCP, AUSF, UDM, UDR, PCF, NSSF, BSF) + MongoDB | `core5g`, `mongo` (DC1, leaf1) |
| gNodeB y equipos | UERANSIM 3.2.6: 1 gNB y 4 UEs (3 IoT industriales + 1 tablet administrativa) | `gnb` (Planta, leaf3), `ue` |
| Transporte N2/N3 | L2 extendido DC1 ↔ Planta sobre EVPN/VXLAN (VNI 10030) | fabric de la Entrega 1 |
| QoS por DNN | `iot`: 5QI 80 (no-GBR baja latencia), ARP 1, 100 Mbit/s · `admin`: 5QI 9, ARP 8, 20 Mbit/s | `topology.yaml` |
| VNFs + SFC | UPF → firewall nftables (fw1 activo / fw2 respaldo) → balanceador HAProxy → srv1/srv2 | `SW-N6`, `SW-SVC` (leaf2) |
| Orquestador NFV | Vigila el firewall cada 0.3 s, conmuta al respaldo y re-instancia el caído por la API de GNS3 | `automation/orquestador_nfv.py` |
| Red óptica F5G | OLT + splitter (hub) + 3 ONT con T-CONT tipo 4/2/3 y DBA por reporte de estado (simulada, 100 Mbit/s) | `olt`, `HUB-ODN`, `ont1-3` (leaf4) |

## Resultados ya medidos (están en `evidence/`)
| Requisito del PDF | Resultado | Archivo |
|---|---|---|
| Registro de abonados 5G y sesiones de datos | 4/4 UEs registrados con sesión PDU (`10.45.0.2-4`, `10.46.0.2`) y su QoS | `5g_registro_*.txt` |
| Latencia 5G extremo a extremo < 10 ms | 2.5 – 3.1 ms UE → servidor, cruzando GTP, EVPN, vFW y vLB | `5g_latencia_sfc_*.txt` |
| Encadenamiento de servicios (SFC) | Balanceo 6/6 entre srv1/srv2; la tablet `admin` bloqueada por el vFW | mismo archivo |
| Diagrama de estado de las VNFs | Diagrama de la cadena con el rol de cada VNF | `nfv_estado_*.html` / `.md` |
| Falla del firewall: re-instancia en < 5 s | Conmutación 0.73 s · interrupción para el robot 1.05 s · re-instancia del caído 9.1 s | `nfv_failover_*.txt`, `nfv_eventos.log` |
| Throughput de la red óptica con DBA | Asegurados respetados y excedente por peso; nunca supera 100 Mbit/s | `f5g_throughput_*.txt`, `f5g_dba_*.svg/.csv` |

## Cómo tomar las evidencias (≈10 min)

### Paso 1 – Levantar el laboratorio (PowerShell)
```bash
cd C:\Users\DD\Documents\Proyecto4_Telecomunicaciones
```
```bash
powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1
```
Está listo cuando la tabla muestra 4/4/4 en spines y 2/2/2 en leafs, aparecen las **4 sesiones 5G** (`TUN interface[...]`)
y la línea `NFV: {"activo":"fw1",...}`.

### Paso 2 – Entrar a la VM (segunda ventana de PowerShell)
```bash
ssh gns3@192.168.56.102
```
```bash
cd ~/netcloud-secure/automation && . venv/bin/activate
```

### Paso 3 – Generar cada evidencia y capturar la pantalla
Captura con **Win + Shift + S** y guarda en `evidence\capturas_pantalla\` con el nombre indicado.

| # | Comando (en la VM) | Qué capturar | Archivo |
|---|---|---|---|
| 1 | `bash ../scripts/prueba_5g.sh` | El inicio: abonados con su 5QI/ARP, NG Setup y registros del AMF | `5g_registro.png` |
| 2 | (misma salida, al final) | Tabla de latencia (CUMPLE), balanceo srv1/srv2 y "BLOQUEADO" | `5g_latencia_sfc.png` |
| 3 | `bash ../scripts/prueba_nfv.sh` | Eventos del orquestador y el bloque **RESULTADO** | `nfv_failover.png` |
| 4 | `python3 prueba_f5g.py` (dura ~1 min) | La tabla por fases | `f5g_throughput.png` |

Luego, en Windows (explorador de archivos), abre con doble clic:
| # | Archivo en `evidence\` | Qué capturar | Archivo |
|---|---|---|---|
| 5 | el `nfv_estado_*.html` más reciente (se abre en el navegador) | El diagrama y la tabla de estado | `nfv_estado.png` |
| 6 | el `f5g_dba_*.svg` más reciente (se abre en el navegador) | La gráfica completa | `f5g_dba.png` |
| 7 | GNS3 con el proyecto `netcloud` | Topología completa con todos los nodos en verde (*View → Fit in view*) | `topologia_gns3_entrega2.png` |

> Los archivos de texto que generan los comandos 1, 3 y 4 quedan en la VM. Cuando termines dime
> **"trae la evidencia y sube las capturas"** y yo los copio al repositorio y hago el commit.

## Demostración en vivo (si el comité la pide)
Los mismos comandos del paso 3, en ese orden. Narrativa sugerida:
1. `prueba_5g.sh` – "El robot se registra en nuestro 5G privado, su tráfico viaja por GTP sobre el fabric EVPN y pasa
   por el firewall y el balanceador virtuales en ~3 ms. La tablet administrativa no puede llegar a la red OT."
2. `prueba_nfv.sh` – "Mato a la fuerza el contenedor del firewall: el orquestador lo detecta en 0.6 s, mueve las IP
   virtuales al respaldo y el robot pierde ~1 s de tráfico; luego re-instancia el contenedor caído como nuevo respaldo."
3. `prueba_f5g.py` – "Tres sucursales compiten por el PON: el DBA garantiza ERP 30 y cámaras 20 Mbit/s y reparte el
   resto por peso cada 250 ms."

## Respuestas preparadas (sección 10 del PDF)
- **SFC sin alterar la latencia crítica:** la cadena se construye por enrutamiento (el UPF tiene como siguiente salto la
  VIP del firewall, y este la del balanceador); son funciones en el kernel (nftables) y un proxy en memoria (HAProxy),
  sin desvíos ni túneles extra. Medido: ~3 ms UE → servidor con toda la cadena.
- **QoS y bearers:** cada DNN define el flujo QoS por defecto de la sesión PDU. `iot` usa **5QI 80** (no-GBR de baja
  latencia, presupuesto de retardo 10 ms) con **ARP 1** y capacidad de prioridad sobre otros; `admin` usa **5QI 9**
  (best effort) con **ARP 8** y vulnerable a ser desplazado, y un AMBR de 20 Mbit/s contra 100 de IoT.
  Evidencia: tabla de abonados en `5g_registro_*.txt`.
- **Por qué F5G simulado:** no existe un emulador libre de la capa física GPON; se simula la ODN (splitter = hub),
  los T-CONT (colas HTB por ONT) y el protocolo DBA por reporte de estado de ITU-T G.984.3, escalado a 100 Mbit/s.

## Si algo falla
| Síntoma | Qué hacer |
|---|---|
| Faltan sesiones 5G en el paso 1 | En la VM: `python3 deploy.py --nodes core5g gnb ue` |
| `prueba_nfv.sh` dice que el respaldo no está listo | `sh ../scripts/orquestador.sh` y espera 10 s |
| `prueba_f5g.py` da 0 en una ONT | `python3 deploy.py --nodes olt ont1 ont2 ont3` y repite |
| Después de cambiar la topología en GNS3 no hay tráfico entre spines y leafs | Cierra y reabre el proyecto y repite el paso 1 |
