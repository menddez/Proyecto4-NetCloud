# Guía de presentación – NetCloud-Secure (15 minutos)

Proyecto integrador de Telecomunicaciones. Objetivo de la presentación: **venderle el proyecto al
catedrático** —explicar el problema, la solución y sus beneficios— y luego **demostrarlo en vivo** con las
pruebas de mayor impacto. Las pruebas largas (IBN completa, failover NFV, throughput F5G) quedan respaldadas
en el informe y en las capturas; aquí se corren solo las rápidas y contundentes para respetar el límite de tiempo.

## Distribución del tiempo (15 min)
| Bloque | Minutos | Contenido |
|---|---|---|
| 1. Apertura y "venta" | 0:00 – 4:30 | Problema del cliente, solución, beneficios de negocio |
| 2. Demostración en vivo | 4:30 – 13:00 | Panorama, automatización/tejido, IBN, 5G, Zero Trust, DDoS |
| 3. Cierre y preguntas | 13:00 – 15:00 | Resumen de valor y preguntas del catedrático |

---

## ANTES de empezar (preparación, NO cuenta en los 15 min)

> Haz esto 10 minutos antes. El laboratorio tarda ~5–8 min en levantar; **nunca lo levantes durante la presentación.**

1. **Levanta todo el laboratorio** (PowerShell, en la carpeta del proyecto):
   ```
   powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1
   ```
   Espera a que imprima la tabla con **4/4/4** en los spines, **2/2/2** en los leafs, las **4 sesiones PDU** y las URLs.
2. **Abre y acomoda las ventanas** que usarás (para no perder tiempo cambiando):
   - **GNS3** con el proyecto `netcloud` (todos los nodos en verde).
   - **Navegador** con dos pestañas: Grafana `http://192.168.56.102:3000` (tablero *NetCloud-Secure*) y Prometheus `http://192.168.56.102:9090/targets`.
   - **Terminal SSH** a la VM, ya posicionada:
     ```
     ssh gns3@192.168.56.102
     ```
     y dentro:
     ```
     cd ~/netcloud-secure/automation && . venv/bin/activate
     ```
3. **Ten a la mano** el informe en PDF y, por si algo falla en vivo, el video de respaldo (si lo grabaste).

---

## BLOQUE 1 — Apertura y "venta" (0:00 – 4:30)

> Habla mirando al catedrático, sin terminal todavía. Vende el *problema* y el *resultado*, no la tecnología.

**(0:00) El problema del cliente.**
> «GSM-Cloud es una multinacional de manufactura con plantas robotizadas en Centroamérica. Su red actual los
> está frenando: los robots sufren microcortes y más de 40 ms de latencia, abrir un servicio nuevo tarda
> semanas de configuración manual en cientos de equipos, y la unión de las redes de oficina (IT) y de planta
> (OT) abrió la puerta a que un ataque salte de una PC infectada a la línea de producción. Necesitan
> transformar su red, no parchearla.»

**(1:30) La solución: NetCloud-Secure.**
> «Diseñamos una red definida por software, totalmente automatizada y segura, sobre cinco pilares: un tejido
> de centro de datos moderno (BGP EVPN/VXLAN), un cerebro que enruta por *intención* (SDN/IBN con Segment
> Routing), un 5G privado para los robots, fibra óptica F5G, funciones de red virtualizadas, y una capa de
> ciberseguridad Zero Trust con monitoreo en tiempo real. Todo se despliega con código, en minutos y de forma
> reproducible.»

**(2:30) Los beneficios (lo que le interesa al negocio).** Apóyate en esta tabla:

| Dolor actual | Lo que entrega NetCloud-Secure |
|---|---|
| Provisionamiento manual, semanas | Automatización total (IaC); un servicio nuevo se crea con **una llamada** |
| Latencia > 40 ms, microcortes | **3 ms** extremo a extremo para la robótica; reconvergencia en **0.19 s** |
| Cambios rígidos de ruta | Enrutamiento **por intención** (IBN): «quiero este tráfico con < 10 ms» y la red lo cumple sola |
| Ataques que saltan de IT a OT | **Zero Trust**: ningún equipo es confiable; un host comprometido queda contenido |
| Ceguera ante fallos y ataques | **Telemetría en tiempo real** y un SIEM que detecta y **mitiga solo** en < 2 s |

**(3:30) Transición a la demo.**
> «Y no es una presentación de diapositivas: todo esto está corriendo ahora mismo en un laboratorio
> virtualizado con GNS3. Se los muestro.»

---

## BLOQUE 2 — Demostración en vivo (4:30 – 13:00)

> Sigue el orden. Cada paso dice **qué ejecutar**, **qué decir** y **qué señalar en la salida**. Los comandos
> de la VM van en la terminal SSH ya abierta; los del navegador en las pestañas preparadas.

### 2.1 Panorama de la red (4:30 – 5:30) — *ventana de GNS3 y Grafana*
> «Esta es la red completa: dos *spines*, cuatro *leafs*, los hosts, el núcleo 5G, la radio, la fibra óptica y
> las funciones virtuales; más de 30 nodos, todos levantados automáticamente.»

Cambia a **Grafana** (pestaña ya abierta):
> «Y esta es la sala de control: telemetría en tiempo real. Aquí vemos los nodos activos, los 4 dispositivos
> 5G registrados, el throughput, y los contadores de seguridad. Esta visibilidad es la base para operar y
> defender la red.»

### 2.2 Automatización y tejido EVPN (5:30 – 7:00) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `head -25 ../topology/topology.yaml` | «Toda la red nace de **un solo archivo**: direcciones, VLANs, 5G, seguridad. Es la única fuente de verdad.» |
| `python3 deploy.py --dry-run && head -18 ../build/leaf1/frr.conf` | «Con eso, el sistema **genera** la configuración de cada equipo con plantillas. Esto es infraestructura como código.» |
| `docker exec $(docker ps --format '{{.Names}}' \| grep '\.leaf1\.') vtysh -c "show bgp l2vpn evpn summary"` | «Y aquí está el tejido funcionando: las sesiones **BGP EVPN establecidas** entre los equipos. Esto reemplaza el *flooding* tradicional de capa 2.» |

### 2.3 El cerebro: enrutamiento por intención con SRv6 (7:00 – 8:00) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `curl -s -X POST http://192.168.56.102:8181/api/intents -d '{"name":"demo","src":"leaf2","dst":"leaf4","max_rtt_ms":10}'` | «Le pido a la red una **intención de negocio**: lleva el tráfico de producción con menos de 10 ms. En la respuesta JSON se ve que el controlador **midió, eligió el mejor camino y lo programó solo** con Segment Routing (campo *spine* y *segments*). Nadie configuró rutas a mano.» |

### 2.4 Resiliencia: caída de un spine (8:00 – 8:50) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `python3 convergence_test.py --fail spine1 --runs 1` | «Simulo la **caída real de un equipo central** mientras corre tráfico. Miren el resultado: la red se recupera en ~**0.2 segundos**, por debajo del segundo exigido. El negocio ni se entera.» (tarda ~40 s) |

### 2.5 5G privado para los robots (8:50 – 9:30) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `sh ../scripts/estado_5g.sh` | «Los robots están conectados a **nuestro 5G privado**: cada uno con su sesión de datos activa. En el informe medimos **3 ms** de latencia extremo a extremo, muy por debajo de los 10 ms que exige la robótica, con prioridad garantizada sobre el tráfico administrativo.» |

### 2.6 Seguridad Zero Trust: contención de un ataque (9:30 – 11:00) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `bash ../scripts/prueba_zerotrust.sh` | «Un atacante tomó control de una PC corporativa e intenta **escanear la base de datos crítica**. Resultado: **0 de 9 puertos**; la microsegmentación lo bloquea todo. Y abajo: el **SIEM lo detectó por telemetría y lo bloqueó automáticamente** en segundos. El equipo legítimo sigue trabajando: contención quirúrgica.» (tarda ~25 s) |

### 2.7 Mitigación de un DDoS contra el 5G (11:00 – 12:30) — *terminal VM*
| Comando | Qué decir / señalar |
|---|---|
| `bash ../scripts/prueba_ddos5g.sh` | «Ahora miles de dispositivos IoT falsos inundan el núcleo 5G con peticiones de conexión. El núcleo **rechaza las identidades falsas y descarta el exceso** (miren los NGAP descartados), y el **robot legítimo conserva su sesión y su latencia** (0 % de pérdida). El ataque se absorbe sin afectar la producción.» (tarda ~60 s) |

> **Si vas sobrado de tiempo (opcional):** `bash ../scripts/prueba_nfv.sh` muestra que, al matar el cortafuegos
> virtual, el respaldo toma el relevo en **0.7 s** y el contenedor caído se reinstancia solo. (tarda ~2 min — solo si sobran minutos.)

---

## BLOQUE 3 — Cierre y preguntas (13:00 – 15:00)

**(13:00) Recapitulación de valor.**
> «En resumen: una red que se **despliega con código**, se **enruta por intención**, da **ultra-baja latencia**
> a la robótica, se **recupera sola** ante fallos y **se defiende sola** ante ataques, con visibilidad total en
> tiempo real. Pasamos de semanas a segundos, de 40 ms a 3 ms, y de una red ciega a una red que se protege a sí
> misma. Todo el código y las evidencias están en el repositorio y en el informe.»

**(13:30) Preguntas.** Respuestas de bolsillo (de la sección 10 del PDF):
- **EVPN vs flooding:** cada equipo *anuncia* las MAC/IP por BGP (rutas tipo 2) en lugar de *inundar*; menos tráfico, más escala y convergencia.
- **QoS 5G:** la telemetría robótica usa 5QI 80 (baja latencia) y ARP 1 con prioridad; lo administrativo, 5QI 9 best-effort.
- **Zero Trust:** firewall distribuido por identidad, denegación por defecto; el aislamiento es por rol, no por subred.
- **gRPC vs SNMP:** gRPC es *push* en streaming (detección en < 2 s); SNMP es *pull* periódico (ciego entre sondeos).
- **SFC sin latencia:** la cadena se arma por enrutamiento con funciones en el kernel; medimos ~3 ms a través de toda la cadena.

---

## Listado de comandos en orden (hoja de referencia)

> **PS** = PowerShell en Windows · **VM** = terminal SSH en la GNS3 VM (`cd ~/netcloud-secure/automation && . venv/bin/activate`)

| # | Dónde | Comando | Qué hace | Qué retorna / qué señalar | Duración |
|---|---|---|---|---|---|
| P1 | PS | `powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1` | Levanta TODO el laboratorio (3 entregas + monitoreo + SIEM) | Tabla 4/4/4 y 2/2/2, 4 sesiones PDU, URLs | ~5–8 min (antes) |
| P2 | Navegador | abrir `http://192.168.56.102:3000` y `:9090/targets` | Abre Grafana y Prometheus | Tablero en vivo; 10/10 exportadores UP | antes |
| P3 | PS→VM | `ssh gns3@192.168.56.102` → `cd ~/netcloud-secure/automation && . venv/bin/activate` | Abre la terminal de trabajo | Prompt `gns3@gns3vm` | antes |
| 1 | VM | `head -25 ../topology/topology.yaml` | Muestra la fuente única de verdad | El YAML con direcciones/VLANs/5G | instante |
| 2 | VM | `python3 deploy.py --dry-run && head -18 ../build/leaf1/frr.conf` | Genera las configuraciones (IaC) | Ruta de `build/` y config FRR de leaf1 | ~5 s |
| 3 | VM | `docker exec $(docker ps --format '{{.Names}}' \| grep '\.leaf1\.') vtysh -c "show bgp l2vpn evpn summary"` | Estado del tejido EVPN | Vecinos BGP **Established** | instante |
| 4 | VM | `curl -s -X POST http://192.168.56.102:8181/api/intents -d '{"name":"demo","src":"leaf2","dst":"leaf4","max_rtt_ms":10}'` | Crea una intención (IBN) | JSON con `spine` elegido y `segments` SRv6 | ~6 s |
| 5 | VM | `python3 convergence_test.py --fail spine1 --runs 1` | Caída real de un spine | «caida estimada … CUMPLE (<1 s)», ~0.2 s | ~40 s |
| 6 | VM | `sh ../scripts/estado_5g.sh` | Estado del 5G | 4 UEs con `TUN interface[...]` | instante |
| 7 | VM | `bash ../scripts/prueba_zerotrust.sh` | Port scan + Zero Trust + SIEM | 0/9 puertos; ALERTA + MITIGACION del SIEM | ~25 s |
| 8 | VM | `bash ../scripts/prueba_ddos5g.sh` | DDoS al núcleo 5G + mitigación | NGAP descartados; robot legítimo 0 % pérdida | ~60 s |
| 9 (opc.) | VM | `bash ../scripts/prueba_nfv.sh` | Falla del cortafuegos virtual | Conmutación 0.7 s; reinstanciación automática | ~2 min |

## Plan B (si algo falla en vivo)
- **Un comando no responde o da error:** no te detengas; di «lo tenemos documentado» y muestra la captura/figura del informe correspondiente. El informe y las capturas en `evidence/capturas_pantalla/` cubren cada prueba.
- **El laboratorio se ve lento:** confirma que la laptop está en «Mejor rendimiento» y conectada al cargador, y que Hyper-V está apagado (ver DEFENSA.md).
- **Se agota el tiempo:** las pruebas imprescindibles son **7 (Zero Trust)** y **8 (DDoS 5G)**; si vas muy justo, haz solo esas dos más el panorama en Grafana.
- **Guías detalladas por entrega:** DEFENSA.md (E1), DEFENSA2.md (E2), DEFENSA3.md (E3).
