"""
Motion Detection Module using OpenCV Background Subtraction
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os


@dataclass
class MotionEvent:
    """모션 이벤트 데이터 클래스"""
    timestamp: str
    camera_id: str
    bounding_boxes: List[Tuple[int, int, int, int]]
    motion_area: int
    confidence: float


class MotionDetector:
    """
    OpenCV Background Subtraction을 사용한 모션 감지

    사용 알고리즘:
    - MOG2: Gaussian Mixture-based Background/Foreground Segmentation
    - KNN: K-Nearest Neighbors based Background/Foreground Segmentation
    """

    def __init__(
        self,
        algorithm: str = "MOG2",
        history: int = 500,
        threshold: int = 16,
        detect_shadows: bool = True,
        min_area: int = 500
    ):
        """
        초기화

        Args:
            algorithm: 'MOG2' 또는 'KNN'
            history: 학습 프레임 수
            threshold: 움직임 감지 임계값
            detect_shadows: 그림자 감지 여부
            min_area: 최소 모션 영역 크기 (픽셀)
        """
        self.algorithm = algorithm
        self.min_area = min_area

        # Background Subtractor 초기화
        if algorithm == "MOG2":
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
                history=history,
                varThreshold=threshold,
                detectShadows=detect_shadows
            )
        elif algorithm == "KNN":
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN(
                history=history,
                dist2Threshold=threshold * 10,  # KNN은 더 큰 값 필요
                detectShadows=detect_shadows
            )
        else:
            raise ValueError(f"Unknown algorithm: {algorithm}")

        self.event_history: List[MotionEvent] = []

    def detect(
        self,
        frame: np.ndarray,
        camera_id: str = "default"
    ) -> Tuple[List[Tuple[int, int, int, int]], np.ndarray]:
        """
        프레임에서 모션 감지

        Args:
            frame: BGR 이미지 프레임
            camera_id: 카메라 식별자

        Returns:
            (bounding_boxes, fg_mask): 감지된 영역의 바운딩 박스와 전경 마스크
        """
        # 전경 마스크 생성
        fg_mask = self.bg_subtractor.apply(frame)

        # 노이즈 제거 (모폴로지 연산)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        # 윤곽선 찾기
        contours, _ = cv2.findContours(
            fg_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        # 바운딩 박스 추출
        bounding_boxes = []
        total_area = 0

        for contour in contours:
            area = cv2.contourArea(contour)

            # 최소 영역보다 큰 윤곽선만 처리
            if area < self.min_area:
                continue

            x, y, w, h = cv2.boundingRect(contour)
            bounding_boxes.append((x, y, w, h))
            total_area += area

        # 이벤트 기록
        if len(bounding_boxes) > 0:
            confidence = min(total_area / (frame.shape[0] * frame.shape[1]), 1.0)
            event = MotionEvent(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                bounding_boxes=bounding_boxes,
                motion_area=total_area,
                confidence=confidence
            )
            self.event_history.append(event)

        return bounding_boxes, fg_mask

    def draw_detections(
        self,
        frame: np.ndarray,
        bounding_boxes: List[Tuple[int, int, int, int]],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        감지 결과를 프레임에 그리기

        Args:
            frame: 원본 프레임
            bounding_boxes: 바운딩 박스 리스트
            color: 박스 색상 (BGR)
            thickness: 선 두께

        Returns:
            그려진 프레임
        """
        result = frame.copy()

        for (x, y, w, h) in bounding_boxes:
            cv2.rectangle(result, (x, y), (x + w, y + h), color, thickness)

            # 영역 크기 표시
            area_text = f"{w * h} px"
            cv2.putText(
                result,
                area_text,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                1
            )

        # 전체 감지 수 표시
        count_text = f"Motion Detected: {len(bounding_boxes)}"
        cv2.putText(
            result,
            count_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            color,
            2
        )

        return result

    def save_events(self, filepath: str):
        """이벤트 기록 저장"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        events_data = [
            {
                "timestamp": event.timestamp,
                "camera_id": event.camera_id,
                "bounding_boxes": event.bounding_boxes,
                "motion_area": event.motion_area,
                "confidence": event.confidence
            }
            for event in self.event_history
        ]

        with open(filepath, 'w') as f:
            json.dump(events_data, f, indent=2)

    def get_recent_events(self, limit: int = 10) -> List[MotionEvent]:
        """최근 이벤트 조회"""
        return self.event_history[-limit:]

    def reset(self):
        """배경 모델 초기화"""
        if self.algorithm == "MOG2":
            self.bg_subtractor = cv2.createBackgroundSubtractorMOG2()
        else:
            self.bg_subtractor = cv2.createBackgroundSubtractorKNN()

        self.event_history.clear()
