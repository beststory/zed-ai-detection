"""
Detection modules for ZED 2i 3-Camera AI Monitoring System
"""

from .motion import MotionDetector
from .person import PersonDetector
from .structure import StructureDetector

__all__ = ["MotionDetector", "PersonDetector", "StructureDetector"]
