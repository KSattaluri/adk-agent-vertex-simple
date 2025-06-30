"""
Timing utilities for performance analysis
"""
import time
from typing import Dict
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

class TimingTracker:
    """Track timing for different operations"""

    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}

    def start(self, operation: str) -> None:
        """Start timing an operation"""
        self.start_times[operation] = time.time()

    def end(self, operation: str) -> float:
        """End timing an operation and return duration"""
        if operation not in self.start_times:
            logger.warning(f"No start time for operation: {operation}")
            return 0.0

        duration = time.time() - self.start_times[operation]
        self.timings[operation] = duration
        del self.start_times[operation]
        return duration

    def get_timings(self) -> Dict[str, float]:
        """Get all recorded timings"""
        return self.timings.copy()


    def reset(self):
        """Reset all timings"""
        self.timings.clear()
        self.start_times.clear()

@contextmanager
def time_operation(tracker: TimingTracker, operation: str, log: bool = True):
    """Context manager for timing operations"""
    tracker.start(operation)

    try:
        yield
    finally:
        duration = tracker.end(operation)
        if log:
            logger.info(f"[TIMING] {operation}: {duration:.3f}s")

