#!/bin/bash
# ZED Motion Tracker 백엔드 서버 설정 스크립트

set -e

echo "=========================================="
echo "ZED Motion Tracker 백엔드 설치 시작"
echo "=========================================="

# 1. 시스템 정보 확인
echo ""
echo "1. 시스템 정보 확인 중..."
echo "OS: $(uname -a)"
echo "Python 버전: $(python3 --version)"

# 2. NVIDIA GPU 확인
echo ""
echo "2. GPU 확인 중..."
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv
else
    echo "경고: nvidia-smi를 찾을 수 없습니다. NVIDIA 드라이버가 설치되어 있는지 확인하세요."
fi

# 3. ZED SDK 설치 확인
echo ""
echo "3. ZED SDK 설치 확인 중..."
if [ -d "/usr/local/zed" ]; then
    echo "ZED SDK가 이미 설치되어 있습니다."
else
    echo "ZED SDK가 설치되어 있지 않습니다."
    echo "ZED SDK를 다운로드하고 설치하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        echo "ZED SDK 다운로드 중..."
        # Ubuntu 22.04, CUDA 12.1 기준
        wget -O zed_installer.run https://download.stereolabs.com/zedsdk/4.2/cu121/ubuntu22
        chmod +x zed_installer.run
        echo "ZED SDK 설치 중... (sudo 권한이 필요합니다)"
        sudo ./zed_installer.run -- silent skip_tools
        rm zed_installer.run
        echo "ZED SDK 설치 완료!"
    else
        echo "ZED SDK 설치를 건너뜁니다."
    fi
fi

# 4. Python 가상환경 생성
echo ""
echo "4. Python 가상환경 생성 중..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "가상환경 생성 완료!"
else
    echo "가상환경이 이미 존재합니다."
fi

# 5. Python 의존성 설치
echo ""
echo "5. Python 의존성 설치 중..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 6. pyzed 설치 시도
echo ""
echo "6. pyzed Python 패키지 설치 중..."
if python3 -c "import pyzed.sl" 2>/dev/null; then
    echo "pyzed가 이미 설치되어 있습니다."
else
    pip install pyzed || echo "경고: pyzed 설치에 실패했습니다. ZED SDK가 올바르게 설치되었는지 확인하세요."
fi

# 7. 설정 확인
echo ""
echo "7. 설정 확인 중..."
echo "현재 디렉토리: $(pwd)"
echo "Python 버전: $(python --version)"
echo ""

# 8. 테스트 실행
echo ""
echo "8. 카메라 연결 테스트..."
python3 << 'EOF'
try:
    import pyzed.sl as sl
    print("✓ pyzed 모듈 로드 성공")

    # 간단한 카메라 테스트
    zed = sl.Camera()
    init_params = sl.InitParameters()
    err = zed.open(init_params)

    if err == sl.ERROR_CODE.SUCCESS:
        print("✓ ZED 카메라 연결 성공!")
        print(f"  카메라 모델: {zed.get_camera_information().camera_model}")
        print(f"  시리얼 번호: {zed.get_camera_information().serial_number}")
        zed.close()
    else:
        print(f"✗ 카메라 연결 실패: {err}")
        print("  카메라가 연결되어 있는지 확인하세요.")

except ImportError:
    print("✗ pyzed 모듈을 찾을 수 없습니다.")
    print("  Mock 모드로 실행됩니다.")
except Exception as e:
    print(f"✗ 오류 발생: {e}")
    print("  Mock 모드로 실행됩니다.")
EOF

echo ""
echo "=========================================="
echo "설치 완료!"
echo "=========================================="
echo ""
echo "백엔드 서버를 실행하려면:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "또는:"
echo "  ./run_server.sh"
echo ""
