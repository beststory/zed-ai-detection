# 멀티모달 비전 AI 시스템 아키텍처

## 📋 시스템 개요

**목표**: 2D CCTV + 3D ZED 카메라 데이터를 결합하여 행동/거리 변화/이상 징후를 자동 인식하는 실시간 비전 AI 시스템

## 🏗️ 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INPUT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  CCTV (RTSP)          │  ZED 2i Camera                              │
│  - H.264 Stream       │  - RGB Stream (ZMQ: tcp://localhost:5555)  │
│  - 192.168.1.50       │  - Depth Map                                │
│  - 30 FPS             │  - Point Cloud                              │
│                       │  - Skeleton Tracking (optional)             │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    SYNCHRONIZATION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  Frame Synchronizer                                                 │
│  - Timestamp-based matching (±100ms tolerance)                      │
│  - Frame buffer queue (max 60 frames)                               │
│  - Sync status monitoring                                           │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       AI PROCESSING LAYER                           │
├─────────────────────────────────────────────────────────────────────┤
│  Vision Processing Pipeline                                         │
│  ┌───────────────────┬───────────────────┬─────────────────────┐   │
│  │ Object Detection  │ 3D Position Track │ Movement Analysis   │   │
│  │ - YOLOv8          │ - ZED SDK         │ - Distance calc     │   │
│  │ - Person class    │ - Point cloud     │ - Speed estimation  │   │
│  │ - Bounding boxes  │ - XYZ coordinates │ - Direction vector  │   │
│  └───────────────────┴───────────────────┴─────────────────────┘   │
│                                                                     │
│  Multi-Modal Fusion Engine                                          │
│  - 2D→3D coordinate mapping                                         │
│  - Cross-camera object matching                                     │
│  - Depth-enhanced person tracking                                   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      EVENT DETECTION ENGINE                         │
├─────────────────────────────────────────────────────────────────────┤
│  Event Types:                                                       │
│  1. Zone Entry/Exit         - ROI + 3D coordinates                  │
│  2. Idle/Static Detection   - Movement < 0.1m for 10s               │
│  3. Fall Detection          - Skeleton angle + depth change         │
│  4. Distance Change Alert   - 3D position delta > threshold         │
│  5. Speed Alert             - Velocity > threshold                  │
│  6. New Object Appearance   - Object tracking delta                 │
│                                                                     │
│  Rule Engine:                                                       │
│  - Configurable thresholds                                          │
│  - Event scoring (confidence)                                       │
│  - Event filtering & aggregation                                    │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICES LAYER                         │
├─────────────────────────────────────────────────────────────────────┤
│  FastAPI Server (http://192.168.1.3:8005)                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ REST API Endpoints                                          │   │
│  │ - /api/events/latest (GET)                                  │   │
│  │ - /api/events/history (GET)                                 │   │
│  │ - /api/movement/tracking/{object_id} (GET)                  │   │
│  │ - /api/cameras/calibration (POST)                           │   │
│  │ - /api/zones/config (POST/GET)                              │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ WebSocket Endpoints                                         │   │
│  │ - /ws/events (real-time event stream)                       │   │
│  │ - /ws/tracking (real-time position updates)                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Background Services                                         │   │
│  │ - Event processor                                           │   │
│  │ - Frame buffer manager                                      │   │
│  │ - Database writer                                           │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      DATA PERSISTENCE LAYER                         │
├─────────────────────────────────────────────────────────────────────┤
│  SQLite Database (events.db)                                        │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Tables:                                                     │   │
│  │ - events (id, timestamp, type, camera_id, confidence, ...)  │   │
│  │ - positions (id, event_id, xyz, distance, speed, ...)       │   │
│  │ - zones (id, name, polygon, rules, ...)                     │   │
│  │ - calibration (camera_id, transform_matrix, ...)            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  File Storage (/home/harvis/zed/data/)                             │
│  - events/                - Event snapshot images                  │
│  - recordings/            - Video segments                          │
│  - measurements/          - 3D measurement data                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      FRONTEND LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Web UI (http://192.168.1.3:5173)                                  │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Live Monitoring Dashboard                                   │   │
│  │ ┌─────────────┬─────────────┬─────────────┐                │   │
│  │ │ CCTV Stream │ ZED RGB     │ ZED Depth   │                │   │
│  │ │ + Overlays  │ + Skeleton  │ + 3D Points │                │   │
│  │ └─────────────┴─────────────┴─────────────┘                │   │
│  │ ┌─────────────────────────────────────────┐                │   │
│  │ │ Real-time Event Feed (WebSocket)        │                │   │
│  │ │ - Event type, time, location            │                │   │
│  │ │ - Confidence score                      │                │   │
│  │ │ - Quick action buttons                  │                │   │
│  │ └─────────────────────────────────────────┘                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Event History & Analytics                                  │   │
│  │ - Timeline view                                             │   │
│  │ - Filter by type, camera, confidence                        │   │
│  │ - Export functionality                                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Configuration Panel                                         │   │
│  │ - Zone drawing tool                                         │   │
│  │ - Event rule editor                                         │   │
│  │ - Camera calibration                                        │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 📊 데이터 플로우

### 1. Frame Ingestion & Synchronization
```python
CCTV → RTSP Decoder → Frame Queue (timestamp: t1)
                                    ↓
                           Synchronizer (match ±100ms)
                                    ↑
ZED → ZMQ Publisher → Frame Queue (timestamp: t2)
```

### 2. AI Processing Pipeline
```python
Synchronized Frames → YOLOv8 Detection → Person Bounding Boxes
                                              ↓
                                        ZED 3D Mapping
                                              ↓
                                    XYZ Position + Depth
                                              ↓
                                    Movement Tracker
                                              ↓
                                Distance, Speed, Direction
```

### 3. Event Detection Flow
```python
Position Data → Rule Engine → Event Triggered?
                                    ↓ (Yes)
                              Event Object Created
                                    ↓
                           WebSocket Broadcast
                                    ↓
                           Database Storage
                                    ↓
                           Frontend Display
```

## 🔧 핵심 컴포넌트 구현

### 1. Frame Synchronizer (`sync/frame_sync.py`)

```python
class FrameSynchronizer:
    """
    CCTV와 ZED 프레임을 타임스탬프 기반으로 동기화
    """
    def __init__(self, tolerance_ms=100, max_buffer=60):
        self.cctv_buffer = deque(maxlen=max_buffer)
        self.zed_buffer = deque(maxlen=max_buffer)
        self.tolerance = timedelta(milliseconds=tolerance_ms)

    def add_cctv_frame(self, frame, timestamp):
        """CCTV 프레임 추가"""

    def add_zed_frame(self, rgb, depth, timestamp):
        """ZED 프레임 추가"""

    def get_synchronized_pair(self):
        """동기화된 프레임 쌍 반환"""
        # 타임스탬프가 tolerance 내에 있는 프레임 매칭
```

### 2. Multi-Modal Fusion Engine (`fusion/multimodal.py`)

```python
class MultiModalFusion:
    """
    2D CCTV + 3D ZED 데이터 통합
    """
    def __init__(self, calibration_data):
        self.calibration = calibration_data

    def map_2d_to_3d(self, bbox_2d, depth_map):
        """2D 바운딩 박스를 3D 좌표로 변환"""

    def match_objects(self, cctv_detections, zed_positions):
        """두 카메라에서 감지된 객체 매칭"""

    def enhance_tracking(self, person_id, cctv_data, zed_data):
        """Depth 정보로 추적 강화"""
```

### 3. Movement Tracker (`tracking/movement.py`)

```python
class MovementTracker:
    """
    3D 공간에서 객체 움직임 추적
    """
    def __init__(self):
        self.tracks = {}  # {object_id: [position_history]}

    def update(self, object_id, position_xyz, timestamp):
        """위치 업데이트"""

    def calculate_distance(self, object_id, time_window_sec=1.0):
        """이동 거리 계산 (m)"""

    def calculate_speed(self, object_id):
        """속도 계산 (m/s)"""

    def get_direction(self, object_id):
        """이동 방향 벡터 계산"""
```

### 4. Event Detection Engine (`events/detector.py`)

```python
class EventDetector:
    """
    이벤트 감지 및 룰 엔진
    """
    def __init__(self, rules_config):
        self.rules = self.load_rules(rules_config)

    def detect_zone_entry(self, position, zones):
        """구역 진입/이탈 감지"""

    def detect_idle(self, object_id, tracker, threshold_m=0.1, duration_sec=10):
        """정지 상태 감지"""

    def detect_fall(self, skeleton_data, depth_change):
        """넘어짐 감지"""

    def detect_distance_change(self, object_id, tracker, threshold_m=0.5):
        """거리 변화 감지"""
```

### 5. WebSocket Event Streamer (`api/websocket.py`)

```python
@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    실시간 이벤트 스트리밍
    """
    await websocket.accept()
    try:
        while True:
            event = await event_queue.get()
            await websocket.send_json({
                "type": event.type,
                "timestamp": event.timestamp.isoformat(),
                "camera_id": event.camera_id,
                "confidence": event.confidence,
                "position": event.position_xyz,
                "metadata": event.metadata
            })
    except WebSocketDisconnect:
        pass
```

## 📦 데이터베이스 스키마

### Events Table
```sql
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    camera_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'zone_entry', 'idle', 'fall', 'distance_change', etc.
    confidence REAL NOT NULL,
    position_x REAL,
    position_y REAL,
    position_z REAL,
    movement_distance REAL,
    movement_speed REAL,
    frame_url TEXT,
    metadata_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_type ON events(event_type);
```

### Positions Table (Position History)
```sql
CREATE TABLE positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    camera_id TEXT NOT NULL,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,
    distance_from_previous REAL,
    speed_ms REAL,
    direction_vector TEXT,  -- JSON: [dx, dy, dz]
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_positions_object_time ON positions(object_id, timestamp);
```

### Zones Table (ROI Configuration)
```sql
CREATE TABLE zones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    polygon_points TEXT NOT NULL,  -- JSON: [[x1,y1], [x2,y2], ...]
    rules_json TEXT,  -- Event rules for this zone
    enabled BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Calibration Table
```sql
CREATE TABLE calibration (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT UNIQUE NOT NULL,
    transform_matrix TEXT NOT NULL,  -- JSON: 4x4 transformation matrix
    pixel_to_meter_ratio REAL,
    calibration_date DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## 🎯 API 엔드포인트

### REST API

#### Events
- `GET /api/events/latest?limit=50` - 최근 이벤트 조회
- `GET /api/events/history?start_time=...&end_time=...` - 이벤트 히스토리
- `GET /api/events/{event_id}` - 특정 이벤트 상세 조회
- `GET /api/events/stats` - 이벤트 통계

#### Movement Tracking
- `GET /api/movement/tracking/{object_id}` - 객체 추적 정보
- `GET /api/movement/active` - 현재 추적 중인 객체 목록

#### Cameras
- `GET /api/cameras/status` - 카메라 상태 조회
- `POST /api/cameras/calibration` - 캘리브레이션 설정
- `GET /api/cameras/health` - 카메라 헬스 체크

#### Zones
- `GET /api/zones` - 모든 구역 조회
- `POST /api/zones` - 새 구역 생성
- `PUT /api/zones/{zone_id}` - 구역 수정
- `DELETE /api/zones/{zone_id}` - 구역 삭제

### WebSocket API

#### Real-time Events
- `WS /ws/events` - 실시간 이벤트 스트림
```json
{
  "type": "zone_entry",
  "timestamp": "2024-11-14T08:30:15.123Z",
  "camera_id": "zed_2i",
  "object_id": "person_001",
  "confidence": 0.95,
  "position": {"x": 1.5, "y": 0.3, "z": 2.1},
  "zone_name": "restricted_area",
  "metadata": {}
}
```

#### Real-time Tracking
- `WS /ws/tracking` - 실시간 위치 업데이트
```json
{
  "object_id": "person_001",
  "timestamp": "2024-11-14T08:30:15.123Z",
  "position": {"x": 1.5, "y": 0.3, "z": 2.1},
  "speed": 0.5,
  "direction": [0.7, 0.0, 0.7],
  "distance_moved": 0.3
}
```

## 🚀 성능 목표

- **처리 FPS**: 15-30 fps (CCTV + ZED 통합)
- **이벤트 탐지 지연**: < 300ms
- **GPU 사용률**: 50-70% (RTX 4090)
- **메모리 사용량**: < 8GB
- **WebSocket 지연**: < 50ms
- **데이터베이스 쓰기**: < 10ms/event

## 📋 MVP 단계 (2-4주)

### Week 1: Foundation
- [x] ZED + CCTV 프레임 수집 (완료)
- [ ] Frame Synchronizer 구현
- [ ] Database 스키마 생성
- [ ] WebSocket 기본 구조

### Week 2: Core Features
- [ ] Multi-Modal Fusion Engine
- [ ] Movement Tracker
- [ ] Event Detection Engine (Zone Entry, Idle)
- [ ] REST API 구현

### Week 3: Integration
- [ ] Frontend Event Dashboard
- [ ] Real-time WebSocket streaming
- [ ] Camera Calibration Tool

### Week 4: Polish & Testing
- [ ] Performance optimization
- [ ] UI/UX improvements
- [ ] Integration testing
- [ ] Documentation

## 🔮 확장 단계

### Advanced Features
- Fall detection (skeleton + depth)
- Activity recognition (sitting/standing/bending)
- Anomaly detection (ML-based)
- Multi-camera fusion (4+ cameras)
- Heat map visualization
- Predictive alerts

### ML Models
- Custom YOLO fine-tuning
- Action recognition (temporal CNN)
- Anomaly detection (VAE/Autoencoder)

## 🔒 보안 고려사항

- WebSocket 인증 토큰
- API 접근 제어 (JWT)
- 이벤트 데이터 암호화
- 스트림 접근 권한 관리
- 로그 암호화 저장

## 📝 다음 단계

1. **Frame Synchronizer 구현** - CCTV와 ZED 타임스탬프 동기화
2. **Database 초기화** - SQLite 스키마 생성
3. **Movement Tracker** - 3D 위치 추적 시스템
4. **Event Engine** - 기본 이벤트 감지 룰
5. **WebSocket Integration** - 실시간 이벤트 스트리밍
