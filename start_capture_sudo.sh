#!/bin/bash
cd /home/harvis/zed
export LD_LIBRARY_PATH=/usr/local/zed/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/usr/local/lib/python3.12/dist-packages:$PYTHONPATH

# Run ZED capture process with sudo (needed for ZED camera access)
sudo -E /home/harvis/zed/venv/bin/python zed_capture.py
