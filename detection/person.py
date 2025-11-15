"""
Person Detection Module using YOLOv8
"""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import os
from ultralytics import YOLO


@dataclass
class PersonDetection:
    """사람 감지 결과 데이터 클래스"""
    timestamp: str
    camera_id: str
    person_count: int
    detections: List[dict]  # bbox, confidence, track_id


class PersonDetector:
    """
    YOLOv8을 사용한 사람 감지 및 추적

    Features:
    - 실시간 사람 감지
    - 객체 추적 (track_id)
    - 신뢰도 필터링
    - 카운팅 및 통계
    """

    def __init__(
        self,
        model_name: str = "yolov8n.pt",
        confidence_threshold: float = 0.5,
        device: str = "cpu"
    ):
        """
        초기화

        Args:
            model_name: YOLO 모델 파일명 (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)
            confidence_threshold: 최소 신뢰도 임계값
            device: 'cpu' 또는 'cuda'
        """
        self.confidence_threshold = confidence_threshold
        self.device = device

        # YOLO 모델 로드
        model_path = os.path.join("models", model_name)

        # 모델이 없으면 자동 다운로드
        if not os.path.exists(model_path):
            print(f"모델이 없습니다. {model_name} 다운로드 중...")
            os.makedirs("models", exist_ok=True)

        self.model = YOLO(model_name)
        self.model.to(device)

        # COCO 데이터셋 클래스 (person = 0)
        self.person_class_id = 0

        self.detection_history: List[PersonDetection] = []

    def detect(
        self,
        frame: np.ndarray,
        camera_id: str = "default",
        track: bool = True
    ) -> Tuple[List[dict], np.ndarray]:
        """
        프레임에서 사람 감지

        Args:
            frame: BGR 이미지 프레임
            camera_id: 카메라 식별자
            track: 객체 추적 활성화 여부

        Returns:
            (detections, annotated_frame): 감지 결과와 주석이 달린 프레임
        """
        # YOLO 추론
        if track:
            results = self.model.track(
                frame,
                persist=True,
                conf=self.confidence_threshold,
                classes=[self.person_class_id],
                verbose=False
            )
        else:
            results = self.model(
                frame,
                conf=self.confidence_threshold,
                classes=[self.person_class_id],
                verbose=False
            )

        detections = []

        if results[0].boxes is not None:
            boxes = results[0].boxes

            for i in range(len(boxes)):
                box = boxes.xyxy[i].cpu().numpy()
                conf = float(boxes.conf[i].cpu().numpy())

                # Track ID (추적 모드일 때만)
                track_id = None
                if track and hasattr(boxes, 'id') and boxes.id is not None:
                    track_id = int(boxes.id[i].cpu().numpy())

                detection = {
                    "bbox": [int(box[0]), int(box[1]), int(box[2]), int(box[3])],
                    "confidence": conf,
                    "track_id": track_id
                }
                detections.append(detection)

        # 이벤트 기록
        if len(detections) > 0:
            event = PersonDetection(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                person_count=len(detections),
                detections=detections
            )
            self.detection_history.append(event)

        # 주석이 달린 프레임 생성
        annotated_frame = results[0].plot()

        return detections, annotated_frame

    def draw_detections(
        self,
        frame: np.ndarray,
        detections: List[dict],
        color: Tuple[int, int, int] = (0, 255, 0),
        thickness: int = 2
    ) -> np.ndarray:
        """
        감지 결과를 프레임에 그리기 (커스텀)

        Args:
            frame: 원본 프레임
            detections: 감지 결과 리스트
            color: 박스 색상 (BGR)
            thickness: 선 두께

        Returns:
            그려진 프레임
        """
        result = frame.copy()

        for det in detections:
            bbox = det["bbox"]
            conf = det["confidence"]
            track_id = det.get("track_id")

            # 바운딩 박스
            cv2.rectangle(
                result,
                (bbox[0], bbox[1]),
                (bbox[2], bbox[3]),
                color,
                thickness
            )

            # 라벨 텍스트
            label = f"Person {conf:.2f}"
            if track_id is not None:
                label = f"ID:{track_id} {conf:.2f}"

            # 텍스트 배경
            (text_w, text_h), _ = cv2.getTextSize(
                label,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                1
            )
            cv2.rectangle(
                result,
                (bbox[0], bbox[1] - text_h - 10),
                (bbox[0] + text_w, bbox[1]),
                color,
                -1
            )

            # 텍스트
            cv2.putText(
                result,
                label,
                (bbox[0], bbox[1] - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                1
            )

        # 전체 카운트
        count_text = f"Persons Detected: {len(detections)}"
        cv2.putText(
            result,
            count_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        return result

    def get_statistics(self, time_window: int = 60) -> dict:
        """
        통계 정보 조회

        Args:
            time_window: 시간 윈도우 (초)

        Returns:
            통계 딕셔너리
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        cutoff_time = now - timedelta(seconds=time_window)

        recent_events = [
            event for event in self.detection_history
            if datetime.fromisoformat(event.timestamp) > cutoff_time
        ]

        if not recent_events:
            return {
                "total_detections": 0,
                "max_persons": 0,
                "avg_persons": 0,
                "time_window": time_window
            }

        person_counts = [event.person_count for event in recent_events]

        return {
            "total_detections": len(recent_events),
            "max_persons": max(person_counts),
            "avg_persons": sum(person_counts) / len(person_counts),
            "time_window": time_window
        }

    def save_events(self, filepath: str):
        """이벤트 기록 저장"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        events_data = [
            {
                "timestamp": event.timestamp,
                "camera_id": event.camera_id,
                "person_count": event.person_count,
                "detections": event.detections
            }
            for event in self.detection_history
        ]

        with open(filepath, 'w') as f:
            json.dump(events_data, f, indent=2)

    def get_recent_events(self, limit: int = 10) -> List[PersonDetection]:
        """최근 이벤트 조회"""
        return self.detection_history[-limit:]

    def reset(self):
        """히스토리 초기화"""
        self.detection_history.clear()
