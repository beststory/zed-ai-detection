#!/bin/bash
# ZED Motion Tracker 백엔드 서버 실행 스크립트

# 가상환경 활성화
source venv/bin/activate

# 서버 실행
echo "=========================================="
echo "ZED Motion Tracker 백엔드 서버 시작"
echo "=========================================="
echo ""
echo "서버 주소: http://0.0.0.0:8000"
echo "API 문서: http://0.0.0.0:8000/docs"
echo ""
echo "종료하려면 Ctrl+C 를 누르세요"
echo ""

python main.py
