# Levanta el laboratorio completo desde Windows en un solo paso:
# GNS3 + GNS3 VM -> proyecto netcloud -> nodos -> configuracion (Netmiko) -> controlador SDN/IBN
# -> orquestador NFV (Entrega 2: 5G, VNFs y F5G se despliegan en el mismo paso).
# Uso (PowerShell, en la carpeta del repo):
#   powershell -ExecutionPolicy Bypass -File scripts\levantar_lab.ps1
$ErrorActionPreference = 'Stop'
$api = 'http://127.0.0.1:3080/v2'
$vm  = 'gns3@192.168.56.102'

function Esperar($texto, $segundos, [scriptblock]$listo) {
    Write-Host "$texto..." -NoNewline
    for ($t = 0; $t -lt $segundos; $t += 5) {
        try { if (& $listo) { Write-Host " OK ($t s)"; return } } catch {}
        Start-Sleep 5; Write-Host '.' -NoNewline
    }
    throw "No se logro: $texto (espera de $segundos s agotada)"
}

try { Invoke-RestMethod "$api/version" -TimeoutSec 3 | Out-Null }
catch { Write-Host 'Abriendo GNS3'; Start-Process 'C:\Program Files\GNS3\gns3.exe' }

Esperar 'Esperando la GNS3 VM' 600 {
    ((Invoke-RestMethod "$api/computes" -TimeoutSec 3) | Where-Object compute_id -eq 'vm').connected
}

$p = (Invoke-RestMethod "$api/projects") | Where-Object name -eq 'netcloud'
Invoke-RestMethod -Method Post "$api/projects/$($p.project_id)/open" | Out-Null
Invoke-RestMethod -Method Post "$api/projects/$($p.project_id)/nodes/start" -Body '{}' | Out-Null
Write-Host 'Proyecto netcloud abierto y nodos iniciados'
# IDs de GNS3 para que el orquestador NFV pueda re-instanciar VNFs caidas
$nodos = @{}
(Invoke-RestMethod "$api/projects/$($p.project_id)/nodes") | ForEach-Object { $nodos[$_.name] = $_.node_id }
@{ project_id = $p.project_id; nodes = $nodos } | ConvertTo-Json -Compress |
    ssh $vm 'cat > ~/netcloud-secure/automation/gns3_ids.json'
Start-Sleep 15

# La VM puede quedar con la hora atrasada si VirtualBox la pauso: se sincroniza con Windows
$epoch = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
ssh $vm "sudo -n date -u -s @$epoch >/dev/null"
Write-Host 'Desplegando configuracion (Netmiko) e iniciando el controlador...'
ssh $vm 'set -o pipefail; bash ~/arranque.sh 2>&1 | grep -v vtysh.conf && rm -f ~/netcloud-secure/automation/controller_state.json && sh ~/netcloud-secure/scripts/controlador.sh && sh ~/netcloud-secure/scripts/orquestador.sh && sh ~/netcloud-secure/scripts/monitoreo.sh && sh ~/netcloud-secure/scripts/siem.sh'
if ($LASTEXITCODE -ne 0) { throw 'Fallo el despliegue: revisa los nodos marcados FALLA arriba' }

Esperar 'Esperando convergencia OSPF/BGP EVPN' 300 {
    $t = Invoke-RestMethod 'http://192.168.56.102:8181/api/topology' -TimeoutSec 60
    ($t.PSObject.Properties.Value | Measure-Object evpn_established -Sum).Sum -ge 16
}
Invoke-RestMethod 'http://192.168.56.102:8181/api/topology' -TimeoutSec 60 |
    ForEach-Object { $_.PSObject.Properties | ForEach-Object {
        [pscustomobject]@{ nodo = $_.Name; ospf = $_.Value.ospf_full; ospf6 = $_.Value.ospf6_full; evpn = $_.Value.evpn_established } } } |
    Format-Table -AutoSize
Write-Host '5G: sesiones PDU activas en los UEs:'
ssh $vm 'sh ~/netcloud-secure/scripts/estado_5g.sh'
Write-Host 'Telemetria: Grafana http://192.168.56.102:3000  (tablero netcloud)   Prometheus :9090'
Write-Host 'Laboratorio listo. Demostraciones: DEFENSA.md (E1), DEFENSA2.md (E2), DEFENSA3.md (E3)'
