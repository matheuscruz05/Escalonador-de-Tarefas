#!/usr/bin/env bash
set -e

for i in 001 002 003 004 005; do
  echo "=== Rodando caso-teste-$i ==="
  python3 -m scheduler_sim.cli run \
    --config scheduler_sim/data/caso-teste-$i.txt \
    --mode full \
    --outdir out_teste_$i
done

