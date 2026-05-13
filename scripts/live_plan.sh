#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

CONFIG="${CONFIG:-configs/bigquant_rotation_hybrid_candidate_turnover.yaml}"
POSITIONS="${POSITIONS:-data/live/positions.csv}"
OUTPUT_DIR="${OUTPUT_DIR:-outputs/live/bigquant_rotation_hybrid_candidate_turnover}"
LOT_SIZE="${LOT_SIZE:-100}"
MIN_TRADE_VALUE="${MIN_TRADE_VALUE:-0}"
PYTHON="${PYTHON:-.conda/etf-quant/bin/python}"

if [ ! -f "$POSITIONS" ]; then
  echo "positions file not found: $POSITIONS"
  echo "copy data/live/positions_example.csv to $POSITIONS and fill your actual holdings."
  exit 1
fi

PYTHONPATH=src "$PYTHON" -m etf_quant.cli live-plan \
  --config "$CONFIG" \
  --positions "$POSITIONS" \
  --output-dir "$OUTPUT_DIR" \
  --lot-size "$LOT_SIZE" \
  --min-trade-value "$MIN_TRADE_VALUE"
