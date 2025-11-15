import numpy as np
import cv2
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime

try:
    import pyzed.sl as sl
    ZED_AVAILABLE = True
except ImportError:
    ZED_AVAILABLE = False
    print("Warning: pyzed module not found. Using mock camera for development.")


class ZEDCamera:
    def __init__(self, resolution="VGA", fps=15, depth_mode="NEURAL", force_mock=False):
        self.camera = None
        self.runtime_parameters = None
        self.image = None
        self.depth = None
        self.point_cloud = None
        self.objects = None
        self.is_opened = False

        # Mock mode for development without ZED SDK
        self.mock_mode = force_mock or not ZED_AVAILABLE
        self.opencv_mode = False  # Use OpenCV as fallback
        self.opencv_cap = None

        if not self.mock_mode:
            self.camera = sl.Camera()

            # Camera configuration - minimal settings for compatibility
            init_params = sl.InitParameters()
            init_params.camera_resolution = getattr(sl.RESOLUTION, resolution)
            init_params.camera_fps = fps
            init_params.depth_mode = getattr(sl.DEPTH_MODE, depth_mode)
            init_params.sdk_verbose = True  # Enable verbose logging

            # Open camera FIRST, then create Mat objects
            err = self.camera.open(init_params)
            if err != sl.ERROR_CODE.SUCCESS:
                print(f"Failed to open ZED camera with SDK: {err}, falling back to OpenCV")
                self.mock_mode = True
                self.camera = None
                try:
                    # Try video devices in order: 1, 2, 0
                    for device_idx in [1, 2, 0]:
                        self.opencv_cap = cv2.VideoCapture(device_idx)
                        if self.opencv_cap.isOpened():
                            self.opencv_mode = True
                            self.is_opened = True
                            print(f"Running in OpenCV mode - Using /dev/video{device_idx}")
                            break
                    if not self.opencv_mode:
                        print("Running in MOCK mode - No camera available")
                        self.is_opened = True
                except Exception as e:
                    print(f"OpenCV error: {e}. Running in MOCK mode")
                    self.is_opened = True
                return

            # Create Mat objects AFTER camera is opened (official SDK pattern)
            self.image = sl.Mat()
            self.depth = sl.Mat()
            self.point_cloud = sl.Mat()

            # Runtime parameters
            self.runtime_parameters = sl.RuntimeParameters()

            # Verify stream is actually working by grabbing a test frame
            test_grab = self.camera.grab(self.runtime_parameters)
            if test_grab != sl.ERROR_CODE.SUCCESS:
                print(f"ZED camera opened but stream failed ({test_grab}), falling back to OpenCV")
                self.camera.close()
                self.camera = None
                self.mock_mode = True
                try:
                    for device_idx in [1, 2, 0]:
                        self.opencv_cap = cv2.VideoCapture(device_idx)
                        if self.opencv_cap.isOpened():
                            self.opencv_mode = True
                            self.is_opened = True
                            print(f"Running in OpenCV mode - Using /dev/video{device_idx}")
                            break
                    if not self.opencv_mode:
                        print("Running in MOCK mode - No camera available")
                        self.is_opened = True
                except Exception as e:
                    print(f"OpenCV error: {e}. Running in MOCK mode")
                    self.is_opened = True
                return

            self.is_opened = True
            print("ZED stream verified - camera ready")

            # Object detection setup - temporarily disabled for testing
            # obj_param = sl.ObjectDetectionParameters()
            # obj_param.enable_tracking = True
            # obj_param.enable_body_fitting = False
            # obj_param.detection_model = sl.OBJECT_DETECTION_MODEL.MULTI_CLASS_BOX_MEDIUM

            # Enable object detection if available
            # if self.camera.enable_object_detection(obj_param) == sl.ERROR_CODE.SUCCESS:
            #     self.objects = sl.Objects()

            print(f"ZED Camera opened successfully - {resolution} @ {fps}fps")
        else:
            # Try OpenCV fallback
            try:
                # Try video devices in order: 1, 2, 0
                for device_idx in [1, 2, 0]:
                    self.opencv_cap = cv2.VideoCapture(device_idx)
                    if self.opencv_cap.isOpened():
                        self.opencv_mode = True
                        self.is_opened = True
                        print(f"Running in OpenCV mode - Using /dev/video{device_idx}")
                        print(f"Resolution: {int(self.opencv_cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(self.opencv_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
                        break
                if not self.opencv_mode:
                    self.mock_mode = True
                    self.is_opened = True
                    print("Running in MOCK mode - ZED SDK not available")
            except Exception as e:
                print(f"OpenCV camera error: {e}")
                self.mock_mode = True
                self.is_opened = True
                print("Running in MOCK mode - ZED SDK not available")

    def grab_frame(self) -> bool:
        """Grab a new frame from the camera"""
        if self.mock_mode:
            return True

        if self.opencv_mode:
            ret, _ = self.opencv_cap.read()
            return ret

        if self.camera.grab(self.runtime_parameters) == sl.ERROR_CODE.SUCCESS:
            return True
        return False

    def get_rgb_image(self) -> Optional[np.ndarray]:
        """Get RGB image as numpy array"""
        if self.mock_mode:
            # Return a mock image for development
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(img, "MOCK CAMERA - Install ZED SDK", (50, 360),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            cv2.putText(img, datetime.now().strftime("%H:%M:%S"), (50, 400),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
            return img

        if self.opencv_mode:
            ret, frame = self.opencv_cap.read()
            if ret:
                # ZED camera outputs side-by-side stereo image (1344x376)
                # Extract left image (first half)
                height, width = frame.shape[:2]
                left_image = frame[:, :width//2]
                # Resize to standard resolution
                left_image = cv2.resize(left_image, (1280, 720))
                return cv2.cvtColor(left_image, cv2.COLOR_BGR2RGB)
            # If OpenCV can't read frames, fall back to mock mode
            if not hasattr(self, '_opencv_failed_logged'):
                print("OpenCV failed to read frames, falling back to MOCK mode")
                self._opencv_failed_logged = True
                self.opencv_mode = False
                self.mock_mode = True
            # Return mock image
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(img, "MOCK CAMERA - ZED SDK Required", (50, 360),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            return img

        self.camera.retrieve_image(self.image, sl.VIEW.LEFT)
        return self.image.get_data()[:, :, :3]  # Remove alpha channel

    def get_depth_map(self) -> Optional[np.ndarray]:
        """Get depth map as numpy array"""
        if self.mock_mode or self.opencv_mode:
            # Return a mock depth map
            depth = np.random.rand(720, 1280) * 5.0  # Random depth 0-5m
            return depth

        try:
            self.camera.retrieve_measure(self.depth, sl.MEASURE.DEPTH)
            depth_data = self.depth.get_data()
            # Replace NaN and inf with 0
            depth_data = np.nan_to_num(depth_data, nan=0.0, posinf=0.0, neginf=0.0)
            return depth_data
        except Exception as e:
            print(f"Error getting depth map: {e}, returning mock data")
            return np.random.rand(720, 1280) * 5.0

    def get_depth_image(self) -> Optional[np.ndarray]:
        """Get depth map as colored image for visualization"""
        depth = self.get_depth_map()
        if depth is None:
            return None

        # Normalize depth to 0-255 range
        depth_normalized = np.clip(depth, 0, 10)  # Clip to 10 meters
        depth_normalized = (depth_normalized / 10.0 * 255).astype(np.uint8)

        # Apply colormap
        depth_colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
        return depth_colored

    def get_point_cloud(self, downsample_factor=4) -> Optional[np.ndarray]:
        """Get point cloud data (downsampled for efficiency)"""
        if self.mock_mode:
            # Return a mock point cloud
            points = np.random.rand(1000, 3) * 5.0  # 1000 random points
            return points

        self.camera.retrieve_measure(self.point_cloud, sl.MEASURE.XYZRGBA)
        pc_data = self.point_cloud.get_data()

        # Downsample
        pc_data = pc_data[::downsample_factor, ::downsample_factor]

        # Extract XYZ coordinates
        points = pc_data[:, :, :3].reshape(-1, 3)

        # Remove invalid points (NaN, inf)
        mask = np.all(np.isfinite(points), axis=1)
        points = points[mask]

        return points

    def get_detected_objects(self) -> list[Dict[str, Any]]:
        """Get detected and tracked objects"""
        if self.mock_mode or self.objects is None:
            # Return mock objects for development
            return [
                {
                    "id": 1,
                    "label": "Person",
                    "confidence": 0.95,
                    "position": {"x": 1.5, "y": 0.5, "z": 2.0},
                    "velocity": {"x": 0.1, "y": 0.0, "z": 0.05},
                    "bounding_box": {"x": 400, "y": 200, "w": 200, "h": 400}
                }
            ]

        self.camera.retrieve_objects(self.objects)

        detected = []
        for obj in self.objects.object_list:
            detected.append({
                "id": obj.id,
                "label": str(obj.label),
                "confidence": obj.confidence,
                "position": {
                    "x": float(obj.position[0]),
                    "y": float(obj.position[1]),
                    "z": float(obj.position[2])
                },
                "velocity": {
                    "x": float(obj.velocity[0]),
                    "y": float(obj.velocity[1]),
                    "z": float(obj.velocity[2])
                },
                "bounding_box": {
                    "x": int(obj.bounding_box_2d[0][0]),
                    "y": int(obj.bounding_box_2d[0][1]),
                    "w": int(obj.bounding_box_2d[2][0] - obj.bounding_box_2d[0][0]),
                    "h": int(obj.bounding_box_2d[2][1] - obj.bounding_box_2d[0][1])
                }
            })

        return detected

    def encode_image_to_jpeg(self, image: np.ndarray, quality=80) -> bytes:
        """Encode numpy image to JPEG bytes"""
        if image is None:
            return b''
        _, buffer = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buffer.tobytes()

    def close(self):
        """Close the camera"""
        if self.opencv_mode and self.opencv_cap is not None:
            self.opencv_cap.release()
        if not self.mock_mode and self.camera is not None:
            self.camera.close()
        self.is_opened = False
        print("ZED Camera closed")

    def __del__(self):
        self.close()
