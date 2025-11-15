"""
Database Manager for Multimodal Vision AI System
SQLite database initialization and management
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLite 데이터베이스 관리자
    - 스키마 초기화
    - CRUD 연산
    - 트랜잭션 관리
    """

    def __init__(self, db_path: str = "data/events.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection: Optional[sqlite3.Connection] = None
        self.initialize_database()

    def initialize_database(self):
        """데이터베이스 초기화 및 스키마 생성"""
        schema_path = Path(__file__).parent / "schema.sql"

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")

        logger.info(f"Initializing database at {self.db_path}")

        with self.get_connection() as conn:
            with open(schema_path, "r") as f:
                schema_sql = f.read()
                conn.executescript(schema_sql)
            conn.commit()

        logger.info("Database initialized successfully")

    @contextmanager
    def get_connection(self):
        """컨텍스트 매니저로 데이터베이스 연결 제공"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 딕셔너리 스타일 접근
        try:
            yield conn
        finally:
            conn.close()

    # ==================== Events ====================

    def insert_event(
        self,
        timestamp: datetime,
        camera_id: str,
        event_type: str,
        confidence: float,
        position_xyz: Optional[tuple] = None,
        movement_distance: Optional[float] = None,
        movement_speed: Optional[float] = None,
        movement_direction: Optional[List[float]] = None,
        object_id: Optional[str] = None,
        object_type: Optional[str] = None,
        zone_id: Optional[int] = None,
        zone_name: Optional[str] = None,
        frame_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> int:
        """이벤트 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO events (
                    timestamp, camera_id, event_type, confidence,
                    position_x, position_y, position_z,
                    movement_distance, movement_speed, movement_direction,
                    object_id, object_type, zone_id, zone_name,
                    frame_url, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp.isoformat(),
                    camera_id,
                    event_type,
                    confidence,
                    position_xyz[0] if position_xyz else None,
                    position_xyz[1] if position_xyz else None,
                    position_xyz[2] if position_xyz else None,
                    movement_distance,
                    movement_speed,
                    json.dumps(movement_direction) if movement_direction else None,
                    object_id,
                    object_type,
                    zone_id,
                    zone_name,
                    frame_url,
                    json.dumps(metadata) if metadata else None,
                ),
            )

            event_id = cursor.lastrowid
            conn.commit()

            logger.debug(
                f"Inserted event {event_id}: {event_type} on {camera_id} at {timestamp}"
            )
            return event_id

    def get_latest_events(self, limit: int = 50, event_type: Optional[str] = None) -> List[Dict]:
        """최근 이벤트 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if event_type:
                cursor.execute(
                    """
                    SELECT * FROM recent_events
                    WHERE event_type = ?
                    LIMIT ?
                    """,
                    (event_type, limit),
                )
            else:
                cursor.execute("SELECT * FROM recent_events LIMIT ?", (limit,))

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_events_by_time_range(
        self, start_time: datetime, end_time: datetime, camera_id: Optional[str] = None
    ) -> List[Dict]:
        """시간 범위로 이벤트 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if camera_id:
                cursor.execute(
                    """
                    SELECT * FROM events
                    WHERE timestamp BETWEEN ? AND ?
                    AND camera_id = ?
                    ORDER BY timestamp DESC
                    """,
                    (start_time.isoformat(), end_time.isoformat(), camera_id),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM events
                    WHERE timestamp BETWEEN ? AND ?
                    ORDER BY timestamp DESC
                    """,
                    (start_time.isoformat(), end_time.isoformat()),
                )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_event_statistics(self) -> Dict[str, Any]:
        """이벤트 통계 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Total events
            cursor.execute("SELECT COUNT(*) as total FROM events")
            total = cursor.fetchone()["total"]

            # Events by type
            cursor.execute(
                """
                SELECT event_type, COUNT(*) as count
                FROM events
                GROUP BY event_type
                ORDER BY count DESC
                """
            )
            by_type = {row["event_type"]: row["count"] for row in cursor.fetchall()}

            # Events in last hour
            cursor.execute(
                """
                SELECT COUNT(*) as count
                FROM events
                WHERE timestamp > datetime('now', '-1 hour')
                """
            )
            last_hour = cursor.fetchone()["count"]

            return {"total": total, "by_type": by_type, "last_hour": last_hour}

    # ==================== Positions ====================

    def insert_position(
        self,
        object_id: str,
        timestamp: datetime,
        camera_id: str,
        xyz: tuple,
        distance_from_previous: Optional[float] = None,
        speed_ms: Optional[float] = None,
        direction_vector: Optional[List[float]] = None,
        bbox: Optional[tuple] = None,
        detection_confidence: Optional[float] = None,
    ) -> int:
        """위치 데이터 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO positions (
                    object_id, timestamp, camera_id,
                    x, y, z,
                    distance_from_previous, speed_ms, direction_vector,
                    bbox_x1, bbox_y1, bbox_x2, bbox_y2,
                    detection_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    object_id,
                    timestamp.isoformat(),
                    camera_id,
                    xyz[0],
                    xyz[1],
                    xyz[2],
                    distance_from_previous,
                    speed_ms,
                    json.dumps(direction_vector) if direction_vector else None,
                    bbox[0] if bbox else None,
                    bbox[1] if bbox else None,
                    bbox[2] if bbox else None,
                    bbox[3] if bbox else None,
                    detection_confidence,
                ),
            )

            position_id = cursor.lastrowid
            conn.commit()

            return position_id

    def get_object_position_history(
        self, object_id: str, limit: int = 100
    ) -> List[Dict]:
        """객체 위치 히스토리 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM positions
                WHERE object_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (object_id, limit),
            )

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ==================== Objects ====================

    def insert_or_update_object(
        self,
        object_id: str,
        object_type: str,
        first_seen: datetime,
        current_camera_id: str,
        current_position: tuple,
    ) -> None:
        """객체 삽입 또는 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO objects (
                    object_id, object_type, first_seen, last_seen,
                    current_camera_id, current_position, current_status
                ) VALUES (?, ?, ?, ?, ?, ?, 'active')
                ON CONFLICT(object_id) DO UPDATE SET
                    last_seen = excluded.last_seen,
                    current_camera_id = excluded.current_camera_id,
                    current_position = excluded.current_position,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    object_id,
                    object_type,
                    first_seen.isoformat(),
                    first_seen.isoformat(),
                    current_camera_id,
                    json.dumps(list(current_position)),
                ),
            )

            conn.commit()

    def get_active_objects(self) -> List[Dict]:
        """현재 활성 객체 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM active_objects")

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # ==================== Zones ====================

    def insert_zone(
        self,
        name: str,
        camera_id: str,
        polygon_points: List[List[int]],
        zone_type: str = "monitoring",
        rules: Optional[Dict] = None,
    ) -> int:
        """구역 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO zones (
                    name, camera_id, polygon_points, zone_type, rules_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    camera_id,
                    json.dumps(polygon_points),
                    zone_type,
                    json.dumps(rules) if rules else None,
                ),
            )

            zone_id = cursor.lastrowid
            conn.commit()

            logger.info(f"Inserted zone {zone_id}: {name} on {camera_id}")
            return zone_id

    def get_zones(self, camera_id: Optional[str] = None) -> List[Dict]:
        """구역 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if camera_id:
                cursor.execute(
                    "SELECT * FROM zones WHERE camera_id = ? AND enabled = 1", (camera_id,)
                )
            else:
                cursor.execute("SELECT * FROM zones WHERE enabled = 1")

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_zone(self, zone_id: int, updates: Dict) -> None:
        """구역 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Build SET clause dynamically
            set_parts = []
            values = []
            for key, value in updates.items():
                if key in ["polygon_points", "rules_json", "bounds_3d"]:
                    set_parts.append(f"{key} = ?")
                    values.append(json.dumps(value))
                else:
                    set_parts.append(f"{key} = ?")
                    values.append(value)

            set_parts.append("updated_at = CURRENT_TIMESTAMP")
            values.append(zone_id)

            query = f"UPDATE zones SET {', '.join(set_parts)} WHERE zone_id = ?"
            cursor.execute(query, values)
            conn.commit()

    # ==================== Cameras ====================

    def insert_or_update_camera(
        self,
        camera_id: str,
        camera_name: str,
        camera_type: str,
        stream_url: Optional[str] = None,
        connection_type: Optional[str] = None,
        resolution: Optional[Dict] = None,
        fps: Optional[int] = None,
    ) -> None:
        """카메라 삽입 또는 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO cameras (
                    camera_id, camera_name, camera_type,
                    stream_url, connection_type, resolution, fps
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET
                    camera_name = excluded.camera_name,
                    stream_url = excluded.stream_url,
                    connection_type = excluded.connection_type,
                    resolution = excluded.resolution,
                    fps = excluded.fps,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    camera_id,
                    camera_name,
                    camera_type,
                    stream_url,
                    connection_type,
                    json.dumps(resolution) if resolution else None,
                    fps,
                ),
            )

            conn.commit()

    def get_cameras(self) -> List[Dict]:
        """모든 카메라 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM cameras")

            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def update_camera_status(self, camera_id: str, status: str) -> None:
        """카메라 상태 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE cameras
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE camera_id = ?
                """,
                (status, camera_id),
            )

            conn.commit()

    # ==================== System Config ====================

    def get_config(self, key: str) -> Any:
        """설정 값 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT config_value, config_type FROM system_config WHERE config_key = ?",
                (key,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            value = row["config_value"]
            config_type = row["config_type"]

            # Type conversion
            if config_type == "integer":
                return int(value)
            elif config_type == "float":
                return float(value)
            elif config_type == "boolean":
                return value.lower() == "true"
            elif config_type == "json":
                return json.loads(value)
            else:
                return value

    def set_config(self, key: str, value: Any, config_type: str = "string") -> None:
        """설정 값 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            if config_type == "json":
                value_str = json.dumps(value)
            else:
                value_str = str(value)

            cursor.execute(
                """
                INSERT INTO system_config (config_key, config_value, config_type)
                VALUES (?, ?, ?)
                ON CONFLICT(config_key) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value_str, config_type),
            )

            conn.commit()

    # ==================== Cleanup ====================

    def cleanup_old_positions(self, days: int = 30) -> int:
        """오래된 위치 데이터 정리"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM positions
                WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                (days,),
            )

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted_count} old position records")
            return deleted_count


# Global database instance
_db_instance: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """싱글톤 데이터베이스 인스턴스 반환"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
