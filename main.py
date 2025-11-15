from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import asyncio
import json
import base64
import cv2
import numpy as np
import time
from typing import List, Optional
from datetime import datetime

from zmq_frame_receiver import ZMQFrameReceiver
from config import settings

# AI Detection modules
from detection.motion import MotionDetector
from detection.person import PersonDetector
from detection.structure import StructureDetector
from ai.ollama_client import create_ollama_client
from ai.analyzer import ImageAnalyzer

# Multimodal System modules
from sync.frame_sync import FrameSynchronizer
from tracking.movement import MovementTracker
from events.detector import EventDetector
from db.database import get_database
from api.websocket.events import (
    get_event_manager,
    get_tracking_manager,
    event_broadcaster_task,
    queue_event,
)

# Import multimodal routes
from api.multimodal_routes import router as multimodal_router

app = FastAPI(
    title="Multimodal Vision AI System",
    description="2D CCTV + 3D ZED Camera 통합 실시간 행동/거리 변화 감지 시스템",
    version="3.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for WebSocket
    allow_credentials=False,  # Must be False when allow_origins is "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include multimodal API routes
app.include_router(multimodal_router)

# Global instances
frame_receiver: Optional[ZMQFrameReceiver] = None
active_connections: List[WebSocket] = []

# AI detection instances
motion_detector: Optional[MotionDetector] = None
person_detector: Optional[PersonDetector] = None
structure_detector: Optional[StructureDetector] = None
image_analyzer: Optional[ImageAnalyzer] = None

# Multimodal system instances
frame_synchronizer: Optional[FrameSynchronizer] = None
movement_tracker: Optional[MovementTracker] = None
event_detector: Optional[EventDetector] = None
broadcaster_task: Optional[asyncio.Task] = None
detection_task: Optional[asyncio.Task] = None


async def ai_detection_loop():
    """
    실시간 AI 탐지 루프
    카메라 프레임을 지속적으로 가져와 AI 모델로 분석하고 이벤트 생성
    """
    global frame_receiver, person_detector, motion_detector, structure_detector
    global frame_synchronizer, movement_tracker, event_detector

    print("🤖 AI Detection Loop started")

    frame_count = 0
    last_frame_time = None

    while True:
        try:
            if not frame_receiver:
                await asyncio.sleep(1)
                continue

            # 프레임 가져오기
            rgb_frame = frame_receiver.get_rgb_frame()
            depth_frame = frame_receiver.get_depth_frame()

            # Check if frame exists
            if rgb_frame is None:
                await asyncio.sleep(0.1)
                continue

            try:
                if rgb_frame.size == 0:
                    await asyncio.sleep(0.1)
                    continue
            except (AttributeError, TypeError):
                await asyncio.sleep(0.1)
                continue

            frame_count += 1
            current_time = time.time()

            # FPS 계산 (1초마다)
            if last_frame_time and (current_time - last_frame_time) >= 1.0:
                fps = frame_count / (current_time - last_frame_time)
                frame_count = 0
                last_frame_time = current_time
            elif not last_frame_time:
                last_frame_time = current_time

            # Person Detection
            if person_detector:
                detections, _ = person_detector.detect(rgb_frame)

                if len(detections) > 0:
                    print(f"🔍 Detected {len(detections)} person(s) at frame {frame_count}")

                for idx, detection in enumerate(detections):
                    track_id = detection.get("track_id")
                    obj_id = f"person_{track_id}" if track_id else f"person_{frame_count}_{idx}"
                    confidence = detection.get("confidence", 0.0)
                    bbox = detection.get("bbox", [0, 0, 0, 0])

                    # 중심점 계산
                    center_x = int((bbox[0] + bbox[2]) / 2)
                    center_y = int((bbox[1] + bbox[3]) / 2)

                    # 3D 위치 가져오기 (depth 있을 경우)
                    position_3d = [center_x / 100.0, center_y / 100.0, 0.0]
                    try:
                        if depth_frame is not None and depth_frame.size > 0:
                            if center_y < depth_frame.shape[0] and center_x < depth_frame.shape[1]:
                                depth_value = depth_frame[center_y, center_x]

                                # Extract scalar value - handle all numpy types
                                if hasattr(depth_value, 'item'):
                                    depth_value = float(depth_value.item())
                                elif hasattr(depth_value, '__len__'):
                                    # It's an array-like object
                                    depth_value = float(depth_value.flat[0])
                                else:
                                    depth_value = float(depth_value)

                                if depth_value > 0:
                                    position_3d[2] = depth_value / 1000.0  # mm to meters
                    except (ValueError, TypeError, IndexError, AttributeError) as e:
                        # Silently handle depth extraction errors
                        pass

                    # Movement Tracking
                    if movement_tracker:
                        movement_data = movement_tracker.update_position(
                            object_id=obj_id,
                            position=position_3d,
                            timestamp=datetime.now()
                        )

                        # Event Detection
                        if event_detector and movement_data:
                            events = event_detector.check_events(
                                object_id=obj_id,
                                position=position_3d,
                                movement_data=movement_data,
                                camera_id="zed_2i"
                            )

                            # 이벤트를 큐에 추가
                            for event in events:
                                print(f"📢 Event detected: {event['type']} for {obj_id}")

                                event_data = {
                                    "event_id": int(time.time() * 1000),
                                    "timestamp": datetime.now().isoformat(),
                                    "event_type": event["type"],
                                    "camera_id": "zed_2i",
                                    "camera_name": "ZED 2i Stereo Camera",
                                    "object_id": obj_id,
                                    "confidence": confidence,
                                    "position_x": position_3d[0],
                                    "position_y": position_3d[1],
                                    "position_z": position_3d[2],
                                    "movement_distance": movement_data.get("distance_moved", 0.0),
                                    "movement_speed": movement_data.get("speed", 0.0),
                                    "zone_name": event.get("zone_name", "전체 영역"),
                                }

                                # 큐에 이벤트 추가
                                queue_event(event_data)

                                # DB에도 저장
                                try:
                                    db = get_database()
                                    db.insert_event(event_data)
                                except Exception as e:
                                    print(f"⚠️ DB insert error: {e}")

            # 프레임 처리 간격 (약 10 FPS)
            await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            print("🛑 AI Detection Loop cancelled")
            break
        except Exception as e:
            import traceback
            print(f"⚠️ Detection loop error: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            await asyncio.sleep(1)


@app.on_event("startup")
async def startup_event():
    """Initialize all system modules on startup"""
    global frame_receiver, motion_detector, person_detector, structure_detector, image_analyzer
    global frame_synchronizer, movement_tracker, event_detector, broadcaster_task, detection_task

    print("\n" + "=" * 60)
    print("🚀 Multimodal Vision AI System Starting...")
    print("=" * 60 + "\n")

    # 1. Database initialization
    try:
        db = get_database()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

    # 2. ZMQ Frame Receiver
    try:
        frame_receiver = ZMQFrameReceiver(zmq_host="localhost", zmq_port=5555)
        frame_receiver.start_receiving()
        print("✅ ZMQ Frame Receiver initialized")
    except Exception as e:
        print(f"❌ Frame receiver initialization failed: {e}")

    # 3. AI Detection Modules
    try:
        import os
        motion_threshold = int(os.getenv("MOTION_THRESHOLD", "500"))
        person_confidence = float(os.getenv("PERSON_CONFIDENCE", "0.5"))
        structure_sensitivity = float(os.getenv("STRUCTURE_SENSITIVITY", "0.01"))

        motion_detector = MotionDetector(min_area=motion_threshold)
        print("✅ Motion Detector initialized")

        person_detector = PersonDetector(confidence_threshold=person_confidence)
        print("✅ Person Detector initialized (YOLOv8)")

        structure_detector = StructureDetector(sensitivity=structure_sensitivity)
        print("✅ Structure Detector initialized")

        image_analyzer = ImageAnalyzer()
        print("✅ Image Analyzer initialized (Ollama)")

    except Exception as e:
        print(f"❌ AI modules initialization failed: {e}")

    # 4. Multimodal System Components
    try:
        # Frame Synchronizer
        tolerance_ms = int(os.getenv("FRAME_SYNC_TOLERANCE_MS", "100"))
        frame_synchronizer = FrameSynchronizer(tolerance_ms=tolerance_ms)
        print("✅ Frame Synchronizer initialized")

        # Movement Tracker
        idle_threshold = float(os.getenv("IDLE_THRESHOLD_M", "0.1"))
        idle_duration = float(os.getenv("IDLE_DURATION_SEC", "10.0"))
        movement_tracker = MovementTracker(
            idle_threshold_m=idle_threshold,
            idle_duration_sec=idle_duration
        )
        print("✅ Movement Tracker initialized")

        # Event Detector
        distance_threshold = float(os.getenv("DISTANCE_ALERT_THRESHOLD_M", "0.5"))
        speed_threshold = float(os.getenv("SPEED_ALERT_THRESHOLD_MS", "2.0"))
        event_detector = EventDetector(
            distance_alert_threshold_m=distance_threshold,
            speed_alert_threshold_ms=speed_threshold
        )
        print("✅ Event Detector initialized")

        # Load zones from database
        zones = db.get_zones()
        for zone_data in zones:
            import json
            polygon_points = json.loads(zone_data["polygon_points"])
            rules = json.loads(zone_data["rules_json"]) if zone_data["rules_json"] else {}

            event_detector.add_zone(
                zone_id=zone_data["zone_id"],
                name=zone_data["name"],
                camera_id=zone_data["camera_id"],
                polygon_points=polygon_points,
                zone_type=zone_data["zone_type"],
                rules=rules
            )
        print(f"✅ Loaded {len(zones)} zones from database")

    except Exception as e:
        print(f"❌ Multimodal system initialization failed: {e}")
        import traceback
        traceback.print_exc()

    # 5. Start WebSocket Event Broadcaster
    try:
        broadcaster_task = asyncio.create_task(event_broadcaster_task())
        print("✅ WebSocket Event Broadcaster started")
    except Exception as e:
        print(f"❌ Event broadcaster failed: {e}")

    # 6. Start AI Detection Loop
    try:
        detection_task = asyncio.create_task(ai_detection_loop())
        print("✅ AI Detection Loop started")
    except Exception as e:
        print(f"❌ AI Detection Loop failed: {e}")

    print("\n" + "=" * 60)
    print("✅ System initialization complete!")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop all modules on shutdown"""
    global frame_receiver, broadcaster_task, detection_task

    print("\n🛑 Shutting down system...")

    if detection_task:
        detection_task.cancel()
        try:
            await detection_task
        except asyncio.CancelledError:
            pass
        print("✅ AI Detection Loop stopped")

    if broadcaster_task:
        broadcaster_task.cancel()
        try:
            await broadcaster_task
        except asyncio.CancelledError:
            pass
        print("✅ Event broadcaster stopped")

    print("✅ Shutdown complete\n")


@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Multimodal Vision AI System",
        "version": "3.0.0",
        "description": "2D CCTV + 3D ZED Camera 통합 실시간 행동/거리 변화 감지 시스템",
        "status": "running",
        "camera_active": frame_receiver.is_receiving() if frame_receiver else False,
        "components": {
            "frame_receiver": frame_receiver is not None,
            "frame_synchronizer": frame_synchronizer is not None,
            "movement_tracker": movement_tracker is not None,
            "event_detector": event_detector is not None,
            "motion_detector": motion_detector is not None,
            "person_detector": person_detector is not None,
            "structure_detector": structure_detector is not None,
            "image_analyzer": image_analyzer is not None,
        }
    }


@app.get("/api/system/health")
async def system_health():
    """시스템 헬스 체크"""
    health_status = {
        "timestamp": datetime.now().isoformat(),
        "status": "healthy",
        "components": {}
    }

    # Frame Receiver
    if frame_receiver:
        health_status["components"]["frame_receiver"] = {
            "status": "active" if frame_receiver.is_receiving() else "inactive",
            "healthy": frame_receiver.is_receiving()
        }
    else:
        health_status["components"]["frame_receiver"] = {
            "status": "not_initialized",
            "healthy": False
        }

    # Movement Tracker
    if movement_tracker:
        stats = movement_tracker.get_statistics()
        health_status["components"]["movement_tracker"] = {
            "status": "active",
            "healthy": True,
            "active_objects": stats["active_objects"]
        }

    # Event Detector
    if event_detector:
        health_status["components"]["event_detector"] = {
            "status": "active",
            "healthy": True,
            "zones_count": len(event_detector.zones)
        }

    # Overall health
    all_healthy = all(
        comp.get("healthy", False)
        for comp in health_status["components"].values()
    )
    health_status["status"] = "healthy" if all_healthy else "degraded"

    return health_status


@app.get("/api/camera/status")
async def camera_status():
    """Get camera status"""
    if not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Frame receiver not initialized"}
        )

    return {
        "is_receiving": frame_receiver.is_receiving(),
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/camera/info")
async def camera_info():
    """Get camera information"""
    return {
        "resolution": settings.camera_resolution,
        "fps": settings.camera_fps,
        "depth_mode": settings.depth_mode,
        "stream_fps": settings.stream_fps,
        "jpeg_quality": settings.jpeg_quality
    }


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time camera streaming (Deprecated - use MJPEG streams instead)"""
    await websocket.accept()
    active_connections.append(websocket)

    try:
        print(f"[STREAM] Client connected: {websocket.client}", flush=True)

        await websocket.send_json({
            "type": "connected",
            "message": "Connected to ZED camera stream",
            "note": "WebSocket streaming deprecated - use MJPEG streams (/stream/rgb, /stream/depth)"
        })

        while True:
            await asyncio.sleep(1.0)

    except WebSocketDisconnect:
        print(f"[STREAM] Client disconnected: {websocket.client}", flush=True)
    except Exception as e:
        print(f"[STREAM] WebSocket error: {e}", flush=True)
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


async def generate_mjpeg_stream_rgb():
    """Generate MJPEG stream from ZMQ RGB frames"""
    while True:
        try:
            if frame_receiver:
                frame = frame_receiver.get_rgb_frame()
                if frame is not None:
                    _, jpeg_bytes = cv2.imencode('.jpg', frame,
                                                  [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes.tobytes() + b'\r\n')
            await asyncio.sleep(1.0 / settings.stream_fps)
        except Exception as e:
            print(f"RGB stream error: {e}")
            break


async def generate_mjpeg_stream_depth():
    """Generate MJPEG stream from ZMQ depth frames"""
    while True:
        try:
            if frame_receiver:
                frame = frame_receiver.get_depth_frame()
                if frame is not None:
                    _, jpeg_bytes = cv2.imencode('.jpg', frame,
                                                  [cv2.IMWRITE_JPEG_QUALITY, settings.jpeg_quality])
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + jpeg_bytes.tobytes() + b'\r\n')
            await asyncio.sleep(1.0 / settings.stream_fps)
        except Exception as e:
            print(f"Depth stream error: {e}")
            break


@app.get("/stream/rgb")
async def stream_rgb():
    """MJPEG stream endpoint for RGB camera"""
    return StreamingResponse(
        generate_mjpeg_stream_rgb(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/stream/depth")
async def stream_depth():
    """MJPEG stream endpoint for depth map"""
    return StreamingResponse(
        generate_mjpeg_stream_depth(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


# ============== AI Detection Endpoints ==============

@app.post("/api/ai/motion/detect")
async def detect_motion(camera_id: str = "zed_rgb"):
    """현재 프레임에서 모션 감지"""
    if not motion_detector or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Motion detector not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    bboxes, fg_mask = motion_detector.detect(rgb_frame, camera_id)

    return {
        "timestamp": datetime.now().isoformat(),
        "camera_id": camera_id,
        "motion_detected": len(bboxes) > 0,
        "bounding_boxes": bboxes,
        "detection_count": len(bboxes)
    }


@app.post("/api/ai/person/detect")
async def detect_person(camera_id: str = "zed_rgb"):
    """현재 프레임에서 사람 감지 (YOLO)"""
    if not person_detector or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Person detector not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    detections, annotated_frame = person_detector.detect(rgb_frame, camera_id, track=True)

    return {
        "timestamp": datetime.now().isoformat(),
        "camera_id": camera_id,
        "persons_detected": len(detections) > 0,
        "person_count": len(detections),
        "detections": detections
    }


@app.post("/api/ai/structure/set-baseline")
async def set_structure_baseline(camera_id: str = "zed_rgb"):
    """구조 변화 감지를 위한 기준선 설정"""
    if not structure_detector or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Structure detector not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    depth_map = frame_receiver.get_depth_frame()

    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    success = structure_detector.set_baseline(rgb_frame, depth_map, camera_id)

    if success:
        return {
            "timestamp": datetime.now().isoformat(),
            "camera_id": camera_id,
            "baseline_set": True,
            "message": "Baseline successfully set"
        }
    else:
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to set baseline"}
        )


@app.post("/api/ai/structure/detect")
async def detect_structure_change(camera_id: str = "zed_rgb"):
    """구조 변화 감지 및 mm 단위 측정"""
    if not structure_detector or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Structure detector not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    depth_map = frame_receiver.get_depth_frame()

    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    displacement_mm, displacement_px, annotated = structure_detector.detect_changes(
        rgb_frame, depth_map, camera_id
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "camera_id": camera_id,
        "change_detected": displacement_mm > 0.5,
        "displacement_mm": displacement_mm,
        "displacement_pixels": displacement_px
    }


@app.post("/api/ai/analyze/scene")
async def analyze_scene(camera_id: str = "zed_rgb"):
    """AI 장면 분석 (Ollama)"""
    if not image_analyzer or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Image analyzer not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    result = image_analyzer.analyze_scene(rgb_frame, camera_id, analysis_type="describe")

    return {
        "timestamp": result.timestamp,
        "camera_id": result.camera_id,
        "description": result.description,
        "anomalies": result.anomalies,
        "confidence": result.confidence,
        "processing_time": result.processing_time
    }


@app.post("/api/ai/analyze/anomaly")
async def analyze_anomaly(camera_id: str = "zed_rgb"):
    """이상 상황 감지 (Ollama)"""
    if not image_analyzer or not frame_receiver:
        return JSONResponse(
            status_code=503,
            content={"error": "Image analyzer not initialized"}
        )

    rgb_frame = frame_receiver.get_rgb_frame()
    if rgb_frame is None:
        return JSONResponse(
            status_code=404,
            content={"error": "No frame available"}
        )

    result = image_analyzer.analyze_scene(rgb_frame, camera_id, analysis_type="anomaly")

    return {
        "timestamp": result.timestamp,
        "camera_id": result.camera_id,
        "anomalies_detected": len(result.anomalies) > 0,
        "anomalies": result.anomalies,
        "description": result.description,
        "confidence": result.confidence
    }


@app.get("/api/ai/stats")
async def get_ai_stats():
    """AI 감지 모듈 통계"""
    stats = {
        "timestamp": datetime.now().isoformat(),
        "motion": motion_detector.get_recent_events(5) if motion_detector else [],
        "person": person_detector.get_statistics() if person_detector else {},
        "structure": structure_detector.get_change_history(days=1) if structure_detector else [],
        "analyzer": image_analyzer.get_statistics() if image_analyzer else {}
    }

    return stats


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
