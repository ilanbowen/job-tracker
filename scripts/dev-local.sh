#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Error: $PYTHON_BIN was not found. Install python3 or run with PYTHON_BIN=/path/to/python3." >&2
  exit 1
fi

"$PYTHON_BIN" -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

python - <<'PY'
import os
import sys
import time
from urllib.parse import urlparse

import psycopg2
from app.config import settings

raw_url = os.environ.get("DATABASE_URL", settings.database_url)
url = raw_url.replace("postgresql+psycopg2", "postgresql")
parsed = urlparse(url)

if parsed.scheme.startswith("sqlite"):
    sys.exit("This project is configured for PostgreSQL. DATABASE_URL should not use sqlite://")

host = parsed.hostname or "localhost"
port = parsed.port or 5432
dbname = parsed.path.lstrip("/")
user = parsed.username
password = parsed.password

for attempt in range(1, 6):
    try:
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port,
            connect_timeout=2,
        )
        conn.close()
        print(f"PostgreSQL is reachable at {host}:{port}")
        break
    except Exception as exc:
        last_error = exc
        print(f"Waiting for PostgreSQL at {host}:{port}... attempt {attempt}/5")
        time.sleep(1)
else:
    print()
    print("Could not connect to PostgreSQL before running migrations.")
    print(f"Database URL target: {host}:{port}/{dbname}")
    print(f"Last error: {last_error}")
    print()
    print("If you want to run FastAPI locally while using Kubernetes PostgreSQL, first run this in another terminal:")
    print("  kubectl port-forward -n job-tracker svc/job-tracker-postgres 5432:5432")
    print()
    print("If the Helm release is not installed yet, run:")
    print("  ./scripts/build-and-import-k3s.sh")
    print("  helm upgrade --install job-tracker ./helm/job-tracker --namespace job-tracker --create-namespace")
    print("  kubectl rollout status -n job-tracker statefulset/job-tracker-postgres")
    sys.exit(1)
PY

alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
