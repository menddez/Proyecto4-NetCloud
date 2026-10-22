#!/bin/sh
# Inicia el SIEM gRPC (servidor + shipper) en la GNS3 VM. Instala grpcio y genera el codigo de siem.proto
# la primera vez. Log: evidence/siem.log   Estado: automation/siem_estado.json
cd "$(dirname "$0")/../automation" || exit 1
. venv/bin/activate
python3 -c "import grpc_tools" 2>/dev/null || pip3 install -q grpcio grpcio-tools
[ -f siem_pb2.py ] && [ siem_pb2.py -nt siem.proto ] || python3 -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. siem.proto
for pid in /tmp/siem-server.pid /tmp/siem-shipper.pid; do [ -f "$pid" ] && kill "$(cat $pid)" 2>/dev/null; done
sleep 1
nohup python3 siem.py server </dev/null >/tmp/siem-server.out 2>&1 & echo $! > /tmp/siem-server.pid
sleep 2
nohup python3 siem.py shipper </dev/null >/tmp/siem-shipper.out 2>&1 & echo $! > /tmp/siem-shipper.pid
sleep 2
echo "SIEM: server pid $(cat /tmp/siem-server.pid), shipper pid $(cat /tmp/siem-shipper.pid)"
head -3 /tmp/siem-server.out
