#!/bin/sh
# Levanta Prometheus y Grafana como contenedores en la GNS3 VM (plano de analitica, Entrega 3).
# Acceso desde Windows:  Prometheus http://192.168.56.102:9090   Grafana http://192.168.56.102:3000
# Grafana entra sin contrasena (anonimo, solo lectura); admin: admin/gsm12345.
M=~/netcloud-secure/monitoreo
docker rm -f gsm-prometheus gsm-grafana >/dev/null 2>&1
docker run -d --name gsm-prometheus --network host --restart unless-stopped \
  -v "$M/prometheus.yml":/etc/prometheus/prometheus.yml:ro \
  prom/prometheus:v2.54.1 \
  --config.file=/etc/prometheus/prometheus.yml --storage.tsdb.retention.time=2h >/dev/null
docker run -d --name gsm-grafana --network host --restart unless-stopped \
  -e GF_SECURITY_ADMIN_PASSWORD=gsm12345 \
  -e GF_AUTH_ANONYMOUS_ENABLED=true -e GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer \
  -e GF_USERS_DEFAULT_THEME=light \
  -v "$M/grafana/datasources":/etc/grafana/provisioning/datasources:ro \
  -v "$M/grafana/dashboards":/etc/grafana/provisioning/dashboards:ro \
  grafana/grafana:11.2.0 >/dev/null
sleep 6
echo "Prometheus: $(docker inspect -f '{{.State.Status}}' gsm-prometheus)  Grafana: $(docker inspect -f '{{.State.Status}}' gsm-grafana)"
echo "  http://192.168.56.102:9090   http://192.168.56.102:3000  (tablero: netcloud)"
