"""
Structural Change Detection Module
문, 직선 등의 미세한 구조 변화를 mm 단위로 감지
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path


@dataclass
class StructuralChange:
    """구조 변화 측정 데이터"""
    timestamp: str
    camera_id: str
    displacement_mm: float
    displacement_pixels: float
    change_percentage: float
    baseline_timestamp: str


class StructureDetector:
    """
    구조 변화 감지 및 mm 단위 측정

    방법:
    1. 기준선(baseline) 이미지 저장
    2. Canny Edge Detection으로 직선/경계 추출
    3. 특징점(ORB/SIFT) 매칭으로 변위 측정
    4. Depth 맵 활용하여 픽셀 → mm 변환
    """

    def __init__(
        self,
        baseline_dir: str = "data/baselines",
        sensitivity: float = 0.01,
        pixel_to_mm_ratio: float = 1.0
    ):
        """
        초기화

        Args:
            baseline_dir: 기준선 이미지 저장 디렉토리
            sensitivity: 변화 감지 민감도 (0.01 = 1%)
            pixel_to_mm_ratio: 픽셀당 mm 비율 (depth 맵에서 계산)
        """
        self.baseline_dir = Path(baseline_dir)
        self.baseline_dir.mkdir(parents=True, exist_ok=True)

        self.sensitivity = sensitivity
        self.pixel_to_mm_ratio = pixel_to_mm_ratio

        # 특징점 검출기 (ORB - 빠르고 효율적)
        self.feature_detector = cv2.ORB_create(nfeatures=1000)

        # 특징점 매처
        self.matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        self.baselines: Dict[str, dict] = {}
        self.change_history: List[StructuralChange] = []

    def set_baseline(
        self,
        frame: np.ndarray,
        depth_map: Optional[np.ndarray],
        camera_id: str = "default"
    ) -> bool:
        """
        기준선 설정

        Args:
            frame: RGB 프레임
            depth_map: Depth 맵 (mm 단위 거리)
            camera_id: 카메라 ID

        Returns:
            성공 여부
        """
        try:
            # 그레이스케일 변환
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Edge 검출
            edges = cv2.Canny(gray, 50, 150)

            # 특징점 추출
            keypoints, descriptors = self.feature_detector.detectAndCompute(gray, None)

            if descriptors is None:
                print(f"특징점을 찾을 수 없습니다: {camera_id}")
                return False

            # 기준선 저장
            timestamp = datetime.now().isoformat()
            baseline_data = {
                "timestamp": timestamp,
                "frame": frame.copy(),
                "gray": gray,
                "edges": edges,
                "keypoints": keypoints,
                "descriptors": descriptors,
                "depth_map": depth_map.copy() if depth_map is not None else None
            }

            self.baselines[camera_id] = baseline_data

            # 디스크에 저장
            baseline_path = self.baseline_dir / f"{camera_id}_{timestamp.replace(':', '-')}"
            np.save(str(baseline_path) + "_frame.npy", frame)
            np.save(str(baseline_path) + "_descriptors.npy", descriptors)

            if depth_map is not None:
                np.save(str(baseline_path) + "_depth.npy", depth_map)

            print(f"✅ 기준선 설정 완료: {camera_id} at {timestamp}")
            return True

        except Exception as e:
            print(f"❌ 기준선 설정 실패: {e}")
            return False

    def detect_changes(
        self,
        frame: np.ndarray,
        depth_map: Optional[np.ndarray],
        camera_id: str = "default"
    ) -> Tuple[float, float, np.ndarray]:
        """
        구조 변화 감지 및 측정

        Args:
            frame: 현재 프레임
            depth_map: 현재 Depth 맵
            camera_id: 카메라 ID

        Returns:
            (displacement_mm, displacement_pixels, annotated_frame)
        """
        if camera_id not in self.baselines:
            print(f"⚠️  기준선이 설정되지 않음: {camera_id}")
            return 0.0, 0.0, frame

        baseline = self.baselines[camera_id]

        # 그레이스케일 변환
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 현재 프레임의 특징점 추출
        keypoints, descriptors = self.feature_detector.detectAndCompute(gray, None)

        if descriptors is None:
            return 0.0, 0.0, frame

        # 특징점 매칭
        matches = self.matcher.match(baseline["descriptors"], descriptors)

        # 상위 매칭만 사용
        matches = sorted(matches, key=lambda x: x.distance)
        good_matches = matches[:min(50, len(matches))]

        if len(good_matches) < 4:
            return 0.0, 0.0, frame

        # 매칭된 점들의 좌표
        pts_baseline = np.float32([
            baseline["keypoints"][m.queryIdx].pt for m in good_matches
        ]).reshape(-1, 1, 2)

        pts_current = np.float32([
            keypoints[m.trainIdx].pt for m in good_matches
        ]).reshape(-1, 1, 2)

        # 변위 벡터 계산
        displacements = pts_current - pts_baseline
        avg_displacement = np.mean(np.linalg.norm(displacements, axis=2))

        # 픽셀 변위
        displacement_pixels = float(avg_displacement)

        # mm 변위 계산 (depth 맵 활용)
        displacement_mm = 0.0
        if depth_map is not None and baseline["depth_map"] is not None:
            # 중앙점의 깊이 사용
            h, w = depth_map.shape
            center_depth = depth_map[h//2, w//2]

            if center_depth > 0:
                # 깊이에 따른 픽셀-mm 비율 조정
                # 거리가 멀수록 픽셀당 mm가 커짐
                pixel_to_mm = center_depth / 1000.0  # 임시 공식
                displacement_mm = displacement_pixels * pixel_to_mm
        else:
            # depth 맵이 없으면 기본 비율 사용
            displacement_mm = displacement_pixels * self.pixel_to_mm_ratio

        # 변화율 계산
        frame_diagonal = np.sqrt(frame.shape[0]**2 + frame.shape[1]**2)
        change_percentage = (displacement_pixels / frame_diagonal) * 100

        # 이벤트 기록
        if change_percentage >= self.sensitivity:
            change_event = StructuralChange(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                displacement_mm=displacement_mm,
                displacement_pixels=displacement_pixels,
                change_percentage=change_percentage,
                baseline_timestamp=baseline["timestamp"]
            )
            self.change_history.append(change_event)

        # 시각화
        annotated_frame = self._draw_changes(
            frame, pts_baseline, pts_current,
            displacement_mm, displacement_pixels
        )

        return displacement_mm, displacement_pixels, annotated_frame

    def _draw_changes(
        self,
        frame: np.ndarray,
        pts_baseline: np.ndarray,
        pts_current: np.ndarray,
        displacement_mm: float,
        displacement_pixels: float
    ) -> np.ndarray:
        """변화 시각화"""
        result = frame.copy()

        # 변위 벡터 그리기
        for i in range(len(pts_baseline)):
            pt1 = tuple(pts_baseline[i][0].astype(int))
            pt2 = tuple(pts_current[i][0].astype(int))

            cv2.arrowedLine(result, pt1, pt2, (0, 255, 255), 2, tipLength=0.3)
            cv2.circle(result, pt1, 3, (0, 0, 255), -1)
            cv2.circle(result, pt2, 3, (0, 255, 0), -1)

        # 정보 텍스트
        info_text = [
            f"Displacement: {displacement_mm:.2f} mm ({displacement_pixels:.1f} px)",
            f"Baseline: {len(pts_baseline)} points tracked"
        ]

        y_offset = 30
        for text in info_text:
            cv2.putText(
                result, text, (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
            )
            y_offset += 30

        return result

    def get_change_history(
        self,
        camera_id: Optional[str] = None,
        days: int = 7
    ) -> List[StructuralChange]:
        """변화 이력 조회"""
        from datetime import timedelta

        cutoff_time = datetime.now() - timedelta(days=days)

        history = [
            event for event in self.change_history
            if datetime.fromisoformat(event.timestamp) > cutoff_time
        ]

        if camera_id:
            history = [e for e in history if e.camera_id == camera_id]

        return history

    def save_events(self, filepath: str):
        """이벤트 기록 저장"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        events_data = [
            {
                "timestamp": event.timestamp,
                "camera_id": event.camera_id,
                "displacement_mm": event.displacement_mm,
                "displacement_pixels": event.displacement_pixels,
                "change_percentage": event.change_percentage,
                "baseline_timestamp": event.baseline_timestamp
            }
            for event in self.change_history
        ]

        with open(filepath, 'w') as f:
            json.dump(events_data, f, indent=2)

    def reset_baseline(self, camera_id: str):
        """특정 카메라의 기준선 초기화"""
        if camera_id in self.baselines:
            del self.baselines[camera_id]
            print(f"기준선 초기화: {camera_id}")
