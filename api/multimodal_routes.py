"""
Multimodal Vision AI System API Routes
멀티모달 비전 AI 시스템 REST API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from db.database import get_database
from api.websocket.events import (
    get_event_manager,
    get_tracking_manager,
    queue_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["multimodal"])


# ==================== Events API ====================


@router.get("/events/latest")
async def get_latest_events(
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
):
    """
    최근 이벤트 조회

    Args:
        limit: 조회할 이벤트 개수 (1-500)
        event_type: 이벤트 타입 필터 (optional)

    Returns:
        이벤트 리스트
    """
    try:
        db = get_database()
        events = db.get_latest_events(limit=limit, event_type=event_type)

        return {"events": events, "count": len(events)}

    except Exception as e:
        logger.error(f"Failed to get latest events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/history")
async def get_events_history(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    camera_id: Optional[str] = None,
):
    """
    이벤트 히스토리 조회

    Args:
        start_time: 시작 시간 (ISO format)
        end_time: 종료 시간 (ISO format)
        camera_id: 카메라 ID 필터 (optional)

    Returns:
        이벤트 리스트
    """
    try:
        db = get_database()

        # Parse timestamps
        if not start_time:
            start_time = (datetime.now() - timedelta(hours=24)).isoformat()
        if not end_time:
            end_time = datetime.now().isoformat()

        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        events = db.get_events_by_time_range(
            start_time=start_dt, end_time=end_dt, camera_id=camera_id
        )

        return {
            "events": events,
            "count": len(events),
            "start_time": start_time,
            "end_time": end_time,
        }

    except Exception as e:
        logger.error(f"Failed to get events history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/{event_id}")
async def get_event_by_id(event_id: int):
    """특정 이벤트 상세 조회"""
    try:
        db = get_database()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Event not found")

            return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get event {event_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/events/stats")
async def get_event_statistics():
    """이벤트 통계 조회"""
    try:
        db = get_database()
        stats = db.get_event_statistics()

        return stats

    except Exception as e:
        logger.error(f"Failed to get event statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Movement Tracking API ====================


@router.get("/movement/tracking/{object_id}")
async def get_object_tracking(object_id: str, limit: int = Query(100, ge=1, le=500)):
    """
    객체 추적 정보 조회

    Args:
        object_id: 객체 ID
        limit: 위치 히스토리 개수

    Returns:
        객체 추적 정보 및 위치 히스토리
    """
    try:
        db = get_database()

        # Get object info
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM objects WHERE object_id = ?", (object_id,))
            object_row = cursor.fetchone()

            if not object_row:
                raise HTTPException(status_code=404, detail="Object not found")

            object_data = dict(object_row)

        # Get position history
        positions = db.get_object_position_history(object_id=object_id, limit=limit)

        return {"object": object_data, "positions": positions, "position_count": len(positions)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tracking for object {object_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/movement/active")
async def get_active_objects():
    """현재 추적 중인 활성 객체 목록 조회"""
    try:
        db = get_database()
        active_objects = db.get_active_objects()

        return {"objects": active_objects, "count": len(active_objects)}

    except Exception as e:
        logger.error(f"Failed to get active objects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Cameras API ====================


@router.get("/cameras/status")
async def get_cameras_status():
    """모든 카메라 상태 조회"""
    try:
        db = get_database()
        cameras = db.get_cameras()

        return {"cameras": cameras, "count": len(cameras)}

    except Exception as e:
        logger.error(f"Failed to get cameras status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cameras/calibration")
async def update_camera_calibration(camera_id: str, calibration_data: Dict[str, Any]):
    """
    카메라 캘리브레이션 설정

    Args:
        camera_id: 카메라 ID
        calibration_data: 캘리브레이션 데이터

    Returns:
        성공 메시지
    """
    try:
        db = get_database()

        with db.get_connection() as conn:
            cursor = conn.cursor()

            import json

            cursor.execute(
                """
                INSERT INTO calibration (
                    camera_id, transform_matrix, calibration_date
                ) VALUES (?, ?, ?)
                ON CONFLICT(camera_id) DO UPDATE SET
                    transform_matrix = excluded.transform_matrix,
                    calibration_date = excluded.calibration_date
                """,
                (
                    camera_id,
                    json.dumps(calibration_data.get("transform_matrix", [])),
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()

        logger.info(f"Calibration updated for camera: {camera_id}")

        return {"status": "success", "camera_id": camera_id}

    except Exception as e:
        logger.error(f"Failed to update calibration for {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cameras/health")
async def camera_health_check():
    """카메라 헬스 체크"""
    try:
        db = get_database()
        cameras = db.get_cameras()

        health_status = []
        for camera in cameras:
            status = {
                "camera_id": camera["camera_id"],
                "status": camera["status"],
                "last_frame": camera["last_frame_timestamp"],
                "healthy": camera["status"] == "active",
            }
            health_status.append(status)

        overall_healthy = all(cam["healthy"] for cam in health_status)

        return {
            "overall_status": "healthy" if overall_healthy else "degraded",
            "cameras": health_status,
        }

    except Exception as e:
        logger.error(f"Failed to perform health check: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Zones API ====================


@router.get("/zones")
async def get_zones(camera_id: Optional[str] = None):
    """모든 구역 조회"""
    try:
        db = get_database()
        zones = db.get_zones(camera_id=camera_id)

        return {"zones": zones, "count": len(zones)}

    except Exception as e:
        logger.error(f"Failed to get zones: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/zones")
async def create_zone(zone_data: Dict[str, Any]):
    """
    새 구역 생성

    Args:
        zone_data: 구역 데이터
            - name: 구역 이름
            - camera_id: 카메라 ID
            - polygon_points: 다각형 좌표 [[x1,y1], [x2,y2], ...]
            - zone_type: 구역 타입 (optional)
            - rules: 룰 설정 (optional)

    Returns:
        생성된 구역 정보
    """
    try:
        db = get_database()

        zone_id = db.insert_zone(
            name=zone_data["name"],
            camera_id=zone_data["camera_id"],
            polygon_points=zone_data["polygon_points"],
            zone_type=zone_data.get("zone_type", "monitoring"),
            rules=zone_data.get("rules"),
        )

        logger.info(f"Zone created: {zone_data['name']} (ID: {zone_id})")

        return {"status": "success", "zone_id": zone_id, "name": zone_data["name"]}

    except Exception as e:
        logger.error(f"Failed to create zone: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/zones/{zone_id}")
async def update_zone(zone_id: int, updates: Dict[str, Any]):
    """구역 수정"""
    try:
        db = get_database()
        db.update_zone(zone_id=zone_id, updates=updates)

        logger.info(f"Zone updated: ID {zone_id}")

        return {"status": "success", "zone_id": zone_id}

    except Exception as e:
        logger.error(f"Failed to update zone {zone_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/zones/{zone_id}")
async def delete_zone(zone_id: int):
    """구역 삭제"""
    try:
        db = get_database()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE zones SET enabled = 0 WHERE zone_id = ?", (zone_id,))
            conn.commit()

        logger.info(f"Zone deleted: ID {zone_id}")

        return {"status": "success", "zone_id": zone_id}

    except Exception as e:
        logger.error(f"Failed to delete zone {zone_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== WebSocket Endpoints ====================


@router.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """
    실시간 이벤트 스트리밍 WebSocket

    클라이언트는 연결 시 필터를 쿼리 파라미터로 전송할 수 있음:
    예: /ws/events?filter=zone_entry,fall
    """
    # Accept connection first (before manager)
    await websocket.accept()

    manager = get_event_manager()

    # Parse event type filters from query params
    filters = set()
    filter_param = websocket.query_params.get("filter")
    if filter_param:
        filters = set(filter_param.split(","))

    # Register with manager (don't call accept again)
    from collections import deque
    manager.active_connections.add(websocket)
    manager.client_filters[websocket] = filters or set()
    manager.message_queues[websocket] = deque(maxlen=manager.max_message_queue)
    manager.stats["total_connections"] += 1
    manager.stats["current_connections"] = len(manager.active_connections)

    logger.info(f"WebSocket client connected. Total: {manager.stats['current_connections']}, Filters: {filters or 'ALL'}")

    try:
        while True:
            # Keep connection alive and handle client messages
            data = await websocket.receive_text()

            # Handle client commands (optional)
            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from events stream")


@router.websocket("/ws/tracking")
async def websocket_tracking(websocket: WebSocket):
    """
    실시간 위치 추적 WebSocket

    클라이언트는 연결 시 객체 ID 필터를 쿼리 파라미터로 전송할 수 있음:
    예: /ws/tracking?object_id=person_001
    """
    manager = get_tracking_manager()

    await manager.connect(websocket)

    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong", "timestamp": datetime.now().isoformat()})

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Client disconnected from tracking stream")
