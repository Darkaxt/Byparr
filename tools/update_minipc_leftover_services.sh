#!/usr/bin/env bash
set -euo pipefail
. /usr/local/sbin/minimal-backup-lib.sh

exec 9>/var/lock/update-minipc-leftover-services.lock
if ! flock -n 9; then
  echo "$(date -Is) update skipped: another run is active"
  exit 0
fi

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_STAMP="$STAMP"
BACKUP_ROOT="/opt/backups/minipc-leftover-services"
BACKUP_DIR="$(backup_new_dir "$BACKUP_ROOT")"

log() { echo "$(date -Is) $*"; }

compose_update() {
  local name="$1" dir="$2"
  shift 2
  local services=("$@")
  log "Updating ${name} in ${dir}"
  cd "$dir"
  docker compose config >/dev/null
  if [ "${#services[@]}" -gt 0 ]; then
    docker compose pull "${services[@]}"
    docker compose up -d "${services[@]}"
  else
    docker compose pull
    docker compose up -d
  fi
}

require_container_running() {
  local container="$1" status
  status="$(docker inspect -f '{{.State.Status}}' "$container" 2>/dev/null || true)"
  if [ "$status" != "running" ]; then
    echo "Container ${container} is not running; status=${status}" >&2
    return 1
  fi
}

check_tor_proxy() {
  require_container_running tor-proxy
  docker exec tor-proxy sh -lc 'netstat -ltn 2>/dev/null | grep -q "0.0.0.0:9050" && netstat -ltn 2>/dev/null | grep -q "0.0.0.0:9051"'
  if ! docker logs --tail 200 tor-proxy 2>&1 | grep -q 'Bootstrapped 100%'; then
    echo "tor-proxy has not bootstrapped to 100%" >&2
    return 1
  fi
  log "tor-proxy health OK: SOCKS/control listeners active and Tor bootstrapped"
}

check_http_code() {
  local name="$1" url="$2"
  shift 2
  local allowed=("$@") code expected
  code="$(curl -k -s -o /dev/null -w '%{http_code}' "$url" || true)"
  for expected in "${allowed[@]}"; do
    if [ "$code" = "$expected" ]; then
      log "${name} health OK at ${url}: HTTP ${code}"
      return 0
    fi
  done
  echo "${name} health failed at ${url}: HTTP ${code}; expected ${allowed[*]}" >&2
  return 1
}

log "Starting MiniPC migrated-service update"
backup_copy_file /opt/prowlarr/compose.yaml "$BACKUP_DIR/prowlarr/compose.yaml"
backup_copy_file /opt/prowlarr/config/config.xml "$BACKUP_DIR/prowlarr/config.xml"
backup_sqlite_gzip /opt/prowlarr/config/prowlarr.db "$BACKUP_DIR/prowlarr/prowlarr.db.gz"
backup_copy_file /opt/byparr/compose.yaml "$BACKUP_DIR/byparr/compose.yaml"
backup_copy_file /opt/unpackerr/compose.yaml "$BACKUP_DIR/unpackerr/compose.yaml"
backup_copy_file /opt/unpackerr/.env "$BACKUP_DIR/unpackerr/.env"
backup_copy_file /opt/unpackerr/config/unpackerr.conf "$BACKUP_DIR/unpackerr/unpackerr.conf"
backup_copy_file /opt/houndarr/compose.yaml "$BACKUP_DIR/houndarr/compose.yaml"
backup_copy_file /opt/houndarr/.env "$BACKUP_DIR/houndarr/.env"
backup_sqlite_gzip /opt/houndarr/data/houndarr.db "$BACKUP_DIR/houndarr/houndarr.db.gz"
backup_copy_file /opt/lidaclips/compose.yaml "$BACKUP_DIR/lidaclips/compose.yaml"
backup_copy_file /opt/lidaclips/.env "$BACKUP_DIR/lidaclips/.env"
backup_copy_file /opt/lidaclips/config/settings_config.json "$BACKUP_DIR/lidaclips/settings_config.json"
backup_sqlite_gzip /opt/lidaclips/config/lidaclips.db "$BACKUP_DIR/lidaclips/lidaclips.db.gz"
backup_copy_file /opt/tunelog/compose.yaml "$BACKUP_DIR/tunelog/compose.yaml"
backup_copy_file /opt/tunelog/.env "$BACKUP_DIR/tunelog/.env"
backup_copy_file /opt/tunelog/config/config.json "$BACKUP_DIR/tunelog/config.json"
for db in /opt/tunelog/data/*.db; do
  [ -f "$db" ] || continue
  backup_sqlite_gzip "$db" "$BACKUP_DIR/tunelog/$(basename "$db").gz"
done
backup_copy_file /opt/audiomuse-ai/compose.yaml "$BACKUP_DIR/audiomuse-ai/compose.yaml"
backup_copy_file /opt/audiomuse-ai/.env "$BACKUP_DIR/audiomuse-ai/.env"
backup_pg_dump_gzip audiomuse-postgres 'pg_dump -U audiomuse -d audiomusedb' "$BACKUP_DIR/audiomuse-ai/audiomuse-postgres.sql.gz"
backup_copy_file /opt/tor-proxy/compose.yaml "$BACKUP_DIR/tor-proxy/compose.yaml"
backup_copy_file /opt/tor-proxy/data/state "$BACKUP_DIR/tor-proxy/state"
backup_copy_file /opt/tor-proxy/data/control_auth_cookie "$BACKUP_DIR/tor-proxy/control_auth_cookie"

compose_update tor-proxy /opt/tor-proxy tor-proxy
# Byparr is a reviewed local build; update it through its source qualification workflow.
log "Skipping registry update for locally built Byparr; retaining qualified image"
compose_update prowlarr /opt/prowlarr prowlarr
compose_update unpackerr /opt/unpackerr unpackerr
compose_update houndarr /opt/houndarr houndarr
compose_update audiomuse-ai /opt/audiomuse-ai redis postgres audiomuse-ai worker
compose_update tunelog /opt/tunelog tunelog-backend tunelog-frontend
compose_update lidaclips /opt/lidaclips lidaclips-pot lidaclips

log "Running MiniPC migrated-service health checks"
for c in tor-proxy byparr prowlarr unpackerr houndarr audiomuse-redis audiomuse-postgres audiomuse-ai audiomuse-worker tunelog-backend tunelog-frontend lidaclips-pot lidaclips; do
  require_container_running "$c"
done
check_tor_proxy
check_http_code prowlarr http://127.0.0.1:9696 302
check_http_code byparr http://127.0.0.1:8191/ready 200
check_http_code houndarr http://127.0.0.1:8877/ 401
check_http_code audiomuse http://127.0.0.1:8000/ 200
check_http_code tunelog-frontend http://127.0.0.1:8173/ 200
check_http_code lidaclips http://127.0.0.1:5000/ 200

backup_keep_latest_dir_only "$BACKUP_ROOT" 1
/usr/local/sbin/prune-docker-safe.sh >/dev/null || true
log "MiniPC migrated-service update completed"
log "Backup dir: ${BACKUP_DIR}"
