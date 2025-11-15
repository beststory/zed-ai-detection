"""
Image Analyzer using Ollama for AI-powered analysis
"""

import cv2
import numpy as np
from typing import Optional, Dict, List, Union
from dataclasses import dataclass
from datetime import datetime
import json
import os

from .ollama_client import OllamaClient, create_ollama_client


@dataclass
class AnalysisResult:
    """이미지 분석 결과"""
    timestamp: str
    camera_id: str
    description: str
    anomalies: List[str]
    confidence: float
    processing_time: float


class ImageAnalyzer:
    """
    Ollama를 사용한 이미지 분석

    Features:
    - 자연어 이미지 설명
    - 이상 감지 (anomaly detection)
    - 변화 비교 분석
    - 보안 위협 감지
    """

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        analysis_dir: str = "data/analysis"
    ):
        """
        초기화

        Args:
            ollama_client: OllamaClient 인스턴스 (None이면 자동 생성)
            analysis_dir: 분석 결과 저장 디렉토리
        """
        self.ollama = ollama_client or create_ollama_client()
        self.analysis_dir = analysis_dir
        os.makedirs(analysis_dir, exist_ok=True)

        self.analysis_history: List[AnalysisResult] = []

        # 분석 프롬프트 템플릿
        self.prompts = {
            "describe": """Analyze this security camera image and describe:
1. Main objects and people visible
2. Their activities and behaviors
3. Time of day indicators (lighting, shadows)
4. Any unusual or suspicious elements
5. Overall scene context

Be concise but detailed.""",

            "anomaly": """Analyze this security camera image for potential anomalies or security concerns:
1. Unauthorized access attempts
2. Unusual movements or behaviors
3. Objects left unattended
4. People in restricted areas
5. Any safety hazards

List only genuine concerns. If nothing unusual, say "No anomalies detected".""",

            "compare": """Compare these two images and identify:
1. What has changed between them
2. Any new objects or people
3. Any missing elements
4. Changes in lighting or environment
5. Significance of the changes

Focus on meaningful differences.""",

            "structural": """Analyze this image for structural changes:
1. Doors or windows - are they open/closed/moved?
2. Straight lines - any displacement or tilting?
3. Wall cracks or deformations
4. Furniture or fixture movements
5. Any structural integrity concerns

Be precise about measurements if visible."""
        }

    def analyze_scene(
        self,
        frame: np.ndarray,
        camera_id: str = "default",
        analysis_type: str = "describe"
    ) -> AnalysisResult:
        """
        장면 분석

        Args:
            frame: 분석할 이미지 프레임
            camera_id: 카메라 ID
            analysis_type: 분석 유형 (describe, anomaly, structural)

        Returns:
            AnalysisResult 객체
        """
        start_time = datetime.now()

        # 프롬프트 선택
        prompt = self.prompts.get(analysis_type, self.prompts["describe"])

        try:
            # Ollama로 이미지 분석
            response = self.ollama.analyze_image(
                image=frame,
                prompt=prompt,
                temperature=0.3  # 일관된 분석을 위해 낮은 temperature
            )

            # 이상 항목 추출
            anomalies = self._extract_anomalies(response.content)

            # 신뢰도 계산 (간단한 휴리스틱)
            confidence = self._calculate_confidence(response.content, anomalies)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            result = AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=response.content,
                anomalies=anomalies,
                confidence=confidence,
                processing_time=processing_time
            )

            self.analysis_history.append(result)

            return result

        except Exception as e:
            print(f"❌ 이미지 분석 실패: {e}")
            # 빈 결과 반환
            return AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=f"분석 실패: {str(e)}",
                anomalies=[],
                confidence=0.0,
                processing_time=0.0
            )

    def compare_frames(
        self,
        frame1: np.ndarray,
        frame2: np.ndarray,
        camera_id: str = "default"
    ) -> AnalysisResult:
        """
        두 프레임 비교 분석

        Args:
            frame1: 이전 프레임
            frame2: 현재 프레임
            camera_id: 카메라 ID

        Returns:
            AnalysisResult 객체
        """
        start_time = datetime.now()

        # 두 이미지를 좌우로 결합
        h1, w1 = frame1.shape[:2]
        h2, w2 = frame2.shape[:2]

        # 높이를 맞춤
        if h1 != h2:
            max_h = max(h1, h2)
            if h1 < max_h:
                frame1 = cv2.resize(frame1, (w1, max_h))
            if h2 < max_h:
                frame2 = cv2.resize(frame2, (w2, max_h))

        # 좌우 결합
        combined = np.hstack([frame1, frame2])

        # 라벨 추가
        cv2.putText(combined, "BEFORE", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(combined, "AFTER", (w1 + 10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        try:
            # Ollama로 비교 분석
            response = self.ollama.analyze_image(
                image=combined,
                prompt=self.prompts["compare"],
                temperature=0.3
            )

            # 변화 항목 추출
            anomalies = self._extract_changes(response.content)

            confidence = self._calculate_confidence(response.content, anomalies)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            result = AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=response.content,
                anomalies=anomalies,
                confidence=confidence,
                processing_time=processing_time
            )

            self.analysis_history.append(result)

            return result

        except Exception as e:
            print(f"❌ 프레임 비교 실패: {e}")
            return AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=f"비교 실패: {str(e)}",
                anomalies=[],
                confidence=0.0,
                processing_time=0.0
            )

    def detect_structural_changes(
        self,
        frame: np.ndarray,
        displacement_mm: float,
        camera_id: str = "default"
    ) -> AnalysisResult:
        """
        구조 변화 분석 (detection/structure.py 결과와 연계)

        Args:
            frame: 현재 프레임
            displacement_mm: 감지된 변위 (mm)
            camera_id: 카메라 ID

        Returns:
            AnalysisResult 객체
        """
        # 변위 정보를 포함한 프롬프트
        enhanced_prompt = f"""{self.prompts["structural"]}

NOTE: Automated structural analysis detected a displacement of {displacement_mm:.2f} mm.
Focus your analysis on identifying what might have caused this displacement."""

        start_time = datetime.now()

        try:
            response = self.ollama.analyze_image(
                image=frame,
                prompt=enhanced_prompt,
                temperature=0.3
            )

            # 구조 변화 항목 추출
            anomalies = self._extract_structural_issues(response.content)

            # 변위가 크면 신뢰도 증가
            base_confidence = self._calculate_confidence(response.content, anomalies)
            if displacement_mm > 1.0:  # 1mm 이상
                base_confidence = min(1.0, base_confidence + 0.2)

            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()

            result = AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=f"[Displacement: {displacement_mm:.2f}mm] {response.content}",
                anomalies=anomalies,
                confidence=base_confidence,
                processing_time=processing_time
            )

            self.analysis_history.append(result)

            return result

        except Exception as e:
            print(f"❌ 구조 변화 분석 실패: {e}")
            return AnalysisResult(
                timestamp=datetime.now().isoformat(),
                camera_id=camera_id,
                description=f"분석 실패: {str(e)}",
                anomalies=[],
                confidence=0.0,
                processing_time=0.0
            )

    def _extract_anomalies(self, text: str) -> List[str]:
        """텍스트에서 이상 항목 추출"""
        anomalies = []

        # "No anomalies" 체크
        if "no anomalies" in text.lower() or "nothing unusual" in text.lower():
            return []

        # 키워드 기반 추출
        keywords = [
            "unauthorized", "suspicious", "unusual", "concern",
            "hazard", "unattended", "restricted", "alert"
        ]

        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                anomalies.append(line.strip())

        return anomalies

    def _extract_changes(self, text: str) -> List[str]:
        """텍스트에서 변화 항목 추출"""
        changes = []

        keywords = [
            "new", "added", "removed", "missing", "moved",
            "changed", "different", "appeared", "disappeared"
        ]

        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                changes.append(line.strip())

        return changes

    def _extract_structural_issues(self, text: str) -> List[str]:
        """텍스트에서 구조 문제 추출"""
        issues = []

        keywords = [
            "open", "closed", "moved", "displaced", "tilted",
            "crack", "deformation", "shift", "misaligned"
        ]

        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in keywords):
                issues.append(line.strip())

        return issues

    def _calculate_confidence(self, text: str, anomalies: List[str]) -> float:
        """
        신뢰도 계산 (간단한 휴리스틱)

        Args:
            text: 분석 텍스트
            anomalies: 추출된 이상 항목

        Returns:
            0.0-1.0 범위의 신뢰도
        """
        confidence = 0.5  # 기본 신뢰도

        # 텍스트 길이 기반 (더 상세한 분석 = 높은 신뢰도)
        if len(text) > 200:
            confidence += 0.2
        elif len(text) > 100:
            confidence += 0.1

        # 이상 항목 개수 기반
        if len(anomalies) > 0:
            confidence += 0.1

        # 확정적 표현 체크
        certain_words = ["clearly", "definitely", "obvious", "certain"]
        if any(word in text.lower() for word in certain_words):
            confidence += 0.1

        # 불확실 표현 체크
        uncertain_words = ["maybe", "possibly", "unclear", "uncertain"]
        if any(word in text.lower() for word in uncertain_words):
            confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def save_analysis_results(self, filepath: str):
        """분석 결과 저장"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        results_data = [
            {
                "timestamp": result.timestamp,
                "camera_id": result.camera_id,
                "description": result.description,
                "anomalies": result.anomalies,
                "confidence": result.confidence,
                "processing_time": result.processing_time
            }
            for result in self.analysis_history
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, indent=2, ensure_ascii=False)

    def get_recent_analyses(self, limit: int = 10) -> List[AnalysisResult]:
        """최근 분석 결과 조회"""
        return self.analysis_history[-limit:]

    def get_statistics(self) -> Dict:
        """분석 통계 조회"""
        if not self.analysis_history:
            return {
                "total_analyses": 0,
                "avg_processing_time": 0,
                "avg_confidence": 0,
                "total_anomalies": 0
            }

        processing_times = [r.processing_time for r in self.analysis_history]
        confidences = [r.confidence for r in self.analysis_history]
        total_anomalies = sum(len(r.anomalies) for r in self.analysis_history)

        return {
            "total_analyses": len(self.analysis_history),
            "avg_processing_time": sum(processing_times) / len(processing_times),
            "avg_confidence": sum(confidences) / len(confidences),
            "total_anomalies": total_anomalies
        }
