#!/bin/sh
set -e

echo "[entrypoint] Inicializando banco de dados..."
python - <<'PYEOF'
from todo_project import app, db
with app.app_context():
    db.create_all()
print("[entrypoint] Banco pronto.")
PYEOF

exec "$@"
