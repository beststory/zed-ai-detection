"""
WebSocket Event Streaming for Multimodal Vision AI System
실시간 이벤트 스트리밍
"""

import asyncio
import json
from datetime import datetime
from typing import Set, Optional, Dict, Any
from fastapi import WebSocket, WebSocketDisconnect
from collections import deque
import logging

logger = logging.getLogger(__name__)


class WebSocketManager:
    """
    WebSocket 연결 관리자

    Features:
    - Multiple client connection management
    - Event broadcasting
    - Client filtering by event type
    - Connection statistics
    """

    def __init__(self, max_message_queue: int = 100):
        """
        Args:
            max_message_queue: 클라이언트별 최대 메시지 큐 크기
        """
        self.active_connections: Set[WebSocket] = set()
        self.client_filters: Dict[WebSocket, Set[str]] = {}  # {websocket: {event_types}}
        self.message_queues: Dict[WebSocket, deque] = {}
        self.max_message_queue = max_message_queue

        # Statistics
        self.stats = {
            "total_connections": 0,
            "current_connections": 0,
            "total_messages_sent": 0,
            "total_messages_failed": 0,
        }

        logger.info("WebSocketManager initialized")

    async def connect(
        self,
        websocket: WebSocket,
        event_filters: Optional[Set[str]] = None,
    ) -> None:
        """
        클라이언트 연결

        Args:
            websocket: WebSocket 연결
            event_filters: 수신할 이벤트 타입 필터 (None이면 모든 이벤트)
        """
        await websocket.accept()

        self.active_connections.add(websocket)
        self.client_filters[websocket] = event_filters or set()
        self.message_queues[websocket] = deque(maxlen=self.max_message_queue)

        self.stats["total_connections"] += 1
        self.stats["current_connections"] = len(self.active_connections)

        logger.info(
            f"WebSocket client connected. "
            f"Total connections: {self.stats['current_connections']}, "
            f"Filters: {event_filters or 'ALL'}"
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """클라이언트 연결 해제"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        if websocket in self.client_filters:
            del self.client_filters[websocket]

        if websocket in self.message_queues:
            del self.message_queues[websocket]

        self.stats["current_connections"] = len(self.active_connections)

        logger.info(
            f"WebSocket client disconnected. "
            f"Remaining connections: {self.stats['current_connections']}"
        )

    async def broadcast(
        self,
        message: Dict[str, Any],
        event_type: Optional[str] = None,
    ) -> int:
        """
        모든 클라이언트에 메시지 브로드캐스트

        Args:
            message: 전송할 메시지 (dict)
            event_type: 이벤트 타입 (필터링용)

        Returns:
            성공적으로 전송한 클라이언트 수
        """
        if not self.active_connections:
            return 0

        message_json = json.dumps(message, default=str)
        success_count = 0
        failed_connections = []

        for websocket in list(self.active_connections):
            # Check filter
            filters = self.client_filters.get(websocket, set())
            if filters and event_type and event_type not in filters:
                continue

            try:
                await websocket.send_text(message_json)
                success_count += 1
                self.stats["total_messages_sent"] += 1

                logger.debug(
                    f"Message sent to client: {event_type or 'unknown'}"
                )

            except WebSocketDisconnect:
                failed_connections.append(websocket)
                logger.warning("Client disconnected during broadcast")

            except Exception as e:
                failed_connections.append(websocket)
                self.stats["total_messages_failed"] += 1
                logger.error(f"Failed to send message to client: {e}")

        # Clean up failed connections
        for websocket in failed_connections:
            self.disconnect(websocket)

        return success_count

    async def send_to_client(
        self,
        websocket: WebSocket,
        message: Dict[str, Any],
    ) -> bool:
        """
        특정 클라이언트에게 메시지 전송

        Args:
            websocket: 대상 WebSocket
            message: 전송할 메시지

        Returns:
            성공 여부
        """
        if websocket not in self.active_connections:
            return False

        try:
            message_json = json.dumps(message, default=str)
            await websocket.send_text(message_json)
            self.stats["total_messages_sent"] += 1
            return True

        except Exception as e:
            self.stats["total_messages_failed"] += 1
            logger.error(f"Failed to send message: {e}")
            self.disconnect(websocket)
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        return {
            **self.stats,
            "active_connections": len(self.active_connections),
            "avg_messages_per_connection": (
                self.stats["total_messages_sent"] / self.stats["total_connections"]
                if self.stats["total_connections"] > 0
                else 0.0
            ),
        }


# Global WebSocket manager instances
_event_manager: Optional[WebSocketManager] = None
_tracking_manager: Optional[WebSocketManager] = None


def get_event_manager() -> WebSocketManager:
    """이벤트 WebSocket 매니저 싱글톤 인스턴스"""
    global _event_manager
    if _event_manager is None:
        _event_manager = WebSocketManager()
    return _event_manager


def get_tracking_manager() -> WebSocketManager:
    """추적 WebSocket 매니저 싱글톤 인스턴스"""
    global _tracking_manager
    if _tracking_manager is None:
        _tracking_manager = WebSocketManager()
    return _tracking_manager


# Event Queue for async processing
event_queue: asyncio.Queue = asyncio.Queue(maxsize=1000)


async def event_broadcaster_task():
    """
    이벤트 큐에서 이벤트를 가져와 WebSocket으로 브로드캐스트하는 백그라운드 태스크
    """
    manager = get_event_manager()

    logger.info("Event broadcaster task started")

    while True:
        try:
            # Get event from queue
            event_data = await event_queue.get()

            # Broadcast to all connected clients
            await manager.broadcast(
                message=event_data,
                event_type=event_data.get("event_type"),
            )

            event_queue.task_done()

        except asyncio.CancelledError:
            logger.info("Event broadcaster task cancelled")
            break

        except Exception as e:
            logger.error(f"Error in event broadcaster: {e}")
            await asyncio.sleep(0.1)


def queue_event(event_data: Dict[str, Any]) -> bool:
    """
    이벤트를 큐에 추가

    Args:
        event_data: 이벤트 데이터

    Returns:
        성공 여부
    """
    try:
        event_queue.put_nowait(event_data)
        return True
    except asyncio.QueueFull:
        logger.error("Event queue is full, dropping event")
        return False
