from __future__ import annotations
from dataclasses import dataclass

@dataclass
class SafetyGate:
    """Central safety gate. Camera loss always disarms; it never auto-rearms."""
    camera_available: bool = False
    enabled: bool = False
    emergency_stopped: bool = False

    def arm(self) -> bool:
        if not self.camera_available or self.emergency_stopped:
            return False
        self.enabled = True
        return True

    def disarm(self, emergency: bool = False) -> None:
        self.enabled = False
        if emergency:
            self.emergency_stopped = True

    def reset_emergency(self) -> None:
        self.emergency_stopped = False

    def camera_lost(self) -> None:
        self.camera_available = False
        self.enabled = False

    def camera_restored(self) -> None:
        self.camera_available = True
        # Deliberately does not enable control.

    @property
    def can_execute(self) -> bool:
        return self.camera_available and self.enabled and not self.emergency_stopped
