"""
Event Detection Engine for Multimodal Vision AI System
이벤트 감지 및 룰 엔진
"""

import numpy as np
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Callable, Any, Tuple
from shapely.geometry import Point, Polygon
import logging

logger = logging.getLogger(__name__)


@dataclass
class Zone:
    """관심 영역 (Region of Interest)"""

    zone_id: int
    name: str
    camera_id: str
    polygon: Polygon  # 2D polygon in image coordinates
    bounds_3d: Optional[Dict] = None  # {min: [x,y,z], max: [x,y,z]}
    rules: Dict = field(default_factory=dict)
    zone_type: str = "monitoring"  # 'restricted', 'monitoring', 'safe', 'hazard'
    priority: int = 5  # 1-10
    enabled: bool = True


@dataclass
class Event:
    """이벤트 데이터"""

    event_id: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)
    camera_id: str = ""
    event_type: str = ""  # 'zone_entry', 'zone_exit', 'idle', 'fall', etc.
    confidence: float = 1.0
    position_xyz: Optional[Tuple[float, float, float]] = None
    movement_distance: Optional[float] = None
    movement_speed: Optional[float] = None
    movement_direction: Optional[List[float]] = None
    object_id: Optional[str] = None
    object_type: Optional[str] = None
    zone_id: Optional[int] = None
    zone_name: Optional[str] = None
    frame_url: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "camera_id": self.camera_id,
            "event_type": self.event_type,
            "confidence": self.confidence,
            "position_xyz": self.position_xyz,
            "movement_distance": self.movement_distance,
            "movement_speed": self.movement_speed,
            "movement_direction": self.movement_direction,
            "object_id": self.object_id,
            "object_type": self.object_type,
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "frame_url": self.frame_url,
            "metadata": self.metadata,
        }


class EventDetector:
    """
    이벤트 감지 및 룰 엔진

    Supported Event Types:
    - zone_entry: 구역 진입
    - zone_exit: 구역 이탈
    - idle: 정지 상태
    - fall: 넘어짐
    - distance_change: 거리 변화
    - speed_alert: 속도 경고
    - new_object: 신규 객체 등장
    """

    def __init__(
        self,
        idle_threshold_m: float = 0.1,
        idle_duration_sec: float = 10.0,
        distance_alert_threshold_m: float = 0.5,
        speed_alert_threshold_ms: float = 2.0,
        confidence_threshold: float = 0.7,
    ):
        """
        Args:
            idle_threshold_m: 정지 상태 이동 거리 임계값 (m)
            idle_duration_sec: 정지 상태 지속 시간 임계값 (초)
            distance_alert_threshold_m: 거리 변화 경고 임계값 (m)
            speed_alert_threshold_ms: 속도 경고 임계값 (m/s)
            confidence_threshold: 이벤트 발생 최소 신뢰도
        """
        self.idle_threshold_m = idle_threshold_m
        self.idle_duration_sec = idle_duration_sec
        self.distance_alert_threshold_m = distance_alert_threshold_m
        self.speed_alert_threshold_ms = speed_alert_threshold_ms
        self.confidence_threshold = confidence_threshold

        # Zones storage
        self.zones: Dict[int, Zone] = {}

        # Object state tracking (for zone entry/exit)
        self.object_zone_states: Dict[str, Optional[int]] = {}  # {object_id: zone_id}

        # Event history (for deduplication)
        self.recent_events: List[Event] = []
        self.max_recent_events = 100

        # Custom event handlers
        self.event_handlers: Dict[str, List[Callable]] = {}

        logger.info("EventDetector initialized")

    def add_zone(
        self,
        zone_id: int,
        name: str,
        camera_id: str,
        polygon_points: List[List[float]],
        zone_type: str = "monitoring",
        rules: Optional[Dict] = None,
        bounds_3d: Optional[Dict] = None,
    ) -> Zone:
        """
        구역 추가

        Args:
            zone_id: 구역 ID
            name: 구역 이름
            camera_id: 카메라 ID
            polygon_points: 2D 다각형 좌표 [[x1,y1], [x2,y2], ...]
            zone_type: 구역 타입
            rules: 이벤트 룰 설정
            bounds_3d: 3D 경계 (optional)

        Returns:
            Zone 객체
        """
        polygon = Polygon(polygon_points)

        zone = Zone(
            zone_id=zone_id,
            name=name,
            camera_id=camera_id,
            polygon=polygon,
            zone_type=zone_type,
            rules=rules or {},
            bounds_3d=bounds_3d,
        )

        self.zones[zone_id] = zone
        logger.info(f"Zone added: {name} (ID: {zone_id}, Type: {zone_type})")

        return zone

    def remove_zone(self, zone_id: int) -> bool:
        """구역 제거"""
        if zone_id in self.zones:
            zone = self.zones[zone_id]
            del self.zones[zone_id]
            logger.info(f"Zone removed: {zone.name} (ID: {zone_id})")
            return True
        return False

    def get_zones(self, camera_id: Optional[str] = None) -> List[Zone]:
        """구역 조회"""
        if camera_id:
            return [z for z in self.zones.values() if z.camera_id == camera_id and z.enabled]
        return [z for z in self.zones.values() if z.enabled]

    def detect_zone_entry_exit(
        self,
        object_id: str,
        position_2d: Tuple[float, float],
        position_3d: Optional[Tuple[float, float, float]] = None,
        camera_id: str = "default",
        object_type: str = "unknown",
    ) -> Optional[Event]:
        """
        구역 진입/이탈 감지

        Args:
            object_id: 객체 ID
            position_2d: 2D 위치 (image coordinates)
            position_3d: 3D 위치 (optional)
            camera_id: 카메라 ID
            object_type: 객체 타입

        Returns:
            Event 또는 None
        """
        point = Point(position_2d)

        # Find current zone
        current_zone = None
        for zone in self.zones.values():
            if zone.camera_id == camera_id and zone.enabled:
                if zone.polygon.contains(point):
                    current_zone = zone
                    break

        # Get previous zone state
        previous_zone_id = self.object_zone_states.get(object_id)

        # Check for zone change
        event = None
        current_zone_id = current_zone.zone_id if current_zone else None

        if current_zone_id != previous_zone_id:
            if current_zone_id is not None:
                # Zone entry
                event = Event(
                    timestamp=datetime.now(),
                    camera_id=camera_id,
                    event_type="zone_entry",
                    confidence=0.95,
                    position_xyz=position_3d,
                    object_id=object_id,
                    object_type=object_type,
                    zone_id=current_zone.zone_id,
                    zone_name=current_zone.name,
                    metadata={
                        "zone_type": current_zone.zone_type,
                        "zone_priority": current_zone.priority,
                    },
                )

                logger.info(
                    f"Zone entry detected: {object_id} → {current_zone.name}"
                )

            elif previous_zone_id is not None:
                # Zone exit
                previous_zone = self.zones.get(previous_zone_id)
                if previous_zone:
                    event = Event(
                        timestamp=datetime.now(),
                        camera_id=camera_id,
                        event_type="zone_exit",
                        confidence=0.95,
                        position_xyz=position_3d,
                        object_id=object_id,
                        object_type=object_type,
                        zone_id=previous_zone.zone_id,
                        zone_name=previous_zone.name,
                        metadata={
                            "zone_type": previous_zone.zone_type,
                            "zone_priority": previous_zone.priority,
                        },
                    )

                    logger.info(
                        f"Zone exit detected: {object_id} ← {previous_zone.name}"
                    )

            # Update state
            self.object_zone_states[object_id] = current_zone_id

        return event

    def detect_idle(
        self,
        object_id: str,
        is_moving: bool,
        idle_duration: float,
        position_3d: Optional[Tuple[float, float, float]] = None,
        camera_id: str = "default",
        object_type: str = "unknown",
    ) -> Optional[Event]:
        """
        정지 상태 감지

        Args:
            object_id: 객체 ID
            is_moving: 현재 움직이는 중인지 여부
            idle_duration: 정지 지속 시간 (초)
            position_3d: 3D 위치
            camera_id: 카메라 ID
            object_type: 객체 타입

        Returns:
            Event 또는 None
        """
        if not is_moving and idle_duration >= self.idle_duration_sec:
            event = Event(
                timestamp=datetime.now(),
                camera_id=camera_id,
                event_type="idle",
                confidence=0.9,
                position_xyz=position_3d,
                object_id=object_id,
                object_type=object_type,
                metadata={
                    "idle_duration_sec": idle_duration,
                    "threshold_sec": self.idle_duration_sec,
                },
            )

            logger.info(
                f"Idle detected: {object_id} (duration: {idle_duration:.1f}s)"
            )

            return event

        return None

    def detect_distance_change(
        self,
        object_id: str,
        distance_moved: float,
        position_3d: Optional[Tuple[float, float, float]] = None,
        camera_id: str = "default",
        object_type: str = "unknown",
    ) -> Optional[Event]:
        """
        거리 변화 감지

        Args:
            object_id: 객체 ID
            distance_moved: 이동 거리 (m)
            position_3d: 3D 위치
            camera_id: 카메라 ID
            object_type: 객체 타입

        Returns:
            Event 또는 None
        """
        if distance_moved >= self.distance_alert_threshold_m:
            event = Event(
                timestamp=datetime.now(),
                camera_id=camera_id,
                event_type="distance_change",
                confidence=0.95,
                position_xyz=position_3d,
                movement_distance=distance_moved,
                object_id=object_id,
                object_type=object_type,
                metadata={
                    "distance_m": distance_moved,
                    "threshold_m": self.distance_alert_threshold_m,
                },
            )

            logger.info(
                f"Distance change detected: {object_id} ({distance_moved:.2f}m)"
            )

            return event

        return None

    def detect_speed_alert(
        self,
        object_id: str,
        speed_ms: float,
        direction: Optional[np.ndarray] = None,
        position_3d: Optional[Tuple[float, float, float]] = None,
        camera_id: str = "default",
        object_type: str = "unknown",
    ) -> Optional[Event]:
        """
        속도 경고 감지

        Args:
            object_id: 객체 ID
            speed_ms: 속도 (m/s)
            direction: 방향 벡터
            position_3d: 3D 위치
            camera_id: 카메라 ID
            object_type: 객체 타입

        Returns:
            Event 또는 None
        """
        if speed_ms >= self.speed_alert_threshold_ms:
            event = Event(
                timestamp=datetime.now(),
                camera_id=camera_id,
                event_type="speed_alert",
                confidence=0.9,
                position_xyz=position_3d,
                movement_speed=speed_ms,
                movement_direction=direction.tolist() if direction is not None else None,
                object_id=object_id,
                object_type=object_type,
                metadata={
                    "speed_ms": speed_ms,
                    "threshold_ms": self.speed_alert_threshold_ms,
                },
            )

            logger.warning(
                f"Speed alert: {object_id} ({speed_ms:.2f}m/s, threshold: {self.speed_alert_threshold_ms}m/s)"
            )

            return event

        return None

    def detect_fall(
        self,
        object_id: str,
        skeleton_data: Optional[Dict] = None,
        depth_change: Optional[float] = None,
        position_3d: Optional[Tuple[float, float, float]] = None,
        camera_id: str = "default",
        object_type: str = "person",
    ) -> Optional[Event]:
        """
        넘어짐 감지

        Args:
            object_id: 객체 ID
            skeleton_data: 스켈레톤 데이터 (angles, keypoints)
            depth_change: Depth 급변량
            position_3d: 3D 위치
            camera_id: 카메라 ID
            object_type: 객체 타입

        Returns:
            Event 또는 None
        """
        # Simplified fall detection logic
        fall_detected = False
        confidence = 0.0

        # Check skeleton angle (if available)
        if skeleton_data and "body_angle" in skeleton_data:
            body_angle = skeleton_data["body_angle"]
            if body_angle < 45:  # Horizontal orientation
                fall_detected = True
                confidence = 0.85

        # Check depth change (sudden vertical drop)
        if depth_change and depth_change > 0.5:  # 50cm drop
            fall_detected = True
            confidence = max(confidence, 0.8)

        if fall_detected:
            event = Event(
                timestamp=datetime.now(),
                camera_id=camera_id,
                event_type="fall",
                confidence=confidence,
                position_xyz=position_3d,
                object_id=object_id,
                object_type=object_type,
                metadata={
                    "skeleton_data": skeleton_data,
                    "depth_change": depth_change,
                },
            )

            logger.warning(f"Fall detected: {object_id} (confidence: {confidence})")

            return event

        return None

    def register_event(self, event: Event) -> None:
        """이벤트 등록 및 히스토리 관리"""
        self.recent_events.append(event)

        # Trim history
        if len(self.recent_events) > self.max_recent_events:
            self.recent_events = self.recent_events[-self.max_recent_events :]

        # Trigger handlers
        if event.event_type in self.event_handlers:
            for handler in self.event_handlers[event.event_type]:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

    def add_event_handler(
        self, event_type: str, handler: Callable[[Event], None]
    ) -> None:
        """이벤트 핸들러 등록"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []

        self.event_handlers[event_type].append(handler)
        logger.info(f"Event handler added for: {event_type}")

    def get_recent_events(self, limit: Optional[int] = None) -> List[Event]:
        """최근 이벤트 조회"""
        if limit:
            return self.recent_events[-limit:]
        return self.recent_events.copy()
