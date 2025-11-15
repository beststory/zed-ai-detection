"""
Ollama API Client for AI Analysis
"""

import httpx
import base64
import json
import os
from typing import Optional, Dict, List, Union
from dataclasses import dataclass
from datetime import datetime
import numpy as np
import cv2


@dataclass
class OllamaResponse:
    """Ollama API 응답 데이터"""
    content: str
    model: str
    timestamp: str
    tokens_used: Optional[int] = None
    generation_time: Optional[float] = None


class OllamaClient:
    """
    Ollama API 클라이언트

    Features:
    - 텍스트 생성 (chat)
    - 이미지 분석 (vision)
    - 스트리밍 응답 지원
    - 타임아웃 및 재시도 로직
    """

    def __init__(
        self,
        host: str = "http://localhost:11434",
        model: str = "gpt-oss:20b",
        timeout: int = 60
    ):
        """
        초기화

        Args:
            host: Ollama 서버 주소
            model: 사용할 모델명
            timeout: API 요청 타임아웃 (초)
        """
        self.host = host.rstrip('/')
        self.model = model
        self.timeout = timeout

        # HTTP 클라이언트 설정
        self.client = httpx.Client(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_keepalive_connections=5)
        )

        self.request_history: List[Dict] = []

    def _encode_image_base64(self, image: Union[np.ndarray, str]) -> str:
        """
        이미지를 Base64로 인코딩

        Args:
            image: NumPy 배열 또는 이미지 파일 경로

        Returns:
            Base64 인코딩된 이미지 문자열
        """
        if isinstance(image, str):
            # 파일 경로인 경우
            with open(image, 'rb') as f:
                image_bytes = f.read()
        else:
            # NumPy 배열인 경우
            _, buffer = cv2.imencode('.jpg', image)
            image_bytes = buffer.tobytes()

        return base64.b64encode(image_bytes).decode('utf-8')

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        stream: bool = False
    ) -> OllamaResponse:
        """
        텍스트 생성 요청

        Args:
            prompt: 프롬프트 텍스트
            system_prompt: 시스템 프롬프트 (선택)
            temperature: 생성 온도 (0.0-1.0)
            stream: 스트리밍 응답 여부

        Returns:
            OllamaResponse 객체
        """
        url = f"{self.host}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": temperature,
            "stream": stream
        }

        if system_prompt:
            payload["system"] = system_prompt

        try:
            start_time = datetime.now()
            response = self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            end_time = datetime.now()

            generation_time = (end_time - start_time).total_seconds()

            # 응답 파싱
            content = result.get("response", "")

            ollama_response = OllamaResponse(
                content=content,
                model=self.model,
                timestamp=datetime.now().isoformat(),
                generation_time=generation_time
            )

            # 히스토리 기록
            self.request_history.append({
                "timestamp": ollama_response.timestamp,
                "type": "chat",
                "prompt": prompt[:100],  # 처음 100자만 저장
                "response": content[:100],
                "generation_time": generation_time
            })

            return ollama_response

        except httpx.TimeoutException:
            raise Exception(f"Ollama API 타임아웃 ({self.timeout}초)")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ollama API 오류: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Ollama 요청 실패: {str(e)}")

    def analyze_image(
        self,
        image: Union[np.ndarray, str],
        prompt: str = "Describe what you see in this image in detail.",
        temperature: float = 0.3
    ) -> OllamaResponse:
        """
        이미지 분석 요청 (Vision)

        Args:
            image: NumPy 배열 또는 이미지 파일 경로
            prompt: 분석 프롬프트
            temperature: 생성 온도

        Returns:
            OllamaResponse 객체
        """
        url = f"{self.host}/api/generate"

        # 이미지 인코딩
        image_base64 = self._encode_image_base64(image)

        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [image_base64],
            "temperature": temperature,
            "stream": False
        }

        try:
            start_time = datetime.now()
            response = self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            end_time = datetime.now()

            generation_time = (end_time - start_time).total_seconds()

            content = result.get("response", "")

            ollama_response = OllamaResponse(
                content=content,
                model=self.model,
                timestamp=datetime.now().isoformat(),
                generation_time=generation_time
            )

            # 히스토리 기록
            self.request_history.append({
                "timestamp": ollama_response.timestamp,
                "type": "vision",
                "prompt": prompt[:100],
                "response": content[:100],
                "generation_time": generation_time
            })

            return ollama_response

        except httpx.TimeoutException:
            raise Exception(f"Ollama API 타임아웃 ({self.timeout}초)")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ollama API 오류: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"이미지 분석 실패: {str(e)}")

    def check_connection(self) -> bool:
        """
        Ollama 서버 연결 확인

        Returns:
            연결 성공 여부
        """
        try:
            url = f"{self.host}/api/tags"
            response = self.client.get(url)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Ollama 서버 연결 실패: {e}")
            return False

    def list_models(self) -> List[str]:
        """
        사용 가능한 모델 목록 조회

        Returns:
            모델 이름 리스트
        """
        try:
            url = f"{self.host}/api/tags"
            response = self.client.get(url)
            response.raise_for_status()

            result = response.json()
            models = [model["name"] for model in result.get("models", [])]
            return models

        except Exception as e:
            print(f"모델 목록 조회 실패: {e}")
            return []

    def get_statistics(self) -> Dict:
        """
        사용 통계 조회

        Returns:
            통계 딕셔너리
        """
        if not self.request_history:
            return {
                "total_requests": 0,
                "chat_requests": 0,
                "vision_requests": 0,
                "avg_generation_time": 0
            }

        chat_count = sum(1 for r in self.request_history if r["type"] == "chat")
        vision_count = sum(1 for r in self.request_history if r["type"] == "vision")

        generation_times = [
            r["generation_time"] for r in self.request_history
            if r["generation_time"] is not None
        ]

        avg_time = sum(generation_times) / len(generation_times) if generation_times else 0

        return {
            "total_requests": len(self.request_history),
            "chat_requests": chat_count,
            "vision_requests": vision_count,
            "avg_generation_time": avg_time
        }

    def close(self):
        """HTTP 클라이언트 종료"""
        self.client.close()

    def __enter__(self):
        """Context manager 진입"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.close()


# 환경 변수에서 설정 로드
def create_ollama_client() -> OllamaClient:
    """
    환경 변수를 사용하여 OllamaClient 생성

    Returns:
        설정된 OllamaClient 인스턴스
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "gpt-oss:20b")

    return OllamaClient(host=host, model=model)
