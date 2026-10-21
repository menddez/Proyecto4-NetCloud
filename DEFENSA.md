# Guía de la defensa en vivo – Entrega 1

Todo se ejecuta desde **tu laptop con Windows**, en **PowerShell normal** (no hace falta administrador).
Los comandos de la red corren dentro de la GNS3 VM; tú solo entras por `ssh`.

## Antes del día (una vez)
1. **Hyper-V apagado** (ya lo está). Si lo volviste a encender para usar Docker/WSL, apágalo:
   PowerShell **como administrador** → `bcdedit /set hypervisorlaunchtype off` → reiniciar Windows.
2. **Laptop conectada al cargador** y modo de energía *Mejor rendimiento*.
3. Haz un **ensayo completo** con esta guía y **grábalo** (Win + Alt + R inicia/detiene la grabación de la Xbox Game Bar;
   los videos quedan en *Videos\Capturas*). Si algo falla en vivo, ese video es tu respaldo.

## El día de la defensa

### Paso 1 – Levantar el laboratorio (≈5 min, hazlo antes de que empiece la llamada)
Abre PowerShell y ejecuta:
```bash
cd C:\Users\DD\Documents\Proyecto4_Telecomunicaciones
```
```bash
powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1
```
El script abre GNS3, espera la GNS3 VM, abre el proyecto `netcloud`, inicia los nodos, despliega la configuración con
Netmiko y arranca el controlador SDN. Termina con una tabla; **está listo cuando cada spine muestra 4/4/4 y cada leaf 2/2/2**
(vecinos OSPF / OSPFv3 / sesiones EVPN) y el mensaje *Laboratorio listo*.

Si aparece un nodo con `FALLA`: en GNS3 detén y vuelve a iniciar ese nodo (*Stop* y luego *Start*, **no** *Reload*) y repite el paso 1.

### Paso 2 – Comparte pantalla y muestra la topología
Ventana de GNS3: 2 spines, 4 leafs, 4 hosts, switch de gestión y NAT.
Explica: underlay OSPF + BFD, overlay BGP EVPN/VXLAN, spines como route reflectors, SRv6 encima.

### Paso 3 – Entra a la GNS3 VM (segunda ventana de PowerShell)
```bash
ssh gns3@192.168.56.102
```
Ya dentro (el prompt cambia a `gns3@gns3vm`), prepara el entorno una sola vez:
```bash
cd ~/netcloud-secure/automation && . venv/bin/activate
```

### Paso 4 – Demostraciones (en este orden)
| # | Comando (dentro de la VM) | Qué mostrar y decir | Criterio de la rúbrica |
|---|---|---|---|
| 1 | `cat ../topology/topology.yaml` | Fuente única de verdad: todo se genera desde aquí | Automatización |
| 2 | `python3 deploy.py --dry-run && cat ../build/leaf1/frr.conf` | Jinja2 genera la configuración de cada nodo | Automatización |
| 3 | `python3 deploy.py` | Netmiko configura los 10 nodos en paralelo | Automatización |
| 4 | `python3 verify.py \| less` (salir con `q`) | `show bgp l2vpn evpn summary`, rutas tipo 2 (MAC/IP) y tipo 3, VNIs, BFD, SIDs SRv6, pings L2 entre sitios | Tejido EVPN |
| 5 | `python3 convergence_test.py --fail spine1 --runs 1` | Caída **real** del spine: ~0.2 s gracias a BFD | Pruebas / fallos |
| 6 | `bash ../scripts/prueba_ibn.sh` | Intención → SRv6 por un spine (captura con SRH), falla de ese spine, protección local y reprogramación | SDN / IBN / SRv6 |
| 7 | Ver abajo (VM + Windows) | Alta de un servicio nuevo con una llamada a la API | Aprovisionamiento dinámico |

**Demo 7 – alta de un servicio nuevo.** Usa una VLAN que no exista: **40 en el ensayo, 50 en la defensa**
(las VLAN creadas quedan en los leafs hasta que se reinician los nodos).
1. En la VM, muestra el antes:
```bash
docker exec $(docker ps --format '{{.Names}}' | grep '\.leaf1\.') vtysh -c "show evpn vni"
```
2. En la primera ventana de PowerShell (Windows), consulta el estado y crea el servicio:
```bash
Invoke-RestMethod http://192.168.56.102:8181/api/topology
```
```bash
Invoke-RestMethod -Method Post http://192.168.56.102:8181/api/services -Body '{"vlan":50,"vni":10050,"name":"Video-Analitica"}'
```
3. En la VM repite el comando del punto 1: aparece la VNI 10050 con 3 VTEPs remotos (los otros leafs).

### Respuestas preparadas (sección 10 del PDF)
- **EVPN vs flooding:** cada leaf aprende MAC/IP de sus hosts y las anuncia como ruta BGP **tipo 2**; los demás leafs las
  instalan en su FDB con el VTEP remoto, sin inundar. La ruta **tipo 3** solo arma la lista de replicación para BUM.
  Evidencia: `show bgp l2vpn evpn route type macip` en `verify_*.txt`.
- **Por qué < 1 s:** BFD detecta la caída en 300 ms (100 ms × 3) y OSPF recalcula; los VTEPs siguen alcanzables por el
  otro spine y BGP no se cae porque sus sesiones van entre loopbacks.
- **Qué hace el controlador:** mide RTT por spine, elige el que cumple la intención y programa en ambos leafs
  `ip rule` + `encap seg6` (segmentos `End` en el spine y `End.DX4` en el leaf destino). Un guardián local retira la
  política en ~0.8 s si el spine cae y el controlador reoptimiza.

## Evidencia que debes guardar
Ya está en el repositorio (carpeta `evidence/`), lista para citarse en el informe:

| Archivo | Qué demuestra | Requisito del PDF |
|---|---|---|
| `verify_20261020_175105.txt` | OSPFv2/OSPFv3/BFD, `show bgp l2vpn evpn`, VNIs, rutas tipo 2 y 3, SIDs SRv6, pings L2 | "verificación de tablas EVPN" y "conectividad L2 extendida" |
| `convergencia_crash_spine1_*.txt`, `convergencia_crash_spine2_*.txt` | Caída real de cada spine: 0.19 s promedio | Prueba de convergencia < 1 s y fallo de spine |
| `convergencia_links_spine1_*.txt` | Caída solo de enlaces: 0.01 s (comparación) | Análisis de convergencia |
| `ibn_20261021_172552.txt` | Intención, política SRv6, captura con SRH, falla y reprogramación | SDN, SRv6, IBN |
| `servicio_20261020_175439.txt` | Alta de VNI 10030 por API y anuncio EVPN | Aprovisionamiento automático |
| `controller.log` | Bitácora de decisiones del controlador | Bitácoras de automatización |
| `capturas/*.pcap` | Abrir con Wireshark: VXLAN (VNI 10010), SRv6 con SRH y VXLAN dentro (VNI 10020), BFD/OSPF | Análisis de tráfico |
| Carpetas `automation/`, `templates/`, `topology/`, `docker/`, `gns3/` | Scripts Python, plantillas Jinja2, topología y manifiestos | "Scripts Python funcionales" y repositorio |

**Lo que solo tú puedes generar** (guárdalo en `evidence/capturas_pantalla/` del repo):
1. **Topología en GNS3** con todos los nodos en verde: Win + Shift + S, recorta la ventana y guarda como `topologia_gns3.png`.
2. **Wireshark – SRv6:** abre `evidence\capturas\srv6_vxlan_vni10020_spine1.pcap` (doble clic). Selecciona el primer paquete,
   despliega *Routing Header for IPv6 (Segment Routing)* y *Virtual eXtensible Local Area Network*; captura como `wireshark_srv6.png`.
3. **Wireshark – VXLAN:** abre `vxlan_evpn_vni10010_spine1.pcap`, despliega la capa VXLAN (VNI 10010); `wireshark_vxlan.png`.
4. **Salida de la demo 6** en la terminal: `demo_ibn.png`.
5. **El video del ensayo** (respaldo de la defensa).

Después, para subirlo al repo, dime "sube las capturas" y yo hago el commit.

## Si algo falla en vivo
| Síntoma | Qué hacer |
|---|---|
| `levantar_lab.ps1` se queda en "Esperando la GNS3 VM" | Cierra GNS3 por completo (detener la VM: **Sí**) y vuelve a correr el paso 1 |
| Un nodo marca `FALLA` | En GNS3: *Stop* + *Start* de ese nodo y repetir el paso 1 |
| `verify.py` muestra OSPF en `Loading` o BGP en `Active` | Se acaba de desplegar: espera 1 minuto y repite |
| Pings fallan en todos los enlaces | Cierra y reabre el proyecto en GNS3, y repite el paso 1 |
| La demo 6 dice que el controlador no responde | En la VM: `sh ~/netcloud-secure/scripts/controlador.sh` |

## Después de la defensa
Para volver a usar Docker Desktop o WSL: PowerShell **como administrador** → `bcdedit /set hypervisorlaunchtype auto` → reiniciar.
