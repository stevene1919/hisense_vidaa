#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

if command -v uv &> /dev/null; then
  echo "==> 🔤 Running Codespell spellchecker..."
  uv run codespell
elif command -v codespell &> /dev/null; then
  echo "==> 🔤 Running Codespell spellchecker..."
  codespell --skip="./.git/*,./.pytest_cache/*,./.ruff_cache/*,*.png,*.p12,*.pem,*.key,credentials.json,./custom_components/hisense_vidaa/translations/*" -L "hass,vidaa,remotenow"
fi

echo "==> 🔍 Running Ruff linter..."
if command -v uv &> /dev/null; then
  uv run ruff check .
else
  ruff check .
fi

echo "==> 🧪 Running Pytest suite..."
if command -v uv &> /dev/null; then
  uv run pytest -v
else
  pytest -v
fi

if command -v docker &> /dev/null; then
  echo "==> 🏛️ Running official Home Assistant Hassfest validator..."
  docker run --rm -v "$DIR"://github/workspace ghcr.io/home-assistant/hassfest
  echo "==> ✅ All local verification and Hassfest checks passed!"
else
  echo "==> ⚠️  Hassfest checks skipped (docker not found)"
  echo "==> ✅ Local verification passed (Hassfest checks skipped)"
fi


