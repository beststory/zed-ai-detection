"""
3D Movement Tracker for Multimodal Vision AI System
객체의 3D 공간 움직임 추적 및 분석
"""

import numpy as np
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
from collections import deque
import logging

logger = logging.getLogger(__name__)


@dataclass
class Position3D:
    """3D 위치 데이터"""

    x: float  # meters
    y: float  # meters
    z: float  # meters
    timestamp: datetime
    confidence: float = 1.0

    def to_array(self) -> np.ndarray:
        """NumPy 배열로 변환"""
        return np.array([self.x, self.y, self.z])

    def distance_to(self, other: "Position3D") -> float:
        """다른 위치까지의 유클리드 거리 (m)"""
        return np.linalg.norm(self.to_array() - other.to_array())


@dataclass
class MovementMetrics:
    """움직임 측정 지표"""

    total_distance: float = 0.0  # meters
    avg_speed: float = 0.0  # m/s
    max_speed: float = 0.0  # m/s
    current_speed: float = 0.0  # m/s
    direction_vector: Optional[np.ndarray] = None  # Unit vector
    is_moving: bool = False
    idle_duration: float = 0.0  # seconds
    last_movement_time: Optional[datetime] = None


@dataclass
class ObjectTrack:
    """객체 추적 데이터"""

    object_id: str
    object_type: str = "unknown"
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    positions: deque = field(default_factory=lambda: deque(maxlen=100))
    metrics: MovementMetrics = field(default_factory=MovementMetrics)
    metadata: Dict = field(default_factory=dict)


class MovementTracker:
    """
    3D 공간에서 객체 움직임 추적

    Features:
    - 3D position history tracking
    - Distance & speed calculation
    - Direction vector estimation
    - Idle detection
    - Movement pattern analysis
    """

    def __init__(
        self,
        idle_threshold_m: float = 0.1,
        idle_duration_sec: float = 10.0,
        max_history: int = 100,
        smoothing_window: int = 5,
    ):
        """
        Args:
            idle_threshold_m: 정지 상태로 간주할 이동 거리 임계값 (m)
            idle_duration_sec: 정지 상태 지속 시간 임계값 (초)
            max_history: 위치 히스토리 최대 개수
            smoothing_window: 속도 계산 평활화 윈도우
        """
        self.idle_threshold_m = idle_threshold_m
        self.idle_duration_sec = idle_duration_sec
        self.max_history = max_history
        self.smoothing_window = smoothing_window

        # Track storage
        self.tracks: Dict[str, ObjectTrack] = {}

        # Statistics
        self.stats = {"total_objects_tracked": 0, "active_objects": 0}

        logger.info(
            f"MovementTracker initialized: idle_threshold={idle_threshold_m}m, "
            f"idle_duration={idle_duration_sec}s"
        )

    def update(
        self,
        object_id: str,
        position_xyz: Tuple[float, float, float],
        timestamp: Optional[datetime] = None,
        object_type: str = "unknown",
        confidence: float = 1.0,
    ) -> MovementMetrics:
        """
        객체 위치 업데이트

        Args:
            object_id: 객체 고유 ID
            position_xyz: 3D 좌표 (x, y, z) in meters
            timestamp: 타임스탬프 (None이면 현재 시간)
            object_type: 객체 타입
            confidence: 위치 신뢰도

        Returns:
            MovementMetrics: 업데이트된 움직임 지표
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Create position object
        position = Position3D(
            x=position_xyz[0],
            y=position_xyz[1],
            z=position_xyz[2],
            timestamp=timestamp,
            confidence=confidence,
        )

        # Get or create track
        if object_id not in self.tracks:
            self.tracks[object_id] = ObjectTrack(
                object_id=object_id,
                object_type=object_type,
                first_seen=timestamp,
                positions=deque(maxlen=self.max_history),
            )
            self.stats["total_objects_tracked"] += 1
            logger.info(f"New object track created: {object_id} ({object_type})")

        track = self.tracks[object_id]

        # Add position
        track.positions.append(position)
        track.last_seen = timestamp

        # Update metrics
        self._update_metrics(track)

        logger.debug(
            f"Object {object_id} updated: pos=({position.x:.2f}, {position.y:.2f}, {position.z:.2f}), "
            f"speed={track.metrics.current_speed:.2f}m/s"
        )

        return track.metrics

    def _update_metrics(self, track: ObjectTrack) -> None:
        """움직임 지표 업데이트"""
        if len(track.positions) < 2:
            return

        # Get recent positions
        recent_positions = list(track.positions)[-self.smoothing_window :]

        # Calculate total distance
        total_distance = 0.0
        for i in range(1, len(recent_positions)):
            total_distance += recent_positions[i].distance_to(recent_positions[i - 1])

        track.metrics.total_distance += total_distance

        # Calculate current speed
        if len(recent_positions) >= 2:
            latest = recent_positions[-1]
            previous = recent_positions[-2]

            distance = latest.distance_to(previous)
            time_diff = (latest.timestamp - previous.timestamp).total_seconds()

            if time_diff > 0:
                current_speed = distance / time_diff
                track.metrics.current_speed = current_speed

                # Update max speed
                if current_speed > track.metrics.max_speed:
                    track.metrics.max_speed = current_speed

                # Update average speed (running average)
                if track.metrics.avg_speed == 0:
                    track.metrics.avg_speed = current_speed
                else:
                    alpha = 0.1  # Smoothing factor
                    track.metrics.avg_speed = (
                        alpha * current_speed + (1 - alpha) * track.metrics.avg_speed
                    )

        # Calculate direction vector
        if len(recent_positions) >= 2:
            latest = recent_positions[-1]
            earliest = recent_positions[0]

            direction = latest.to_array() - earliest.to_array()
            norm = np.linalg.norm(direction)

            if norm > 0.01:  # Minimum movement threshold
                track.metrics.direction_vector = direction / norm
            else:
                track.metrics.direction_vector = None

        # Check if moving
        if len(recent_positions) >= 2:
            latest = recent_positions[-1]
            earliest = recent_positions[0]
            distance = latest.distance_to(earliest)

            track.metrics.is_moving = distance > self.idle_threshold_m

            if track.metrics.is_moving:
                track.metrics.last_movement_time = latest.timestamp
                track.metrics.idle_duration = 0.0
            else:
                # Calculate idle duration
                if track.metrics.last_movement_time:
                    track.metrics.idle_duration = (
                        latest.timestamp - track.metrics.last_movement_time
                    ).total_seconds()
                else:
                    track.metrics.idle_duration = (
                        latest.timestamp - track.first_seen
                    ).total_seconds()

    def get_track(self, object_id: str) -> Optional[ObjectTrack]:
        """객체 추적 데이터 조회"""
        return self.tracks.get(object_id)

    def get_active_tracks(self, timeout_sec: float = 5.0) -> List[ObjectTrack]:
        """활성 추적 중인 객체 목록 조회"""
        now = datetime.now()
        timeout = timedelta(seconds=timeout_sec)

        active = []
        for track in self.tracks.values():
            if (now - track.last_seen) < timeout:
                active.append(track)

        self.stats["active_objects"] = len(active)
        return active

    def calculate_distance(
        self, object_id: str, time_window_sec: float = 1.0
    ) -> Optional[float]:
        """
        시간 윈도우 내 이동 거리 계산

        Args:
            object_id: 객체 ID
            time_window_sec: 시간 윈도우 (초)

        Returns:
            이동 거리 (m) 또는 None
        """
        track = self.tracks.get(object_id)
        if not track or len(track.positions) < 2:
            return None

        cutoff_time = datetime.now() - timedelta(seconds=time_window_sec)

        # Filter positions in time window
        positions_in_window = [
            pos for pos in track.positions if pos.timestamp >= cutoff_time
        ]

        if len(positions_in_window) < 2:
            return None

        # Calculate cumulative distance
        total_distance = 0.0
        for i in range(1, len(positions_in_window)):
            total_distance += positions_in_window[i].distance_to(
                positions_in_window[i - 1]
            )

        return total_distance

    def calculate_speed(self, object_id: str) -> Optional[float]:
        """현재 속도 계산 (m/s)"""
        track = self.tracks.get(object_id)
        if not track:
            return None

        return track.metrics.current_speed

    def get_direction(self, object_id: str) -> Optional[np.ndarray]:
        """이동 방향 벡터 반환"""
        track = self.tracks.get(object_id)
        if not track:
            return None

        return track.metrics.direction_vector

    def is_idle(
        self, object_id: str, duration_sec: Optional[float] = None
    ) -> Optional[bool]:
        """
        정지 상태 확인

        Args:
            object_id: 객체 ID
            duration_sec: 정지 지속 시간 임계값 (None이면 기본값 사용)

        Returns:
            정지 상태 여부 또는 None (객체가 없는 경우)
        """
        track = self.tracks.get(object_id)
        if not track:
            return None

        threshold = duration_sec if duration_sec is not None else self.idle_duration_sec

        return (
            not track.metrics.is_moving and track.metrics.idle_duration >= threshold
        )

    def get_position_history(
        self, object_id: str, limit: Optional[int] = None
    ) -> Optional[List[Position3D]]:
        """위치 히스토리 조회"""
        track = self.tracks.get(object_id)
        if not track:
            return None

        positions = list(track.positions)
        if limit:
            positions = positions[-limit:]

        return positions

    def remove_track(self, object_id: str) -> bool:
        """추적 제거"""
        if object_id in self.tracks:
            del self.tracks[object_id]
            logger.info(f"Track removed: {object_id}")
            return True
        return False

    def cleanup_old_tracks(self, timeout_sec: float = 60.0) -> int:
        """오래된 추적 제거"""
        now = datetime.now()
        timeout = timedelta(seconds=timeout_sec)

        to_remove = []
        for object_id, track in self.tracks.items():
            if (now - track.last_seen) > timeout:
                to_remove.append(object_id)

        for object_id in to_remove:
            del self.tracks[object_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tracks")

        return len(to_remove)

    def get_statistics(self) -> Dict:
        """통계 조회"""
        total_distance = sum(
            track.metrics.total_distance for track in self.tracks.values()
        )
        avg_speed = (
            sum(track.metrics.avg_speed for track in self.tracks.values())
            / len(self.tracks)
            if self.tracks
            else 0.0
        )

        return {
            **self.stats,
            "total_tracks": len(self.tracks),
            "total_distance_all_objects": total_distance,
            "avg_speed_all_objects": avg_speed,
        }
