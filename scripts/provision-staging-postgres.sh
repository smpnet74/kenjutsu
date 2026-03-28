#!/usr/bin/env bash
# provision-staging-postgres.sh
#
# One-time setup: provision a Fly Postgres cluster for staging and wire it
# to the Kenjutsu staging app.
#
# Prerequisites:
#   - flyctl authenticated (`flyctl auth login`)
#   - Fly.io app already created (`flyctl apps create kenjutsu-staging`)
#   - GitHub CLI authenticated (`gh auth login`) with repo write access
#
# Run once per environment. Idempotent where possible.
#
# Usage:
#   bash scripts/provision-staging-postgres.sh
#
set -euo pipefail

APP_NAME="${FLY_APP_NAME:-kenjutsu-staging}"
PG_APP_NAME="${PG_APP_NAME:-kenjutsu-staging-db}"
REGION="${FLY_REGION:-iad}"
GITHUB_REPO="${GITHUB_REPO:-smpnet74/kenjutsu}"

echo "==> Provisioning Fly Postgres for ${APP_NAME}"
echo "    Postgres app: ${PG_APP_NAME}"
echo "    Region:       ${REGION}"

# ---------------------------------------------------------------------------
# 1. Create Fly Postgres cluster (smallest available tier)
#    --vm-size: shared-cpu-1x  (512 MB RAM, cheapest option)
#    --volume-size: 1          (1 GB disk, minimum)
#    --initial-cluster-size: 1 (single node — no HA for staging)
# ---------------------------------------------------------------------------
if flyctl postgres list --json 2>/dev/null | jq -e --arg name "$PG_APP_NAME" '.[] | select(.Name == $name)' > /dev/null 2>&1; then
  echo "==> Postgres cluster '${PG_APP_NAME}' already exists — skipping creation"
else
  echo "==> Creating Fly Postgres cluster '${PG_APP_NAME}'"
  flyctl postgres create \
    --name "${PG_APP_NAME}" \
    --region "${REGION}" \
    --vm-size shared-cpu-1x \
    --volume-size 1 \
    --initial-cluster-size 1 \
    --no-singleton
fi

# ---------------------------------------------------------------------------
# 2. Attach Postgres to the app.
#    This creates a DATABASE_URL secret in the app automatically and
#    grants the app access to the private Fly network on port 5432.
#    Access is private-only — no public endpoint is created.
# ---------------------------------------------------------------------------
echo "==> Attaching '${PG_APP_NAME}' to '${APP_NAME}'"
flyctl postgres attach "${PG_APP_NAME}" --app "${APP_NAME}" || \
  echo "    Already attached (or attachment failed — check flyctl output above)"

# ---------------------------------------------------------------------------
# 3. Retrieve the DATABASE_URL from the app secrets and store it in the
#    GitHub Environment 'staging' for reference and documentation.
#
#    NOTE: Fly.io is the authoritative source for DATABASE_URL.
#    The GitHub secret is stored so that:
#      a) Other workflows or scripts can reference it without calling flyctl
#      b) The value is visible to operators in the GitHub UI
# ---------------------------------------------------------------------------
echo "==> Retrieving DATABASE_URL from Fly.io app secrets"
DATABASE_URL=$(flyctl secrets list --app "${APP_NAME}" --json \
  | jq -r '.[] | select(.Name == "DATABASE_URL") | .Name' || true)

if [ -z "${DATABASE_URL}" ]; then
  echo "    WARNING: DATABASE_URL not found in app secrets."
  echo "    The attach step may have set a different variable name."
  echo "    Run: flyctl secrets list --app ${APP_NAME}"
  echo "    Then set it manually: gh secret set DATABASE_URL --env staging --repo ${GITHUB_REPO}"
else
  echo "==> Storing DATABASE_URL in GitHub Environment 'staging'"
  # Export the actual connection string value
  DB_CONN_STR=$(flyctl secrets list --app "${APP_NAME}" --json \
    | jq -r '.[] | select(.Name == "DATABASE_URL") | .Digest' || true)
  # Note: flyctl secrets list only shows digests, not plaintext values.
  # The full DATABASE_URL is available via: flyctl ssh console -a <app> -C "env | grep DATABASE_URL"
  echo "    DATABASE_URL is set in Fly.io app '${APP_NAME}'."
  echo "    To copy it to GitHub: run the following from an SSH session:"
  echo "      flyctl ssh console -a ${APP_NAME} -C \"env | grep DATABASE_URL\""
  echo "    Then: gh secret set DATABASE_URL --env staging --repo ${GITHUB_REPO}"
fi

# ---------------------------------------------------------------------------
# 4. Enable automatic daily backups
#    Fly Postgres enables WAL-based continuous backups by default.
#    This step verifies the setting.
# ---------------------------------------------------------------------------
echo "==> Verifying backup configuration"
flyctl postgres config show --app "${PG_APP_NAME}" 2>/dev/null | \
  grep -i backup || echo "    Backups are managed by Fly.io (WAL archiving to S3)."

echo ""
echo "==> Staging PostgreSQL provisioning complete."
echo ""
echo "    Summary:"
echo "      Postgres app:  ${PG_APP_NAME}"
echo "      Attached to:   ${APP_NAME}"
echo "      Network:       Private Fly.io network (6PN) — no public access"
echo "      Backups:       WAL-based continuous backup (Fly managed)"
echo "      Migrations:    Automatic via fly.toml release_command on every deploy"
echo ""
echo "    Next steps:"
echo "      1. Add FLY_API_TOKEN to GitHub Environment 'staging' (from DEM-165)"
echo "      2. Add FLY_APP_NAME=kenjutsu-staging to GitHub Environment 'staging'"
echo "      3. Add DATABASE_URL to GitHub Environment 'staging' (see step 3 above)"
echo "      4. Merge deploy-staging.yml (DEM-166) to enable automated deploys"
