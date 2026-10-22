# Guía de evidencias y demostración – Entrega 3 (Zero Trust, telemetría gRPC, SIEM y ataques)

Todo desde **PowerShell normal** en tu laptop; los comandos de red corren dentro de la GNS3 VM por `ssh`.
Diseño: `docs/superpowers/specs/2026-10-21-entrega3-design.md`.

## Qué se construyó
| Pieza | Implementación | Dónde |
|---|---|---|
| Microsegmentación Zero Trust | Firewall distribuido nftables por host (tabla `zt`), default-deny este-oeste, matriz por identidad (tags) | srv1, srv2, lb, `dbsrv` (VNI 10050) |
| Base de datos crítica / atacante | `dbsrv` (10.50.0.20, puertos 5432/3306/6379/27017) y `pc-corp` (10.50.0.30, comprometido) | nodos nuevos en SW-SVC |
| Telemetría | Exportadores stdlib (`:9100/metrics`) en fabric, 5G, NFV, F5G y DB → Prometheus + Grafana | contenedores en la GNS3 VM |
| SIEM gRPC | Streaming de eventos de seguridad por gRPC (shipper→servidor), correlación y mitigación automática | venv de la VM |
| Seguridad del núcleo 5G | Tabla nft `g5`: cuenta NGAP/GTP-U, limita señalización nueva, conjunto `bloqueados` | core5g |

## Resultados ya medidos (están en `evidence/`)
| Requisito del PDF | Resultado | Archivo |
|---|---|---|
| Port scan de equipo comprometido → BD bloqueado (§6) | 0 de 9 puertos abiertos; el acceso autorizado app→db:5432 sí funciona | `zerotrust_*.txt` |
| Movimiento lateral / exfiltración (§7) | pc-corp → srv1:8080 bloqueado; mitigación quirúrgica (corp→lb:80 sigue OK) | `zerotrust_*.txt` |
| Análisis de eventos automatizado (SIEM) | Detección por telemetría gRPC en <2 s y bloqueo automático del atacante en dbsrv | `siem.log` |
| Telemetría en streaming + Prometheus + tableros | 10/10 exportadores arriba; tablero Grafana en vivo | Grafana |
| DDoS de IoT falsos al núcleo 5G (§7) | 35 416 peticiones NGAP en 5 s, 35 371 descartadas; robot legítimo 600/600 pings, latencia 5 ms | `ddos5g_*.txt` |

## Cómo tomar las evidencias (~10 min)

### Paso 1 – Levantar el laboratorio (PowerShell)
```bash
cd C:\Users\DD\Documents\Proyecto4_Telecomunicaciones
```
```bash
powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1
```
Levanta las tres entregas e inicia Prometheus, Grafana y el SIEM. Está listo cuando imprime las URLs de Grafana.

### Paso 2 – Entrar a la VM (segunda ventana de PowerShell)
```bash
ssh gns3@192.168.56.102
```

### Paso 3 – Generar cada evidencia y capturar la pantalla
Captura con **Win + Shift + S** y guarda en `evidence\capturas_pantalla\` con el nombre indicado.

| # | Comando (en la VM) | Qué capturar | Archivo |
|---|---|---|---|
| 1 | `bash ~/netcloud-secure/scripts/prueba_zerotrust.sh` | Escaneo bloqueado (0/9), contadores nft y la **alerta+mitigación del SIEM** | `zerotrust.png` |
| 2 | `bash ~/netcloud-secure/scripts/prueba_ddos5g.sh` | Alerta DDoS, NGAP descartado y el robot legítimo con 0 pérdida / <10 ms | `ddos5g.png` |

### Paso 4 – Tableros (desde el navegador de Windows)
| # | Abrir | Qué capturar | Archivo |
|---|---|---|---|
| 3 | `http://192.168.56.102:3000` → tablero **NetCloud-Secure** | El tablero completo con datos en vivo (haz las pruebas 1 y 2 antes para que haya picos) | `grafana.png` |
| 4 | `http://192.168.56.102:9090/targets` | Los 10 exportadores en estado **UP** | `prometheus_targets.png` |

> Grafana entra sin contraseña (anónimo, solo lectura). Si te pide usuario: admin / gsm12345.
> Cuando termines, dime **"trae la evidencia y sube las capturas"** y las copio al repo con un commit.

## Respuestas preparadas (sección 10 del PDF)
- **Microsegmentación Zero Trust contra movimiento lateral:** cada host del segmento de servicios lleva su propio
  firewall (nft tabla `zt`) con política *default-deny* este-oeste; solo se aceptan los flujos rol→rol de la matriz
  (app→db:5432, lb→app:8080, corp→lb:80). Un host comprometido no confiable no puede siquiera escanear puertos de la
  BD: cada intento se cuenta por origen (`ztdrop_db_from_corp`) y se descarta. El SIEM, al ver el pico por el stream
  gRPC, bloquea al atacante en segundos. El aislamiento es por identidad, no por subred, así que un equipo infectado
  queda contenido aunque esté en la misma red.
- **gRPC en streaming vs SNMP (pregunta 10.5):** el SIEM recibe un flujo continuo de muestras empujadas (push) por
  gRPC; detecta el port scan y el DDoS en <2 s y dispara la mitigación automática. SNMP es *pull*: el colector sondea
  cada N segundos, así que entre sondeos un ataque pasa desapercibido, añade carga de polling y no es un flujo continuo.
  El modelo push/streaming da detección proactiva casi en tiempo real.
- **QoS y prioridad de bearers (10.3):** ver `5g_registro_*.txt` (Entrega 2): la telemetría robótica usa 5QI 80 (baja
  latencia) y ARP 1 con prioridad; el tráfico administrativo 5QI 9 best-effort y ARP 8.

## Si algo falla
| Síntoma | Qué hacer |
|---|---|
| El SIEM no genera alerta | En la VM: `sh ~/netcloud-secure/scripts/siem.sh` y repite la prueba |
| Grafana sin datos | `sh ~/netcloud-secure/scripts/monitoreo.sh`; espera 10 s y recarga |
| dbsrv/pc-corp sin responder | Cierra y reabre el proyecto en GNS3 y repite el paso 1 |
| pc-corp ya bloqueado de una corrida previa | El bloqueo expira solo en 10 min, o redepliega: `python3 deploy.py --nodes dbsrv` |
