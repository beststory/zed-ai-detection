from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8005

    # CORS settings
    cors_origins: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://192.168.1.3:5173",
        "http://192.168.1.3:3000"
    ]

    # ZED Camera settings
    camera_resolution: str = "VGA"  # HD2K, HD1080, HD720, VGA (using lower resolution to reduce resource usage)
    camera_fps: int = 15
    depth_mode: str = "NONE"  # NONE (disable depth, RGB only), PERFORMANCE, QUALITY, NEURAL

    # Streaming settings
    jpeg_quality: int = 80
    stream_fps: int = 15

    # Ollama settings (optional, used by AI modules)
    ollama_host: Optional[str] = "http://localhost:11434"
    ollama_model: Optional[str] = "gpt-oss:20b"

    # Detection settings (optional, used by AI modules)
    motion_threshold: Optional[int] = 500
    person_confidence: Optional[float] = 0.5
    structure_sensitivity: Optional[float] = 0.01

    # Camera integration settings (optional)
    zed_resolution: Optional[str] = "VGA"
    zed_fps: Optional[int] = 15
    hanwha_rtsp_url: Optional[str] = None
    hanwha_ip: Optional[str] = None
    hanwha_user: Optional[str] = None
    hanwha_password: Optional[str] = None

    # API settings (optional)
    api_host: Optional[str] = "192.168.1.3"
    api_port: Optional[int] = 8005

    # Data storage paths (optional)
    data_dir: Optional[str] = "/home/harvis/zed/data"
    baseline_dir: Optional[str] = "/home/harvis/zed/data/baselines"
    events_dir: Optional[str] = "/home/harvis/zed/data/events"
    measurements_dir: Optional[str] = "/home/harvis/zed/data/measurements"

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env

settings = Settings()
