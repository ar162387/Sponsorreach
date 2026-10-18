#!/bin/sh
set -eu
task_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pg_bin="${SPONSORMATCH_PG_BIN:-/opt/homebrew/opt/postgresql@16/bin}"
task_data="$task_root/.local/postgres"
if [ ! -x "$pg_bin/postgres" ]; then
  echo "Set SPONSORMATCH_PG_BIN to a PostgreSQL >=16 bin directory with pgvector >=0.8 installed." >&2
  exit 1
fi
mkdir -p "$task_root/.local"
if [ ! -f "$task_data/PG_VERSION" ]; then
  "$pg_bin/initdb" -D "$task_data" -A trust --no-locale -E UTF8
fi
if ! "$pg_bin/pg_ctl" -D "$task_data" status >/dev/null 2>&1; then
  "$pg_bin/pg_ctl" -D "$task_data" -l "$task_root/.local/postgres.log" -o '-p 55432 -h 127.0.0.1' start
fi
if ! "$pg_bin/psql" -h 127.0.0.1 -p 55432 -d postgres -tAc "select 1 from pg_database where datname='sponsormatch'" | rg -q 1; then
  "$pg_bin/createdb" -h 127.0.0.1 -p 55432 sponsormatch
fi
echo "Dedicated local database ready on 127.0.0.1:55432."
