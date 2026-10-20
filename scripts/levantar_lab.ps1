# Levanta el laboratorio completo desde Windows en un solo paso:
# GNS3 + GNS3 VM -> proyecto netcloud -> nodos -> configuracion (Netmiko) -> controlador SDN/IBN.
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
Start-Sleep 15

Write-Host 'Desplegando configuracion (Netmiko) e iniciando el controlador...'
ssh $vm 'set -o pipefail; bash ~/arranque.sh 2>&1 | grep -v vtysh.conf && rm -f ~/netcloud-secure/automation/controller_state.json && sh ~/netcloud-secure/scripts/controlador.sh'
if ($LASTEXITCODE -ne 0) { throw 'Fallo el despliegue: revisa los nodos marcados FALLA arriba' }

Esperar 'Esperando convergencia OSPF/BGP EVPN' 300 {
    $t = Invoke-RestMethod 'http://192.168.56.102:8181/api/topology' -TimeoutSec 60
    ($t.PSObject.Properties.Value | Measure-Object evpn_established -Sum).Sum -ge 16
}
Invoke-RestMethod 'http://192.168.56.102:8181/api/topology' -TimeoutSec 60 |
    ForEach-Object { $_.PSObject.Properties | ForEach-Object {
        [pscustomobject]@{ nodo = $_.Name; ospf = $_.Value.ospf_full; ospf6 = $_.Value.ospf6_full; evpn = $_.Value.evpn_established } } } |
    Format-Table -AutoSize
Write-Host 'Laboratorio listo. Demostracion:  ssh gns3@192.168.56.102 "bash ~/netcloud-secure/scripts/prueba_ibn.sh"'
