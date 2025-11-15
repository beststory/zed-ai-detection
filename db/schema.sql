-- 멀티모달 비전 AI 시스템 데이터베이스 스키마
-- SQLite Database Schema

-- Events Table: 감지된 모든 이벤트 저장
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    camera_id TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'zone_entry', 'zone_exit', 'idle', 'fall', 'distance_change', 'speed_alert', 'new_object'
    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),

    -- 3D Position data
    position_x REAL,
    position_y REAL,
    position_z REAL,

    -- Movement data
    movement_distance REAL,  -- meters
    movement_speed REAL,     -- m/s
    movement_direction TEXT, -- JSON: [dx, dy, dz]

    -- Object tracking
    object_id TEXT,
    object_type TEXT,  -- 'person', 'vehicle', 'object'

    -- Associated zone (if applicable)
    zone_id INTEGER,
    zone_name TEXT,

    -- Media references
    frame_url TEXT,
    video_segment_url TEXT,

    -- Additional metadata
    metadata_json TEXT,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (zone_id) REFERENCES zones(zone_id)
);

-- Indexes for fast event queries
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_camera ON events(camera_id);
CREATE INDEX IF NOT EXISTS idx_events_object ON events(object_id);
CREATE INDEX IF NOT EXISTS idx_events_zone ON events(zone_id);

-- Positions Table: 객체 위치 히스토리 (고빈도 데이터)
CREATE TABLE IF NOT EXISTS positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    camera_id TEXT NOT NULL,

    -- 3D coordinates
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL,

    -- Movement metrics
    distance_from_previous REAL,  -- meters
    speed_ms REAL,                 -- m/s
    direction_vector TEXT,         -- JSON: [dx, dy, dz]

    -- 2D bounding box (from detection)
    bbox_x1 INTEGER,
    bbox_y1 INTEGER,
    bbox_x2 INTEGER,
    bbox_y2 INTEGER,

    -- Detection confidence
    detection_confidence REAL,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for position tracking queries
CREATE INDEX IF NOT EXISTS idx_positions_object_time ON positions(object_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_positions_camera_time ON positions(camera_id, timestamp DESC);

-- Zones Table: ROI (Region of Interest) 설정
CREATE TABLE IF NOT EXISTS zones (
    zone_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    camera_id TEXT NOT NULL,

    -- Zone geometry (2D polygon in image coordinates)
    polygon_points TEXT NOT NULL,  -- JSON: [[x1,y1], [x2,y2], ...]

    -- 3D zone bounds (optional, for ZED camera)
    bounds_3d TEXT,  -- JSON: {min: [x,y,z], max: [x,y,z]}

    -- Event rules configuration
    rules_json TEXT,  -- JSON: {entry: true, exit: true, idle_threshold_sec: 10, ...}

    -- Zone properties
    zone_type TEXT,  -- 'restricted', 'monitoring', 'safe', 'hazard'
    priority INTEGER DEFAULT 5,  -- 1-10, higher = more important
    color TEXT DEFAULT '#FF0000',  -- UI display color

    -- Status
    enabled BOOLEAN DEFAULT 1,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Calibration Table: 카메라 캘리브레이션 데이터
CREATE TABLE IF NOT EXISTS calibration (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT UNIQUE NOT NULL,

    -- Transformation matrix (2D→3D mapping)
    transform_matrix TEXT NOT NULL,  -- JSON: 4x4 or 3x3 matrix

    -- Calibration parameters
    focal_length REAL,
    principal_point TEXT,  -- JSON: [cx, cy]
    distortion_coeffs TEXT,  -- JSON: [k1, k2, p1, p2, k3]

    -- Pixel to meter conversion
    pixel_to_meter_ratio REAL,

    -- Reference points used for calibration
    reference_points TEXT,  -- JSON: [{pixel: [x,y], world: [X,Y,Z]}, ...]

    -- Calibration quality metrics
    reprojection_error REAL,
    calibration_quality TEXT,  -- 'excellent', 'good', 'acceptable', 'poor'

    -- Calibration metadata
    calibration_date DATETIME NOT NULL,
    calibrated_by TEXT,
    notes TEXT,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Objects Table: 추적 중인 객체 정보
CREATE TABLE IF NOT EXISTS objects (
    object_id TEXT PRIMARY KEY,
    object_type TEXT NOT NULL,  -- 'person', 'vehicle', 'object'

    -- First/Last seen
    first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL,

    -- Tracking statistics
    total_distance_traveled REAL DEFAULT 0.0,  -- meters
    max_speed REAL DEFAULT 0.0,  -- m/s
    avg_speed REAL DEFAULT 0.0,  -- m/s
    time_in_zones TEXT,  -- JSON: {zone_name: duration_sec, ...}

    -- Current state
    current_camera_id TEXT,
    current_position TEXT,  -- JSON: [x, y, z]
    current_status TEXT,  -- 'active', 'idle', 'lost'

    -- Event counts
    event_count INTEGER DEFAULT 0,
    alert_count INTEGER DEFAULT 0,

    -- Metadata
    metadata_json TEXT,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Cameras Table: 카메라 정보 및 상태
CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    camera_name TEXT NOT NULL,
    camera_type TEXT NOT NULL,  -- 'cctv', 'zed', 'depth'

    -- Connection info
    stream_url TEXT,
    connection_type TEXT,  -- 'rtsp', 'zmq', 'usb'

    -- Camera properties
    resolution TEXT,  -- JSON: {width: 1920, height: 1080}
    fps INTEGER,

    -- Position and orientation
    position_3d TEXT,  -- JSON: [x, y, z] in world coordinates
    orientation TEXT,  -- JSON: [roll, pitch, yaw] in degrees

    -- Status
    status TEXT DEFAULT 'active',  -- 'active', 'inactive', 'error'
    last_frame_timestamp DATETIME,
    uptime_seconds INTEGER DEFAULT 0,

    -- Health metrics
    frame_drop_rate REAL DEFAULT 0.0,
    avg_latency_ms REAL DEFAULT 0.0,
    error_count INTEGER DEFAULT 0,

    -- Audit
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- System Configuration Table
CREATE TABLE IF NOT EXISTS system_config (
    config_key TEXT PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type TEXT NOT NULL,  -- 'string', 'integer', 'float', 'boolean', 'json'
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert default configuration
INSERT OR IGNORE INTO system_config (config_key, config_value, config_type, description) VALUES
    ('frame_sync_tolerance_ms', '100', 'integer', 'Frame synchronization tolerance in milliseconds'),
    ('max_frame_buffer', '60', 'integer', 'Maximum frames in sync buffer'),
    ('event_confidence_threshold', '0.7', 'float', 'Minimum confidence for event triggers'),
    ('idle_threshold_sec', '10', 'integer', 'Seconds before idle event triggered'),
    ('distance_alert_threshold_m', '0.5', 'float', 'Distance change alert threshold in meters'),
    ('speed_alert_threshold_ms', '2.0', 'float', 'Speed alert threshold in m/s'),
    ('tracking_lost_timeout_sec', '5', 'integer', 'Seconds before object tracking is lost'),
    ('websocket_broadcast_fps', '10', 'integer', 'WebSocket event broadcast rate'),
    ('database_cleanup_days', '30', 'integer', 'Days to keep old position data'),
    ('enable_fall_detection', 'true', 'boolean', 'Enable fall detection feature'),
    ('enable_zone_alerts', 'true', 'boolean', 'Enable zone entry/exit alerts'),
    ('max_tracked_objects', '50', 'integer', 'Maximum simultaneous tracked objects');

-- Views for common queries

-- Recent Events View
CREATE VIEW IF NOT EXISTS recent_events AS
SELECT
    e.event_id,
    e.timestamp,
    e.event_type,
    e.camera_id,
    e.object_id,
    e.confidence,
    e.position_x,
    e.position_y,
    e.position_z,
    e.movement_distance,
    e.movement_speed,
    e.zone_name,
    c.camera_name
FROM events e
LEFT JOIN cameras c ON e.camera_id = c.camera_id
ORDER BY e.timestamp DESC
LIMIT 100;

-- Active Objects View
CREATE VIEW IF NOT EXISTS active_objects AS
SELECT
    o.object_id,
    o.object_type,
    o.current_camera_id,
    o.current_position,
    o.current_status,
    o.last_seen,
    c.camera_name,
    CAST((julianday('now') - julianday(o.last_seen)) * 86400 AS INTEGER) AS seconds_since_seen
FROM objects o
LEFT JOIN cameras c ON o.current_camera_id = c.camera_id
WHERE o.current_status = 'active'
ORDER BY o.last_seen DESC;

-- Zone Statistics View
CREATE VIEW IF NOT EXISTS zone_statistics AS
SELECT
    z.zone_id,
    z.name AS zone_name,
    z.zone_type,
    COUNT(DISTINCT e.object_id) AS unique_visitors,
    COUNT(e.event_id) AS total_events,
    AVG(CASE WHEN e.event_type = 'idle' THEN 1 ELSE 0 END) AS idle_rate,
    MAX(e.timestamp) AS last_event_time
FROM zones z
LEFT JOIN events e ON z.zone_id = e.zone_id
GROUP BY z.zone_id
ORDER BY total_events DESC;

-- Triggers for automatic updates

-- Update objects.last_seen when new position is inserted
CREATE TRIGGER IF NOT EXISTS update_object_last_seen
AFTER INSERT ON positions
BEGIN
    UPDATE objects
    SET
        last_seen = NEW.timestamp,
        current_camera_id = NEW.camera_id,
        current_position = json_array(NEW.x, NEW.y, NEW.z),
        updated_at = CURRENT_TIMESTAMP
    WHERE object_id = NEW.object_id;
END;

-- Update objects.event_count when new event is created
CREATE TRIGGER IF NOT EXISTS update_object_event_count
AFTER INSERT ON events
BEGIN
    UPDATE objects
    SET
        event_count = event_count + 1,
        alert_count = alert_count + CASE
            WHEN NEW.event_type IN ('fall', 'speed_alert', 'zone_entry') THEN 1
            ELSE 0
        END,
        updated_at = CURRENT_TIMESTAMP
    WHERE object_id = NEW.object_id;
END;

-- Update cameras.last_frame_timestamp
CREATE TRIGGER IF NOT EXISTS update_camera_last_frame
AFTER INSERT ON positions
BEGIN
    UPDATE cameras
    SET
        last_frame_timestamp = NEW.timestamp,
        updated_at = CURRENT_TIMESTAMP
    WHERE camera_id = NEW.camera_id;
END;
