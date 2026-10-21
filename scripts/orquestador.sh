#!/bin/sh
# Inicia (o reinicia) el orquestador NFV en segundo plano dentro de la GNS3 VM.
# Log: /tmp/orquestador.out   Eventos: evidence/nfv_eventos.log   Estado: automation/nfv_estado.json
cd "$(dirname "$0")/../automation" || exit 1
[ -f /tmp/orquestador.pid ] && kill "$(cat /tmp/orquestador.pid)" 2>/dev/null && sleep 1
. venv/bin/activate
nohup python3 orquestador_nfv.py </dev/null > /tmp/orquestador.out 2>&1 &
echo $! > /tmp/orquestador.pid
echo "orquestador NFV iniciado (pid $!)"
