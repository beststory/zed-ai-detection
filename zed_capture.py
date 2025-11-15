#!/usr/bin/env python3
"""
ZED Camera Capture Process
Runs independently from FastAPI to avoid CUDA context conflicts.
Streams frames via ZMQ PUB/SUB pattern.
"""
import sys
import time
import zmq
import cv2
import numpy as np
from datetime import datetime

# Force unbuffered output
sys.stdout = open(sys.stdout.fileno(), 'w', buffering=1)
sys.stderr = open(sys.stderr.fileno(), 'w', buffering=1)

try:
    import pyzed.sl as sl
    ZED_AVAILABLE = True
except ImportError:
    ZED_AVAILABLE = False
    print("Warning: pyzed module not found. Using mock camera.")


class ZEDCaptureProcess:
    def __init__(self, zmq_port=5555):
        self.zmq_port = zmq_port
        self.camera = None
        self.mock_mode = not ZED_AVAILABLE
        self.running = False

        # Setup ZMQ
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PUB)
        self.socket.bind(f"tcp://*:{zmq_port}")
        print(f"ZMQ publisher bound to tcp://*:{zmq_port}")

    def init_camera(self):
        """Initialize ZED camera"""
        print(f"[INIT] Starting camera initialization... mock_mode={self.mock_mode}", flush=True)

        if self.mock_mode:
            print("[INIT] Running in MOCK mode - ZED SDK not available", flush=True)
            return True

        try:
            print("[INIT] Creating ZED Camera object...", flush=True)
            self.camera = sl.Camera()

            init_params = sl.InitParameters()
            init_params.camera_resolution = sl.RESOLUTION.VGA
            init_params.camera_fps = 15
            init_params.depth_mode = sl.DEPTH_MODE.ULTRA  # Enable depth sensing
            init_params.sdk_verbose = False  # Disable verbose to see our logs

            print("[INIT] Attempting to open ZED camera...", flush=True)
            err = self.camera.open(init_params)
            print(f"[INIT] Camera open result: {err}", flush=True)

            if err != sl.ERROR_CODE.SUCCESS:
                print(f"[INIT] Failed to open ZED camera: {err}", flush=True)
                print("[INIT] Falling back to MOCK mode", flush=True)
                self.mock_mode = True
                self.camera = None
                return True

            # Create Mat objects AFTER camera is opened
            self.image = sl.Mat()
            self.depth = sl.Mat()
            self.point_cloud = sl.Mat()

            # Enable Positional Tracking (required for sensors and body tracking)
            tracking_params = sl.PositionalTrackingParameters()
            err_tracking = self.camera.enable_positional_tracking(tracking_params)
            if err_tracking != sl.ERROR_CODE.SUCCESS:
                print(f"[INIT] Warning: Positional tracking failed: {err_tracking}")

            # Enable Body Tracking
            body_params = sl.BodyTrackingParameters()
            body_params.enable_tracking = True
            body_params.enable_body_fitting = False
            body_params.detection_model = sl.BODY_TRACKING_MODEL.HUMAN_BODY_FAST
            body_params.body_format = sl.BODY_FORMAT.BODY_18

            err_body = self.camera.enable_body_tracking(body_params)
            if err_body != sl.ERROR_CODE.SUCCESS:
                print(f"[INIT] Warning: Body tracking initialization failed: {err_body}")
                self.body_tracking_enabled = False
            else:
                print("[INIT] Body tracking enabled successfully!")
                self.body_tracking_enabled = True
                self.bodies = sl.Bodies()

            # Runtime parameters
            self.runtime_parameters = sl.RuntimeParameters()
            self.body_runtime_params = sl.BodyTrackingRuntimeParameters()

            # Sensor data
            self.sensors_data = sl.SensorsData()

            # Test grab
            test_grab = self.camera.grab(self.runtime_parameters)
            if test_grab != sl.ERROR_CODE.SUCCESS:
                print(f"ZED camera opened but stream failed: {test_grab}")
                print("Falling back to MOCK mode")
                self.camera.close()
                self.camera = None
                self.mock_mode = True
                return True

            print("ZED Camera initialized successfully!")
            print(f"[INIT] Body Tracking: {'ENABLED' if self.body_tracking_enabled else 'DISABLED'}")
            return True

        except Exception as e:
            print(f"Error initializing camera: {e}")
            print("Falling back to MOCK mode")
            self.mock_mode = True
            self.camera = None
            return True

    def generate_mock_frame(self, frame_type='rgb'):
        """Generate mock frames for testing"""
        if frame_type == 'rgb':
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(img, "ZED CAMERA - MOCK MODE", (50, 360),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
            cv2.putText(img, datetime.now().strftime("%H:%M:%S.%f")[:-3], (50, 420),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (200, 200, 200), 2)
            cv2.putText(img, "Process separation working!", (50, 480),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100, 255, 100), 2)
            return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            depth = np.random.rand(720, 1280).astype(np.float32) * 5.0
            depth_normalized = np.clip(depth, 0, 10)
            depth_normalized = (depth_normalized / 10.0 * 255).astype(np.uint8)
            depth_colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
            return depth_colored

    def grab_and_publish(self):
        """Main loop: grab frames and publish via ZMQ"""
        frame_count = 0
        last_fps_time = time.time()
        fps = 0

        while self.running:
            try:
                # Get RGB frame
                if self.mock_mode:
                    rgb_frame = self.generate_mock_frame('rgb')
                    depth_frame = self.generate_mock_frame('depth')
                else:
                    if self.camera.grab(self.runtime_parameters) != sl.ERROR_CODE.SUCCESS:
                        print("Failed to grab frame")
                        time.sleep(0.01)
                        continue

                    self.camera.retrieve_image(self.image, sl.VIEW.LEFT)
                    rgb_frame = self.image.get_data()[:, :, :3]

                    # Retrieve real depth data
                    self.camera.retrieve_measure(self.depth, sl.MEASURE.DEPTH)
                    depth_data = self.depth.get_data()

                    # Remove invalid values (NaN, inf)
                    depth_valid = np.nan_to_num(depth_data, nan=0.0, posinf=0.0, neginf=0.0)

                    # Apply light Gaussian blur to reduce noise while preserving edges
                    depth_smoothed = cv2.GaussianBlur(depth_valid, (3, 3), 0)

                    # Adaptive range adjustment: use percentile for better contrast
                    valid_depths = depth_smoothed[depth_smoothed > 0]
                    if len(valid_depths) > 0:
                        # Use 0.5 and 99.5 percentile for even finer range control
                        min_depth = np.percentile(valid_depths, 0.5)
                        max_depth = np.percentile(valid_depths, 99.5)

                        # Clip to adaptive range
                        depth_clipped = np.clip(depth_smoothed, min_depth, max_depth)

                        # Normalize to 0-255 range
                        if max_depth > min_depth:
                            depth_normalized = ((depth_clipped - min_depth) / (max_depth - min_depth) * 255).astype(np.uint8)
                        else:
                            depth_normalized = np.zeros_like(depth_valid, dtype=np.uint8)

                        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
                        # for much better local contrast while preventing over-amplification
                        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                        depth_enhanced = clahe.apply(depth_normalized)

                        # Apply bilateral filter to preserve edges while smoothing
                        depth_refined = cv2.bilateralFilter(depth_enhanced, 5, 50, 50)

                        # Apply TURBO colormap (best color gradient with smooth transitions)
                        depth_frame = cv2.applyColorMap(depth_refined, cv2.COLORMAP_TURBO)
                    else:
                        # Fallback to black image if no valid depth
                        depth_frame = np.zeros((depth_valid.shape[0], depth_valid.shape[1], 3), dtype=np.uint8)

                # Encode frames to JPEG
                _, rgb_buffer = cv2.imencode('.jpg', cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR),
                                             [cv2.IMWRITE_JPEG_QUALITY, 80])
                _, depth_buffer = cv2.imencode('.jpg', depth_frame,
                                               [cv2.IMWRITE_JPEG_QUALITY, 80])

                # Publish RGB and Depth via ZMQ
                self.socket.send_multipart([b'rgb', rgb_buffer.tobytes()])
                self.socket.send_multipart([b'depth', depth_buffer.tobytes()])

                # Point Cloud - send every 3 frames to reduce bandwidth
                if not self.mock_mode and frame_count % 3 == 0:
                    self.camera.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
                    pc_data = self.point_cloud.get_data()

                    # Downsample point cloud (stride by 4 for performance)
                    pc_downsampled = pc_data[::4, ::4].copy()

                    # Send point cloud as binary numpy array
                    pc_buffer = pc_downsampled.tobytes()
                    pc_shape = f"{pc_downsampled.shape[0]},{pc_downsampled.shape[1]}".encode()
                    self.socket.send_multipart([b'pointcloud', pc_shape, pc_buffer])

                # Body Tracking - send skeleton data if enabled
                if not self.mock_mode and hasattr(self, 'body_tracking_enabled') and self.body_tracking_enabled:
                    self.camera.retrieve_bodies(self.bodies, self.body_runtime_params)

                    body_list = []
                    for i in range(self.bodies.body_list.__len__()):
                        body = self.bodies.body_list[i]
                        if body.tracking_state == sl.OBJECT_TRACKING_STATE.OK:
                            # Extract skeleton keypoints
                            keypoints = []
                            for kp in body.keypoint:
                                keypoints.append([kp[0], kp[1], kp[2]])  # x, y, z coordinates

                            body_data = {
                                'id': int(body.id),
                                'confidence': float(body.confidence),
                                'keypoints': keypoints
                            }
                            body_list.append(body_data)

                    if body_list:
                        import json
                        body_json = json.dumps(body_list).encode()
                        self.socket.send_multipart([b'bodies', body_json])

                # Sensor Data - send IMU and environmental sensors
                if not self.mock_mode and frame_count % 2 == 0:
                    self.camera.get_sensors_data(self.sensors_data, sl.TIME_REFERENCE.IMAGE)
                    imu_data = self.sensors_data.get_imu_data()

                    # Extract sensor readings
                    accel = imu_data.get_linear_acceleration()
                    gyro = imu_data.get_angular_velocity()

                    # Get environmental sensors
                    mag_data = self.sensors_data.get_magnetometer_data()
                    baro_data = self.sensors_data.get_barometer_data()
                    temp = self.sensors_data.get_temperature_data()

                    # Temperature data - get value directly
                    try:
                        temp_value = temp[sl.SENSOR_LOCATION.ONBOARD_LEFT] if hasattr(temp, '__getitem__') else 0.0
                    except:
                        temp_value = 0.0

                    sensor_dict = {
                        'accel': [float(accel[0]), float(accel[1]), float(accel[2])],
                        'gyro': [float(gyro[0]), float(gyro[1]), float(gyro[2])],
                        'mag': [float(mag_data.get_magnetic_field_calibrated()[0]),
                                float(mag_data.get_magnetic_field_calibrated()[1]),
                                float(mag_data.get_magnetic_field_calibrated()[2])],
                        'pressure': float(baro_data.pressure),
                        'temperature': float(temp_value)
                    }

                    import json
                    sensor_json = json.dumps(sensor_dict).encode()
                    self.socket.send_multipart([b'sensors', sensor_json])

                # FPS calculation
                frame_count += 1
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    fps = frame_count / (current_time - last_fps_time)
                    if frame_count % 30 == 0:
                        print(f"Capture FPS: {fps:.1f} | Mode: {'MOCK' if self.mock_mode else 'ZED'}")
                    frame_count = 0
                    last_fps_time = current_time

                # Frame rate limiting (15 FPS target)
                time.sleep(1.0 / 15.0)

            except KeyboardInterrupt:
                print("\nStopping capture...")
                break
            except Exception as e:
                print(f"Error in capture loop: {e}")
                time.sleep(0.1)

    def start(self):
        """Start capture process"""
        self.running = True
        self.grab_and_publish()

    def stop(self):
        """Stop capture and cleanup"""
        self.running = False
        if self.camera:
            self.camera.close()
        self.socket.close()
        self.context.term()
        print("Capture process stopped")


if __name__ == "__main__":
    print("ZED Camera Capture Process Starting...")
    print("=" * 60)

    capture = ZEDCaptureProcess(zmq_port=5555)

    if not capture.init_camera():
        print("Failed to initialize camera")
        sys.exit(1)

    print("\nCapture process ready. Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        capture.start()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        capture.stop()
