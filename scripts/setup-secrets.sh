#!/usr/bin/env bash
# ============================================================
# setup-secrets.sh — Configure GitHub repo secrets for CI/CD
#
# Parses .github/workflows/deploy.yml for required secrets,
# checks which are already configured, and prompts to set
# any that are missing.
#
# Usage:  bash scripts/setup-secrets.sh
# Requires: gh CLI (authenticated)
# ============================================================

set -euo pipefail

WORKFLOW=".github/workflows/deploy.yml"

if [[ ! -f "$WORKFLOW" ]]; then
    echo "ERROR: $WORKFLOW not found. Run from the repo root."
    exit 1
fi

if ! command -v gh &>/dev/null; then
    echo "ERROR: gh CLI not found. Install from https://cli.github.com"
    exit 1
fi

# Extract unique secret names from the workflow file
REQUIRED=$(grep -oE 'secrets\.[A-Z_]+' "$WORKFLOW" | sed 's/secrets\.//' | sort -u)

if [[ -z "$REQUIRED" ]]; then
    echo "No secrets found in $WORKFLOW."
    exit 0
fi

echo "=== Required secrets (from $WORKFLOW) ==="
echo "$REQUIRED"
echo ""

# Get currently configured secrets
CONFIGURED=$(gh secret list --json name --jq '.[].name' 2>/dev/null || echo "")

echo "=== Currently configured ==="
if [[ -z "$CONFIGURED" ]]; then
    echo "(none)"
else
    echo "$CONFIGURED"
fi
echo ""

# Find missing secrets
MISSING=()
for secret in $REQUIRED; do
    if ! echo "$CONFIGURED" | grep -qx "$secret"; then
        MISSING+=("$secret")
    fi
done

if [[ ${#MISSING[@]} -eq 0 ]]; then
    echo "All secrets are configured. Nothing to do."
    exit 0
fi

echo "=== Missing secrets ==="
for s in "${MISSING[@]}"; do
    echo "  - $s"
done
echo ""

read -rp "Set missing secrets now? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    echo "Aborted."
    exit 0
fi

echo ""
for secret in "${MISSING[@]}"; do
    read -rsp "Enter value for $secret: " VALUE
    echo ""
    if [[ -z "$VALUE" ]]; then
        echo "  Skipped $secret (empty value)."
        continue
    fi
    echo "$VALUE" | gh secret set "$secret"
    echo "  Set $secret"
done

echo ""
echo "Done. Current secrets:"
gh secret list
