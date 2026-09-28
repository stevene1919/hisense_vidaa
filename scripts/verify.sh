#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

echo "==> 🔍 Running Ruff linter..."
ruff check .

echo "==> 🧪 Running Pytest suite..."
pytest -v

if command -v docker &> /dev/null; then
  echo "==> 🏛️ Running official Home Assistant Hassfest validator..."
  docker run --rm -v "$DIR"://github/workspace ghcr.io/home-assistant/hassfest
fi

echo "==> ✅ All local verification and Hassfest checks passed!"

