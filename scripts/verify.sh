#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if command -v codespell &> /dev/null; then
  echo "==> 🔤 Running Codespell spellchecker..."
  codespell --skip="./.git/*,./.pytest_cache/*,./.ruff_cache/*,*.png,*.p12,*.pem,*.key,credentials.json" -L "hass,vidaa,remotenow"
fi

echo "==> 🔍 Running Ruff linter..."
ruff check .

echo "==> 🧪 Running Pytest suite..."
pytest -v

if command -v docker &> /dev/null; then
  echo "==> 🏛️ Running official Home Assistant Hassfest validator..."
  docker run --rm -v "$DIR"://github/workspace ghcr.io/home-assistant/hassfest
  echo "==> ✅ All local verification and Hassfest checks passed!"
else
  echo "==> ⚠️  Hassfest checks skipped (docker not found)"
  echo "==> ✅ Local verification passed (Hassfest checks skipped)"
fi


