#!/bin/sh
# Container start on hosts without a release step (DEV-37): migrate, then serve.
set -e
alembic upgrade head
exec uvicorn --factory app.main:create_app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --workers "${WEB_CONCURRENCY:-1}"
