"""
ZMQ Frame Receiver for FastAPI
Receives frames from separate ZED capture process via ZMQ.
"""
import zmq
import numpy as np
import cv2
from typing import Optional, Tuple
import threading
import time


class ZMQFrameReceiver:
    def __init__(self, zmq_host="localhost", zmq_port=5555):
        self.zmq_host = zmq_host
        self.zmq_port = zmq_port

        self.rgb_frame = None
        self.depth_frame = None
        self.point_cloud_data = None
        self.bodies_data = None
        self.sensor_data = None
        self.frame_lock = threading.Lock()
        self.running = False
        self.receiver_thread = None

        # Stats
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0

        # ZMQ setup
        self.context = None
        self.socket = None

    def connect(self):
        """Connect to ZMQ publisher"""
        try:
            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.SUB)
            self.socket.connect(f"tcp://{self.zmq_host}:{self.zmq_port}")
            self.socket.subscribe(b"")  # Subscribe to all messages
            self.socket.setsockopt(zmq.RCVTIMEO, 1000)  # 1 second timeout
            print(f"Connected to ZMQ publisher at {self.zmq_host}:{self.zmq_port}")
            return True
        except Exception as e:
            print(f"Failed to connect to ZMQ: {e}")
            return False

    def start_receiving(self):
        """Start background thread for receiving frames"""
        if self.running:
            return

        if not self.connect():
            print("Failed to connect to capture process")
            return

        self.running = True
        self.receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self.receiver_thread.start()
        print("Frame receiver thread started")

    def _receive_loop(self):
        """Background loop to receive frames"""
        import json

        while self.running:
            try:
                # Receive multipart message [type, data] or [type, metadata, data]
                message = self.socket.recv_multipart(zmq.NOBLOCK)

                if len(message) >= 2:
                    frame_type = message[0]

                    with self.frame_lock:
                        if frame_type == b'rgb' or frame_type == b'depth':
                            # Image data - decode JPEG
                            frame_data = message[1]
                            frame_array = np.frombuffer(frame_data, dtype=np.uint8)
                            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

                            if frame is not None:
                                if frame_type == b'rgb':
                                    self.rgb_frame = frame
                                elif frame_type == b'depth':
                                    self.depth_frame = frame

                        elif frame_type == b'pointcloud' and len(message) == 3:
                            # Point cloud data - binary numpy array
                            pc_shape = message[1].decode().split(',')
                            pc_buffer = message[2]

                            rows, cols = int(pc_shape[0]), int(pc_shape[1])
                            pc_array = np.frombuffer(pc_buffer, dtype=np.float32)
                            pc_array = pc_array.reshape((rows, cols, 4))  # XYZRGBA
                            self.point_cloud_data = pc_array

                        elif frame_type == b'bodies':
                            # Body tracking data - JSON
                            body_json = message[1].decode()
                            self.bodies_data = json.loads(body_json)

                        elif frame_type == b'sensors':
                            # Sensor data - JSON
                            sensor_json = message[1].decode()
                            self.sensor_data = json.loads(sensor_json)

                    # FPS calculation
                    if frame_type in [b'rgb', b'depth']:
                        self.frame_count += 1
                        current_time = time.time()
                        if current_time - self.last_fps_time >= 1.0:
                            self.fps = self.frame_count / (current_time - self.last_fps_time)
                            if self.frame_count % 30 == 0:
                                print(f"Receiver FPS: {self.fps:.1f}")
                            self.frame_count = 0
                            self.last_fps_time = current_time

            except zmq.Again:
                # No message available, continue
                time.sleep(0.01)
            except Exception as e:
                if self.running:
                    print(f"Error receiving frame: {e}")
                time.sleep(0.1)

    def get_rgb_frame(self) -> Optional[np.ndarray]:
        """Get latest RGB frame"""
        with self.frame_lock:
            if self.rgb_frame is not None:
                return self.rgb_frame.copy()
        return None

    def get_depth_frame(self) -> Optional[np.ndarray]:
        """Get latest depth frame"""
        with self.frame_lock:
            if self.depth_frame is not None:
                return self.depth_frame.copy()
        return None

    def get_point_cloud(self):
        """Get latest point cloud data"""
        with self.frame_lock:
            if self.point_cloud_data is not None:
                return self.point_cloud_data.copy()
        return None

    def get_bodies(self):
        """Get latest body tracking data"""
        with self.frame_lock:
            if self.bodies_data is not None:
                return self.bodies_data.copy() if isinstance(self.bodies_data, list) else self.bodies_data
        return None

    def get_sensors(self):
        """Get latest sensor data"""
        with self.frame_lock:
            if self.sensor_data is not None:
                return self.sensor_data.copy() if isinstance(self.sensor_data, dict) else self.sensor_data
        return None

    def stop(self):
        """Stop receiving frames"""
        self.running = False
        if self.receiver_thread:
            self.receiver_thread.join(timeout=2.0)
        if self.socket:
            self.socket.close()
        if self.context:
            self.context.term()
        print("Frame receiver stopped")

    def is_receiving(self) -> bool:
        """Check if actively receiving frames"""
        return self.running and self.rgb_frame is not None
