#!/bin/bash
cd /home/harvis/zed
source venv/bin/activate
# Add ZED SDK libraries and Python packages
export LD_LIBRARY_PATH=/usr/local/zed/lib:$LD_LIBRARY_PATH
export PYTHONPATH=/usr/local/lib/python3.12/dist-packages:$PYTHONPATH
python main.py
