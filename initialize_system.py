"""
시스템 초기화 스크립트
데이터베이스 초기화 및 카메라/구역 기본 설정
"""

from db.database import get_database
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def initialize_cameras():
    """카메라 정보 초기화"""
    db = get_database()

    cameras = [
        {
            "camera_id": "zed_2i",
            "camera_name": "ZED 2i Stereo Camera",
            "camera_type": "zed",
            "stream_url": "tcp://localhost:5555",
            "connection_type": "zmq",
            "resolution": {"width": 672, "height": 376},  # VGA
            "fps": 15,
        },
        {
            "camera_id": "hanwha_cctv",
            "camera_name": "Hanwha Wisenet CCTV",
            "camera_type": "cctv",
            "stream_url": "rtsp://admin:softway7&@192.168.1.50:554/profile1/media.smp",
            "connection_type": "rtsp",
            "resolution": {"width": 1920, "height": 1080},
            "fps": 30,
        },
    ]

    for camera in cameras:
        db.insert_or_update_camera(**camera)
        logger.info(f"✅ Camera initialized: {camera['camera_name']}")


def initialize_default_zones():
    """기본 구역 설정"""
    db = get_database()

    zones = [
        {
            "name": "전체 영역",
            "camera_id": "zed_2i",
            "polygon_points": [[0, 0], [672, 0], [672, 376], [0, 376]],
            "zone_type": "monitoring",
            "rules": {
                "entry": True,
                "exit": True,
                "idle_threshold_sec": 10,
                "speed_alert": True,
            },
        },
        {
            "name": "제한 구역 예시",
            "camera_id": "zed_2i",
            "polygon_points": [[200, 150], [450, 150], [450, 300], [200, 300]],
            "zone_type": "restricted",
            "rules": {
                "entry": True,
                "exit": True,
                "alert_on_entry": True,
            },
        },
    ]

    for zone in zones:
        zone_id = db.insert_zone(**zone)
        logger.info(f"✅ Zone created: {zone['name']} (ID: {zone_id})")


def initialize_system_config():
    """시스템 설정 확인 (이미 schema.sql에서 초기화됨)"""
    db = get_database()

    # Verify config
    tolerance = db.get_config("frame_sync_tolerance_ms")
    logger.info(f"✅ System config loaded: frame_sync_tolerance_ms = {tolerance}")


def main():
    """시스템 초기화 메인 함수"""
    logger.info("=" * 60)
    logger.info("멀티모달 비전 AI 시스템 초기화")
    logger.info("=" * 60)

    try:
        # Initialize database (already done by DatabaseManager)
        logger.info("\n[1/3] 데이터베이스 초기화")
        db = get_database()
        logger.info("✅ Database initialized")

        # Initialize cameras
        logger.info("\n[2/3] 카메라 정보 초기화")
        initialize_cameras()

        # Initialize default zones
        logger.info("\n[3/3] 기본 구역 설정")
        initialize_default_zones()

        # Verify system config
        logger.info("\n[시스템 설정 확인]")
        initialize_system_config()

        logger.info("\n" + "=" * 60)
        logger.info("✅ 시스템 초기화 완료!")
        logger.info("=" * 60)

        # Print summary
        cameras = db.get_cameras()
        zones = db.get_zones()
        logger.info(f"\n📊 초기화 요약:")
        logger.info(f"  - 카메라: {len(cameras)}개")
        logger.info(f"  - 구역: {len(zones)}개")

    except Exception as e:
        logger.error(f"\n❌ 초기화 실패: {e}")
        raise


if __name__ == "__main__":
    main()
