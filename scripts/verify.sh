#!/usr/bin/env bash
set -e

echo "==> 🔍 Running Ruff linter..."
ruff check .

echo "==> 🧪 Running Pytest suite..."
pytest -v

echo "==> ✅ All local verification checks passed!"
