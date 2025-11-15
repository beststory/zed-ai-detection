#!/bin/bash
cd /home/harvis/zed
# Add ZED SDK libraries
export LD_LIBRARY_PATH=/usr/local/zed/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/usr/local/lib/python3.12/dist-packages:$PYTHONPATH
# Run with sudo using venv python - disable auto-reload
sudo -E /home/harvis/zed/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8005 --no-access-log
