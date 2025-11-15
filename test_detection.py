#!/usr/bin/env python3
"""
Test AI Detection System
실시간으로 사람 감지를 테스트합니다
"""
import asyncio
import sys
from detection.person import PersonDetector
from zmq_frame_receiver import ZMQFrameReceiver

async def test_detection():
    """Test person detection with ZMQ frames"""
    print("=" * 60)
    print("AI Detection Test Starting...")
    print("=" * 60)

    # Initialize modules
    print("\n1. Initializing ZMQ Frame Receiver...")
    frame_receiver = ZMQFrameReceiver()
    await asyncio.sleep(2)  # Wait for connection

    print("2. Initializing Person Detector...")
    person_detector = PersonDetector()

    print("\n3. Starting detection loop...")
    print("   Move in front of the camera to test detection")
    print("   Press Ctrl+C to stop\n")

    frame_count = 0
    detection_count = 0

    try:
        while True:
            # Get frame
            rgb_frame = frame_receiver.get_rgb_frame()

            if rgb_frame is not None:
                try:
                    if rgb_frame.size > 0:
                        frame_count += 1

                        # Run detection
                        detections, _ = person_detector.detect(rgb_frame)

                        if len(detections) > 0:
                            detection_count += 1
                            print(f"🔍 Frame {frame_count}: Detected {len(detections)} person(s)")
                            for idx, det in enumerate(detections):
                                conf = det.get('confidence', 0)
                                bbox = det.get('bbox', [])
                                print(f"   Person {idx+1}: confidence={conf:.2f}, bbox={bbox}")
                        else:
                            if frame_count % 10 == 0:
                                print(f"⚪ Frame {frame_count}: No person detected")

                except (AttributeError, TypeError):
                    pass

            await asyncio.sleep(0.1)  # 10 FPS

    except KeyboardInterrupt:
        print(f"\n\nTest completed:")
        print(f"  Total frames: {frame_count}")
        print(f"  Detections: {detection_count}")
        print(f"  Detection rate: {detection_count/frame_count*100:.1f}%" if frame_count > 0 else "  No frames received")

if __name__ == "__main__":
    asyncio.run(test_detection())
