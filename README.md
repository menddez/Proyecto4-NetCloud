# NETCLOUD-SECURE 5G/F5G – Entrega 1
Tejido spine-leaf **OSPFv2/OSPFv3 + BFD (underlay) + BGP EVPN/VXLAN (overlay)** con FRRouting en GNS3,
**Segment Routing SRv6** en el kernel Linux y un **controlador SDN/IBN** propio que traduce intenciones
en políticas SRv6. Todo automatizado con **Python + Netmiko + Jinja2**.

## Resultados (2026-10-20)
| Prueba | Resultado | Evidencia |
|---|---|---|
| OSPFv2 / OSPFv3 / BFD / BGP EVPN | 16/16 adyacencias v4, 16/16 v6, BFD up, 16/16 sesiones EVPN | `verify_20261020_175105.txt` |
| L2 extendida entre sitios (VNI 10010 y 10020) | 4/4 pings sin pérdida | mismo archivo |
| Caída real de un spine (modo `crash`) | **0.19 s** promedio (6/6 corridas < 1 s) | `convergencia_crash_*` |
| Caída de enlaces de un spine (modo `links`) | 0.01 s | `convergencia_links_*` |
| SRv6: VXLAN OT (VNI 10020) dirigido por spine2 | Capturado con SRH (`segleft` 1→0); el otro spine no ve el flujo | `ibn_20261020_175315.txt` |
| Falla del spine de la intención | Protección local: 0.75 s de pérdida; controlador reoptimiza en 10.5 s sin pérdida adicional | mismo archivo |
| Alta automática de servicio (VLAN 30 → VNI 10030) | 1 llamada a la API; rutas EVPN tipo 3 en los 4 VTEPs | `servicio_*.txt` |

## Estructura del repositorio
| Carpeta | Contenido |
|---|---|
| `automation/` | `deploy.py`, `verify.py`, `convergence_test.py` (Netmiko + Jinja2), `controller.py` (SDN/IBN) y `test_controller.py` |
| `templates/` | Plantillas Jinja2 de FRR y Linux por rol |
| `topology/topology.yaml` | Fuente única de verdad (direccionamiento, VNIs) |
| `docker/` | Imagen `gsm-frr:1.0` (FRR + sshd) |
| `gns3/` | `netcloud.gns3` (topología) y `crear_topologia_gns3.py` (la crea vía API REST) |
| `scripts/arranque.sh` | Arranque diario dentro de la GNS3 VM (red de gestión + despliegue) |
| `scripts/controlador.sh` | Inicia/reinicia el controlador en segundo plano |
| `scripts/levantar_lab.ps1` | **Desde Windows**: levanta GNS3, la VM, el proyecto, la configuración y el controlador en un paso |
| `DEFENSA.md` | Guía de la demostración en vivo y lista de evidencias |
| `scripts/prueba_ibn.sh` | Demostración completa SRv6 + IBN + falla de spine (para la defensa) |
| `evidence/` | Salidas de verificación, reconvergencia, IBN, bitácora del controlador y `capturas/*.pcap` (Wireshark) |

Este repositorio (Windows) es la fuente de verdad; la GNS3 VM tiene una copia en `~/netcloud-secure`.
Sincronizar desde PowerShell/Git Bash en la carpeta del repo:
```bash
tar cf - automation templates topology docker scripts | ssh gns3@192.168.56.102 "cd ~/netcloud-secure && tar xf -"
ssh gns3@192.168.56.102 "cd ~/netcloud-secure && tar cf - evidence" | tar xf -
```

## 1. Instalación en Windows (16 GB RAM)
1. **GNS3**: instalar GNS3 para Windows (gns3.com, descarga gratuita con registro). Aceptar la instalación de Wireshark.
2. **Hipervisor para la GNS3 VM**: VirtualBox (gratis) o VMware Workstation Pro (gratis para uso personal).
   **Desactiva Hyper-V mientras uses el laboratorio** (`bcdedit /set hypervisorlaunchtype off` como administrador y reiniciar).
   Con Hyper-V activo (WSL2, Docker Desktop, VBS) VirtualBox corre sobre él y la GNS3 VM sufre pausas de 20–300 s
   que rompen OSPF y los túneles de GNS3. Para volver a usar WSL/Docker: `bcdedit /set hypervisorlaunchtype auto` y reiniciar.
   La GNS3 VM se configuró en modo *headless*.
3. **GNS3 VM**: descargar la GNS3 VM de la misma versión que el GNS3 instalado, importarla y en
   *Edit → Preferences → GNS3 VM* habilitarla con **8 GB RAM y 4 vCPU**. (Deja ~8 GB para Windows.)
4. Anota la IP de la GNS3 VM (se muestra en su consola). Usuario de SSH por defecto: `gns3` / `gns3`.

## 2. Construir la imagen Docker (dentro de la GNS3 VM)
Desde PowerShell, copia el repositorio a la VM y construye:
```powershell
scp -r .\netcloud-secure gns3@<IP_GNS3_VM>:~/
ssh gns3@<IP_GNS3_VM>
cd ~/netcloud-secure/docker
sudo docker build -t gsm-frr:1.0 .
```

## 3. Crear los templates en GNS3
*Edit → Preferences → Docker containers → New → Existing image → `gsm-frr:1.0` → servidor: GNS3 VM*.
Crea tres templates con la **misma imagen**, cambiando solo el número de adaptadores:

| Template | Adaptadores | Console |
|---|---|---|
| gsm-spine | 5 | telnet |
| gsm-leaf | 4 | telnet |
| gsm-host | 2 | telnet |

Deja vacío el campo *Start command* (usa el de la imagen).

## 4. Armar la topología
Arrastra 2 spines, 4 leafs y 4 hosts. **Renómbralos exactamente**: `spine1, spine2, leaf1..leaf4, host1..host4`
(el nombre determina la IP de gestión). Agrega un **Ethernet switch** (gestión) y un **NAT**.

| Enlace | Conexión |
|---|---|
| Spine1 eth0..eth3 | Leaf1..Leaf4 **eth0** |
| Spine2 eth0..eth3 | Leaf1..Leaf4 **eth1** |
| Leaf *n* eth2 | Host *n* eth0 |
| Gestión | spine eth4, leaf eth3, host eth1 → Switch ↔ NAT |

Inicia todos los nodos (▶).

## 5. Ejecutar la automatización (desde la GNS3 VM)
```bash
cd ~/netcloud-secure/automation
sudo apt-get install -y python3-venv   # si hiciera falta
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
python3 deploy.py --dry-run     # revisa las configs generadas en ../build/
python3 deploy.py               # despliega en los 10 nodos
python3 verify.py               # tablas EVPN + pings L2 -> ../evidence/
python3 convergence_test.py --fail spine1   # caida real del spine (< 1 s)
python3 convergence_test.py --fail spine1 --mode links   # solo caida de enlaces
python3 test_controller.py      # prueba de la logica del controlador (sin laboratorio)
sh ../scripts/controlador.sh    # inicia el controlador SDN/IBN en :8181
bash ../scripts/prueba_ibn.sh   # demostracion SRv6 + IBN -> ../evidence/ibn_*.txt
```
Descarga la carpeta `evidence/` a tu PC (`scp`) para el informe.

## 6. Direccionamiento
- Loopbacks: spines `10.0.0.1-2/32`, leafs `10.0.0.11-14/32`. AS 65000 (iBGP, spines = route reflectors).
- Enlaces /31: spine *s* ↔ leaf *l* = `10.1.s.(2*(l-1))` (spine) / `+1` (leaf).
- VLAN 10 → VNI 10010 (IT), VLAN 20 → VNI 10020 (OT).
- Hosts: host1 `10.10.0.11`, host3 `10.10.0.13` (VLAN10, sitios distintos); host2 `10.20.0.12`, host4 `10.20.0.14` (VLAN20).
- Gestión: `192.168.122.0/24` (spines .11-.12, leafs .21-.24, hosts .31-.34).
- SRv6: nodo *N* = último octeto del loopback. Locator `fc00:0:N::/48` en la interfaz `sr0`, anunciado por OSPFv3:
  `::1` dirección del nodo, `::e` SID **End** (todos), `::d4` SID **End.DX4** (leafs, entrega el VXLAN IPv4 interno).
- BFD: perfil `rapido` (100 ms × 3) en OSPFv2 y OSPFv3 de todos los enlaces de fabric.

## 7. SRv6 y controlador SDN/IBN
El controlador (`automation/controller.py`, solo librería estándar + Netmiko) corre en la GNS3 VM y expone una API REST
en `http://192.168.56.102:8181` (también accesible desde Windows):

| Método y ruta | Qué hace |
|---|---|
| `GET /api/topology` | Estado OSPFv2/OSPFv3/EVPN de cada nodo |
| `POST /api/intents` | `{"name","src","dst","avoid":[],"max_rtt_ms":10}`: mide RTT por cada spine, elige el que cumple y programa SRv6 en ambos leafs |
| `GET /api/intents` / `DELETE /api/intents/<name>` | Consultar / retirar (el tráfico vuelve a OSPF ECMP) |
| `POST /api/reconcile` | Recalcula todas las intenciones |
| `POST /api/services` | `{"vlan":30,"vni":10030,"name":"Video"}`: crea el bridge + VXLAN en todos los leafs; EVPN lo anuncia |

Cómo se cumple una intención: en el leaf origen se instala `ip rule to <loopback destino> lookup 100` y en la tabla 100
`encap seg6 mode encap segs <spine>::e,<leaf destino>::d4`. El VXLAN sale encapsulado en IPv6 con SRH, el spine aplica
`End` y el leaf destino `End.DX4` (desencapsula y entrega). Igual en sentido contrario.

Lazo cerrado en dos niveles:
1. **Protección local** (en cada leaf, tipo BFD/TI-LFA): sondea el spine cada 100 ms y tras 2 fallos (~0.8 s) retira la
   política; el tráfico cae al ECMP de OSPF, que con BFD ya reconvergió.
2. **Controlador** (cada 5 s, con histéresis): detecta la falla o la retirada y reprograma por el mejor spine disponible.

Ejemplo desde PowerShell:
```bash
curl.exe -s -X POST http://192.168.56.102:8181/api/intents -d "{\"name\":\"ot\",\"src\":\"leaf2\",\"dst\":\"leaf4\",\"max_rtt_ms\":10}"
```
Bitácora de decisiones: `evidence/controller.log`. Sin autenticación: solo escucha en la red host-only del laboratorio.

## 8. Evidencias para la Entrega 1
- Salida de `show bgp l2vpn evpn summary`, `show evpn vni`, rutas tipo 2 (macip) y tipo 3 (multicast) → `evidence/verify_*.txt`
- Ping host1↔host3 y host2↔host4 (L2 extendida entre sitios) → mismo archivo
- Reconvergencia → `evidence/convergencia_*.txt`
- SRv6 + IBN + falla del spine de la intención → `evidence/ibn_*.txt`; alta de servicio → `evidence/servicio_*.txt`
- Capturas de GNS3 y de Wireshark (UDP 4789) en un enlace spine-leaf.

## 9. Problemas comunes
- **No conecta por SSH**: confirma que el nodo se llama exactamente `leaf1`, etc., y que el NAT está unido al switch de gestión. Prueba `ping 192.168.122.21` desde la GNS3 VM.
- **Sesiones EVPN en Idle/Active**: revisa `show ip ospf neighbor` y que las loopbacks sean alcanzables (`ping 10.0.0.1 -I lo`).
- **`show evpn vni` vacío**: verifica `ip -d link show vxlan10010` y que el kernel de la VM soporte VXLAN.
- **Reconvergencia > 1 s**: revisa `show bfd peers brief` (deben estar `up`); BFD es lo que baja la detección a ~0.3 s.
- **`docker pause` no simula un spine caído**: el kernel del contenedor sigue reenviando. `convergence_test.py` (modo `crash`)
  congela FRR **y** baja las interfaces con `nsenter`.
- **Enlaces spine-leaf sin tráfico (cada lado solo ve sus propios hellos)**: la GNS3 VM se congeló (VirtualBox con Hyper-V activo, ver §1),
  `systemd-networkd` reinició y ubridge cerró los túneles UDP. Solución: **cerrar y reabrir el proyecto** en GNS3 (detener/iniciar nodos
  no recrea el ubridge del switch/NAT). En la VM se desactivó el watchdog de networkd
  (`/etc/systemd/system/systemd-networkd.service.d/no-watchdog.conf`) para evitar que se repita.
- **`zebra is not running` tras iniciar un nodo**: carrera en el arranque de FRR; watchfrr lo revive en ~60 s.
  `deploy.py` ya espera a zebra (`pidof`; `pgrep -x` no funciona en busybox) antes de aplicar la configuración.
- **`pkill -f` por SSH mata tu propia sesión** si el patrón aparece en el comando; usa `scripts/controlador.sh` (PID en archivo).
- **Verificar justo después de desplegar** muestra OSPF en `Loading` y BGP en `Active`: es la reconvergencia; espera ~1 min.
- **No uses *Reload* en nodos Docker**: GNS3 a veces no reconecta las interfaces. Usa *Stop* + *Start*.
