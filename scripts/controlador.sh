#!/bin/sh
# Inicia (o reinicia) el controlador SDN/IBN en segundo plano dentro de la GNS3 VM.
# Log: /tmp/controller.out   API: http://192.168.56.102:8181
cd "$(dirname "$0")/../automation" || exit 1
[ -f /tmp/controller.pid ] && kill "$(cat /tmp/controller.pid)" 2>/dev/null && sleep 1
. venv/bin/activate
nohup python3 controller.py </dev/null > /tmp/controller.out 2>&1 &
echo $! > /tmp/controller.pid
echo "controlador iniciado (pid $!)"
