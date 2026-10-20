# NETCLOUD-SECURE 5G/F5G – Entrega 1
Tejido spine-leaf **OSPF (underlay) + BGP EVPN/VXLAN (overlay)** con FRRouting en GNS3,
automatizado con **Python + Netmiko + Jinja2**.

## Estructura del repositorio
| Carpeta | Contenido |
|---|---|
| `automation/` | `deploy.py`, `verify.py`, `convergence_test.py` (Netmiko + Jinja2) |
| `templates/` | Plantillas Jinja2 de FRR y Linux por rol |
| `topology/topology.yaml` | Fuente única de verdad (direccionamiento, VNIs) |
| `docker/` | Imagen `gsm-frr:1.0` (FRR + sshd) |
| `gns3/` | `netcloud.gns3` (topología) y `crear_topologia_gns3.py` (la crea vía API REST) |
| `scripts/arranque.sh` | Arranque diario dentro de la GNS3 VM (red de gestión + despliegue) |
| `evidence/` | Salidas de verificación y reconvergencia |

Este repositorio (Windows) es la fuente de verdad; la GNS3 VM tiene una copia en `~/netcloud-secure`.
Sincronizar desde PowerShell/Git Bash en la carpeta del repo:
```bash
tar cf - automation templates topology docker | ssh gns3@192.168.56.102 "cd ~/netcloud-secure && tar xf -"
ssh gns3@192.168.56.102 "cd ~/netcloud-secure && tar cf - evidence" | tar xf -
```

## 1. Instalación en Windows (16 GB RAM)
1. **GNS3**: instalar GNS3 para Windows (gns3.com, descarga gratuita con registro). Aceptar la instalación de Wireshark.
2. **Hipervisor para la GNS3 VM**: VirtualBox (gratis) o VMware Workstation Pro (gratis para uso personal).
   Si usas Hyper-V/WSL2/Docker Desktop, pueden entrar en conflicto con VirtualBox; en ese caso usa la opción Hyper-V de la GNS3 VM.
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
python3 convergence_test.py --fail spine1   # reconvergencia < 1 s
```
Descarga la carpeta `evidence/` a tu PC (`scp`) para el informe.

## 6. Direccionamiento
- Loopbacks: spines `10.0.0.1-2/32`, leafs `10.0.0.11-14/32`. AS 65000 (iBGP, spines = route reflectors).
- Enlaces /31: spine *s* ↔ leaf *l* = `10.1.s.(2*(l-1))` (spine) / `+1` (leaf).
- VLAN 10 → VNI 10010 (IT), VLAN 20 → VNI 10020 (OT).
- Hosts: host1 `10.10.0.11`, host3 `10.10.0.13` (VLAN10, sitios distintos); host2 `10.20.0.12`, host4 `10.20.0.14` (VLAN20).
- Gestión: `192.168.122.0/24` (spines .11-.12, leafs .21-.24, hosts .31-.34).

## 7. Evidencias para la Entrega 1
- Salida de `show bgp l2vpn evpn summary`, `show evpn vni`, rutas tipo 2 (macip) y tipo 3 (multicast) → `evidence/verify_*.txt`
- Ping host1↔host3 y host2↔host4 (L2 extendida entre sitios) → mismo archivo
- Reconvergencia → `evidence/convergencia_*.txt`
- Capturas de GNS3 y de Wireshark (UDP 4789) en un enlace spine-leaf.

## 8. Problemas comunes
- **No conecta por SSH**: confirma que el nodo se llama exactamente `leaf1`, etc., y que el NAT está unido al switch de gestión. Prueba `ping 192.168.122.21` desde la GNS3 VM.
- **Sesiones EVPN en Idle/Active**: revisa `show ip ospf neighbor` y que las loopbacks sean alcanzables (`ping 10.0.0.1 -I lo`).
- **`show evpn vni` vacío**: verifica `ip -d link show vxlan10010` y que el kernel de la VM soporte VXLAN.
- **Reconvergencia > 1 s**: sube `hello_multiplier` (máx. 20) en `topology/topology.yaml` y vuelve a desplegar; el siguiente paso sería BFD.
- **Enlaces spine-leaf sin tráfico (cada lado solo ve sus propios hellos)**: la GNS3 VM se congeló (VirtualBox con Hyper-V activo),
  `systemd-networkd` reinició y ubridge cerró los túneles UDP. Solución: **cerrar y reabrir el proyecto** en GNS3 (detener/iniciar nodos
  no recrea el ubridge del switch/NAT). En la VM se desactivó el watchdog de networkd
  (`/etc/systemd/system/systemd-networkd.service.d/no-watchdog.conf`) para evitar que se repita.
- **`zebra is not running` tras iniciar un nodo**: carrera en el arranque de FRR; watchfrr lo revive en ~60 s.
  `deploy.py` ya espera a zebra antes de aplicar la configuración.
- **Verificar justo después de desplegar** muestra OSPF en `Loading` y BGP en `Active`: es la reconvergencia; espera ~1 min.
- **No uses *Reload* en nodos Docker**: GNS3 a veces no reconecta las interfaces. Usa *Stop* + *Start*.
