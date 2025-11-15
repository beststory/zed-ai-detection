"""
Frame Synchronizer for Multimodal Vision AI System
CCTV와 ZED 카메라 프레임을 타임스탬프 기반으로 동기화
"""

import numpy as np
from collections import deque
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Tuple, Dict
from threading import Lock
import logging

logger = logging.getLogger(__name__)


@dataclass
class FrameData:
    """프레임 데이터 구조"""

    frame: np.ndarray
    timestamp: datetime
    camera_id: str
    frame_number: int
    metadata: Optional[Dict] = None


@dataclass
class SynchronizedFramePair:
    """동기화된 프레임 쌍"""

    cctv_frame: FrameData
    zed_rgb: FrameData
    zed_depth: Optional[np.ndarray] = None
    time_diff_ms: float = 0.0
    sync_quality: str = "good"  # 'excellent', 'good', 'acceptable', 'poor'


class FrameSynchronizer:
    """
    CCTV와 ZED 프레임을 타임스탬프 기반으로 동기화

    Features:
    - Timestamp-based frame matching
    - Configurable tolerance window
    - Buffer management for async streams
    - Sync quality assessment
    - Statistics tracking
    """

    def __init__(
        self,
        tolerance_ms: int = 100,
        max_buffer: int = 60,
        sync_mode: str = "nearest",  # 'nearest', 'forward', 'backward'
    ):
        """
        Args:
            tolerance_ms: 동기화 허용 오차 (밀리초)
            max_buffer: 최대 버퍼 크기 (프레임 수)
            sync_mode: 동기화 모드
                - nearest: 가장 가까운 타임스탬프 매칭
                - forward: 미래 방향으로만 매칭
                - backward: 과거 방향으로만 매칭
        """
        self.tolerance = timedelta(milliseconds=tolerance_ms)
        self.max_buffer = max_buffer
        self.sync_mode = sync_mode

        # Frame buffers
        self.cctv_buffer = deque(maxlen=max_buffer)
        self.zed_buffer = deque(maxlen=max_buffer)

        # Thread safety
        self.lock = Lock()

        # Statistics
        self.stats = {
            "cctv_frames_received": 0,
            "zed_frames_received": 0,
            "synchronized_pairs": 0,
            "dropped_cctv": 0,
            "dropped_zed": 0,
            "avg_time_diff_ms": 0.0,
            "max_time_diff_ms": 0.0,
        }

        logger.info(
            f"FrameSynchronizer initialized: tolerance={tolerance_ms}ms, "
            f"buffer={max_buffer}, mode={sync_mode}"
        )

    def add_cctv_frame(
        self,
        frame: np.ndarray,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        CCTV 프레임 추가

        Args:
            frame: 프레임 이미지 (numpy array)
            timestamp: 타임스탬프 (None이면 현재 시간 사용)
            metadata: 추가 메타데이터
        """
        if timestamp is None:
            timestamp = datetime.now()

        frame_data = FrameData(
            frame=frame,
            timestamp=timestamp,
            camera_id="cctv",
            frame_number=self.stats["cctv_frames_received"],
            metadata=metadata,
        )

        with self.lock:
            self.cctv_buffer.append(frame_data)
            self.stats["cctv_frames_received"] += 1

        logger.debug(
            f"CCTV frame added: timestamp={timestamp.isoformat()}, "
            f"buffer_size={len(self.cctv_buffer)}"
        )

    def add_zed_frame(
        self,
        rgb: np.ndarray,
        depth: Optional[np.ndarray] = None,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        ZED 프레임 추가

        Args:
            rgb: RGB 프레임
            depth: Depth 맵 (optional)
            timestamp: 타임스탬프 (None이면 현재 시간 사용)
            metadata: 추가 메타데이터
        """
        if timestamp is None:
            timestamp = datetime.now()

        # Store depth in metadata
        if metadata is None:
            metadata = {}
        if depth is not None:
            metadata["depth"] = depth

        frame_data = FrameData(
            frame=rgb,
            timestamp=timestamp,
            camera_id="zed",
            frame_number=self.stats["zed_frames_received"],
            metadata=metadata,
        )

        with self.lock:
            self.zed_buffer.append(frame_data)
            self.stats["zed_frames_received"] += 1

        logger.debug(
            f"ZED frame added: timestamp={timestamp.isoformat()}, "
            f"buffer_size={len(self.zed_buffer)}"
        )

    def get_synchronized_pair(self) -> Optional[SynchronizedFramePair]:
        """
        동기화된 프레임 쌍 반환

        Returns:
            SynchronizedFramePair 또는 None (매칭 실패 시)
        """
        with self.lock:
            if not self.cctv_buffer or not self.zed_buffer:
                return None

            # Get oldest CCTV frame
            cctv_frame = self.cctv_buffer[0]

            # Find matching ZED frame
            matched_zed = None
            min_diff = None

            for i, zed_frame in enumerate(self.zed_buffer):
                time_diff = abs(zed_frame.timestamp - cctv_frame.timestamp)

                if time_diff <= self.tolerance:
                    if min_diff is None or time_diff < min_diff:
                        min_diff = time_diff
                        matched_zed = (i, zed_frame)

            if matched_zed is None:
                # No match found, drop oldest CCTV frame
                self.cctv_buffer.popleft()
                self.stats["dropped_cctv"] += 1
                logger.warning(
                    f"No ZED match for CCTV frame at {cctv_frame.timestamp.isoformat()}"
                )
                return None

            # Extract matched frames
            zed_idx, zed_frame = matched_zed
            self.cctv_buffer.popleft()
            self.zed_buffer.remove(zed_frame)

            # Calculate time difference
            time_diff_ms = abs(
                (zed_frame.timestamp - cctv_frame.timestamp).total_seconds() * 1000
            )

            # Assess sync quality
            sync_quality = self._assess_sync_quality(time_diff_ms)

            # Update statistics
            self.stats["synchronized_pairs"] += 1
            self._update_time_diff_stats(time_diff_ms)

            # Extract depth from metadata
            depth_map = None
            if zed_frame.metadata and "depth" in zed_frame.metadata:
                depth_map = zed_frame.metadata["depth"]

            synchronized_pair = SynchronizedFramePair(
                cctv_frame=cctv_frame,
                zed_rgb=zed_frame,
                zed_depth=depth_map,
                time_diff_ms=time_diff_ms,
                sync_quality=sync_quality,
            )

            logger.debug(
                f"Synchronized pair created: time_diff={time_diff_ms:.2f}ms, "
                f"quality={sync_quality}"
            )

            return synchronized_pair

    def _assess_sync_quality(self, time_diff_ms: float) -> str:
        """동기화 품질 평가"""
        tolerance_ms = self.tolerance.total_seconds() * 1000

        if time_diff_ms <= tolerance_ms * 0.25:
            return "excellent"
        elif time_diff_ms <= tolerance_ms * 0.5:
            return "good"
        elif time_diff_ms <= tolerance_ms * 0.75:
            return "acceptable"
        else:
            return "poor"

    def _update_time_diff_stats(self, time_diff_ms: float) -> None:
        """타임 차이 통계 업데이트"""
        n = self.stats["synchronized_pairs"]

        # Running average
        current_avg = self.stats["avg_time_diff_ms"]
        self.stats["avg_time_diff_ms"] = (current_avg * (n - 1) + time_diff_ms) / n

        # Max
        if time_diff_ms > self.stats["max_time_diff_ms"]:
            self.stats["max_time_diff_ms"] = time_diff_ms

    def get_buffer_status(self) -> Dict:
        """버퍼 상태 조회"""
        with self.lock:
            return {
                "cctv_buffer_size": len(self.cctv_buffer),
                "zed_buffer_size": len(self.zed_buffer),
                "cctv_buffer_utilization": len(self.cctv_buffer) / self.max_buffer,
                "zed_buffer_utilization": len(self.zed_buffer) / self.max_buffer,
            }

    def get_statistics(self) -> Dict:
        """통계 조회"""
        with self.lock:
            total_received = (
                self.stats["cctv_frames_received"] + self.stats["zed_frames_received"]
            )
            sync_rate = (
                self.stats["synchronized_pairs"] / (total_received / 2)
                if total_received > 0
                else 0.0
            )

            return {
                **self.stats,
                "sync_rate": sync_rate,
                "drop_rate_cctv": (
                    self.stats["dropped_cctv"] / self.stats["cctv_frames_received"]
                    if self.stats["cctv_frames_received"] > 0
                    else 0.0
                ),
                "drop_rate_zed": (
                    self.stats["dropped_zed"] / self.stats["zed_frames_received"]
                    if self.stats["zed_frames_received"] > 0
                    else 0.0
                ),
            }

    def reset_statistics(self) -> None:
        """통계 초기화"""
        with self.lock:
            self.stats = {
                "cctv_frames_received": 0,
                "zed_frames_received": 0,
                "synchronized_pairs": 0,
                "dropped_cctv": 0,
                "dropped_zed": 0,
                "avg_time_diff_ms": 0.0,
                "max_time_diff_ms": 0.0,
            }

        logger.info("Statistics reset")

    def clear_buffers(self) -> None:
        """버퍼 초기화"""
        with self.lock:
            self.cctv_buffer.clear()
            self.zed_buffer.clear()

        logger.info("Buffers cleared")
