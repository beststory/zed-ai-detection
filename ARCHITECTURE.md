# 3-Camera 종합 모니터링 시스템 아키텍처

## 시스템 개요

3개 카메라를 활용한 AI 기반 실시간 모니터링 및 변화 감지 시스템

### 카메라 구성
1. **ZED 2i RGB 카메라** - 192.168.1.3:8005/stream/rgb
2. **ZED 2i Depth 카메라** - 192.168.1.3:8005/stream/depth
3. **한화 Wisenet CCTV** - 192.168.1.50 (RTSP: rtsp://admin:softway7&@192.168.1.50:554/profile1/media.smp)

---

## 핵심 기능

### 1. 모션 감지 (Motion Detection)
- **OpenCV 배경 차감 (Background Subtraction)**
  - MOG2, KNN 알고리즘 사용
  - 실시간 움직임 감지
  - 바운딩 박스 표시

### 2. 사람 감지 (Person Detection)
- **YOLOv8 / YOLOv5** (오픈소스)
  - 실시간 객체 감지
  - 사람 클래스 필터링
  - 신뢰도 점수 표시
  - 카운팅 및 추적

### 3. 구조 변화 감지 (Structural Change Detection)
- **기준선 비교 (Baseline Comparison)**
  - 첫 프레임을 기준선으로 저장
  - 구조적 특징점(SIFT/ORB) 추출
  - 시간 경과에 따른 변화량 측정

- **에지 검출 (Edge Detection)**
  - Canny Edge Detector
  - 직선/곡선 변화 감지
  - 픽셀 단위 변위 측정 (mm 단위 변환)

- **깊이 맵 활용 (Depth Map Analysis)**
  - ZED 2i Depth 데이터 활용
  - 3D 공간 변위 측정
  - 정밀한 거리 계산 (mm 단위)

### 4. AI 분석 (Ollama GPT-4o-mini 통합)
- **이미지 분석**
  - 이상 상황 자동 판단
  - 자연어 설명 생성
  - 위험도 평가

- **시계열 분석**
  - 변화 패턴 분석
  - 예측 및 경고

---

## 기술 스택

### 백엔드
- **Python 3.12**
- **FastAPI** - REST API 서버
- **OpenCV** - 영상 처리
- **YOLOv8 (ultralytics)** - 객체 감지
- **NumPy** - 수치 계산
- **Pillow** - 이미지 처리
- **python-multipart** - 멀티미디어 처리
- **httpx** - Ollama API 통신

### 프론트엔드
- **Vanilla JavaScript** (모듈 시스템)
- **HTML5/CSS3**
- **Chart.js** - 데이터 시각화
- **Vite** - 개발 서버

### AI/ML
- **Ollama (GPT-4o-mini)** - 로컬 LLM
- **YOLOv8** - 사전 학습 모델
- **OpenCV DNN 모듈** - 추론 가속

### 카메라 SDK
- **ZED SDK 5.1.1** - Stereolabs ZED 2i
- **RTSP** - 한화 Wisenet CCTV

---

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vite)                          │
│                     http://192.168.1.3:5173                     │
│  ┌──────────┬──────────┬──────────┬──────────┬─────────────┐   │
│  │  Video   │  Point   │  Body    │ Sensors  │ IP Cameras  │   │
│  │ Streams  │  Cloud   │ Tracking │   Data   │   + AI      │   │
│  └──────────┴──────────┴──────────┴──────────┴─────────────┘   │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────┴────────────────────────────────────────┐
│                 Backend API (FastAPI)                           │
│                  http://192.168.1.3:8005                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  /stream/rgb, /stream/depth                              │  │
│  │  /api/pointcloud, /api/bodies, /api/sensors             │  │
│  │  /api/detection/motion                                   │  │
│  │  /api/detection/person                                   │  │
│  │  /api/detection/structure                                │  │
│  │  /api/analysis/ai                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
└───┬───────────┬────────────┬────────────────────────────────────┘
    │           │            │
┌───┴───┐  ┌───┴────┐  ┌────┴─────┐
│ ZED   │  │ ZED    │  │ Hanwha   │
│ RGB   │  │ Depth  │  │ Wisenet  │
│       │  │        │  │ CCTV     │
└───────┘  └────────┘  └──────────┘
                            │
                    ┌───────┴────────┐
                    │ Ollama Server  │
                    │ (localhost)    │
                    │ GPT-4o-mini    │
                    └────────────────┘
```

---

## 디렉토리 구조

```
/home/harvis/zed/
├── main.py                    # FastAPI 메인 서버
├── camera.py                  # ZED 카메라 제어
├── config.py                  # 설정 파일
├── .env                       # 환경 변수 (Ollama 설정)
│
├── detection/                 # 감지 모듈
│   ├── __init__.py
│   ├── motion.py              # 모션 감지
│   ├── person.py              # 사람 감지 (YOLO)
│   ├── structure.py           # 구조 변화 감지
│   └── utils.py               # 공통 유틸리티
│
├── ai/                        # AI 분석 모듈
│   ├── __init__.py
│   ├── ollama_client.py       # Ollama API 클라이언트
│   └── analyzer.py            # 이미지 분석기
│
├── models/                    # 사전 학습 모델
│   └── yolov8n.pt            # YOLOv8 Nano 모델
│
├── data/                      # 데이터 저장
│   ├── baselines/             # 기준선 이미지
│   ├── events/                # 감지 이벤트 로그
│   └── measurements/          # 변화량 측정 데이터
│
├── frontend/                  # 프론트엔드
│   ├── index.html
│   ├── app.js
│   └── styles.css
│
└── requirements.txt           # Python 의존성
```

---

## API 엔드포인트

### 기존 엔드포인트
- `GET /` - 서버 상태
- `GET /stream/rgb` - RGB 스트림
- `GET /stream/depth` - Depth 스트림
- `GET /api/pointcloud` - 포인트 클라우드 데이터
- `GET /api/bodies` - 신체 추적 데이터
- `GET /api/sensors` - IMU 센서 데이터

### 신규 엔드포인트

#### 감지 API
- `GET /api/detection/motion` - 실시간 모션 감지
- `GET /api/detection/person` - 사람 감지 (YOLO)
- `GET /api/detection/structure` - 구조 변화 감지
- `POST /api/detection/baseline` - 기준선 설정
- `GET /api/detection/events` - 감지 이벤트 로그

#### 측정 API
- `GET /api/measurement/displacement` - 변위 측정 (mm 단위)
- `GET /api/measurement/history` - 시계열 변화 데이터

#### AI 분석 API
- `POST /api/analysis/image` - 이미지 AI 분석
- `POST /api/analysis/anomaly` - 이상 감지 분석
- `GET /api/analysis/report` - 종합 분석 리포트

---

## 구현 단계

### Phase 1: 모션 감지 (Motion Detection)
1. OpenCV BackgroundSubtractor 구현
2. 모션 영역 바운딩 박스 표시
3. 프론트엔드 실시간 표시
4. 이벤트 로깅

### Phase 2: 사람 감지 (Person Detection)
1. YOLOv8 모델 다운로드 및 통합
2. 실시간 추론 파이프라인
3. 사람 카운팅 및 추적
4. 경고 알림 시스템

### Phase 3: 구조 변화 감지 (Structural Change)
1. 기준선 이미지 저장
2. 특징점 추출 (SIFT/ORB)
3. 에지 검출 및 비교
4. Depth 맵 활용 변위 측정
5. mm 단위 정밀 측정

### Phase 4: AI 분석 (Ollama Integration)
1. Ollama API 클라이언트 구현
2. 이미지 분석 프롬프트 설계
3. 자연어 설명 생성
4. 종합 리포트 생성

### Phase 5: 프론트엔드 통합
1. 새 탭 "AI 모니터링" 추가
2. 실시간 감지 결과 표시
3. 차트 및 시각화
4. 이벤트 타임라인

---

## 환경 변수 (.env)

```env
# Ollama 설정
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=gpt-4o-mini

# 감지 설정
MOTION_THRESHOLD=500
PERSON_CONFIDENCE=0.5
STRUCTURE_SENSITIVITY=0.01

# 카메라 설정
ZED_RESOLUTION=VGA
ZED_FPS=15
HANWHA_RTSP_URL=rtsp://admin:softway7&@192.168.1.50:554/profile1/media.smp
```

---

## 성능 최적화

1. **멀티스레딩**
   - 각 카메라 별도 스레드 처리
   - YOLO 추론 비동기 처리

2. **프레임 샘플링**
   - 구조 변화 감지: 1 FPS
   - 모션 감지: 10 FPS
   - 사람 감지: 5 FPS

3. **GPU 가속**
   - CUDA 활성화 (가능한 경우)
   - OpenCV DNN 모듈 최적화

---

## 보안 고려사항

1. RTSP 인증 정보 암호화
2. API 엔드포인트 인증
3. 이벤트 로그 암호화 저장
4. 프론트엔드 CORS 설정

---

## 모니터링 대시보드 기능

### 실시간 모니터링
- 3개 카메라 동시 표시
- 감지 결과 오버레이
- 실시간 통계

### 이벤트 관리
- 타임라인 뷰
- 필터링 및 검색
- 이벤트 재생

### 분석 리포트
- 일/주/월 통계
- 변화 추이 그래프
- AI 분석 요약

---

## 다음 단계

1. .env 파일 생성 및 Ollama 설정 확인
2. YOLOv8 설치 및 모델 다운로드
3. detection/ 모듈 구현
4. AI 분석 모듈 구현
5. 프론트엔드 통합
