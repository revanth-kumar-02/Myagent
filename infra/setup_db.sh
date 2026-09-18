#!/usr/bin/env bash
# infra/setup_db.sh — Bootstrap the Kora PostgreSQL database
# Run this once: bash infra/setup_db.sh
# Requires postgres superuser access (sudo -u postgres)

set -e

DB_USER="kora"
DB_PASS="kora_dev_password"
DB_NAME="kora"

echo "==> Creating role '${DB_USER}' (if not exists)..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='${DB_USER}'" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';"

echo "==> Setting password..."
sudo -u postgres psql -c "ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASS}';"

echo "==> Creating database '${DB_NAME}' (if not exists)..."
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1 || \
  sudo -u postgres createdb -O "${DB_USER}" "${DB_NAME}"

echo "==> Installing extensions..."
sudo -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";"
sudo -u postgres psql -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"

echo "==> Granting privileges..."
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"

echo "==> Applying schema..."
sudo -u postgres psql -d "${DB_NAME}" -U postgres -f "$(dirname "$0")/migrations/001_initial_schema.sql"

echo ""
echo "✓ Database setup complete."
echo "  Connection: postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
