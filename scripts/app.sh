#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-.conda/etf-quant/bin/python}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8765}"

PYTHONPATH=src "$PYTHON" -m etf_quant.cli app --host "$HOST" --port "$PORT"
