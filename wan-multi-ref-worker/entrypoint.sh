#!/bin/bash
set -e

echo "Starting ComfyUI..."
python /ComfyUI/main.py --listen --use-sage-attention &

echo "Waiting for ComfyUI..."
max_wait=180
wait_count=0
while [ $wait_count -lt $max_wait ]; do
  if curl -s http://127.0.0.1:8188/ > /dev/null 2>&1; then
    echo "ComfyUI is ready"
    break
  fi
  sleep 2
  wait_count=$((wait_count + 2))
done

if [ $wait_count -ge $max_wait ]; then
  echo "ComfyUI failed to start"
  exit 1
fi

echo "Starting handler..."
exec python /handler.py
