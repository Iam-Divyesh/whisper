"""System tray icon and menu using pystray."""
import os
import sys
from io import BytesIO
from enum import Enum
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray


class TrayState(Enum):
    """Tray icon states."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    TYPING = "typing"
    ERROR = "error"


class TrayIcon:
    """System tray icon manager."""
    
    def __init__(
        self,
        on_toggle: Optional[Callable] = None,
        on_settings: Optional[Callable] = None,
        on_exit: Optional[Callable] = None
    ):
        """Initialize tray icon.
        
        Args:
            on_toggle: Callback for toggle recording
            on_settings: Callback for settings
            on_exit: Callback for exit
        """
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_exit = on_exit
        self._state = TrayState.IDLE
        self._icon: Optional[pystray.Icon] = None
        
    def _create_image(self, state: TrayState) -> Image.Image:
        """Create icon image for state."""
        width = 64
        height = 64
        
        # Color mapping
        colors = {
            TrayState.IDLE: (128, 128, 128),      # Gray
            TrayState.RECORDING: (255, 0, 0),      # Red
            TrayState.PROCESSING: (255, 255, 0),   # Yellow
            TrayState.TYPING: (0, 255, 0),         # Green
            TrayState.ERROR: (255, 128, 0),        # Orange
        }
        
        color = colors.get(state, (128, 128, 128))
        
        # Create image
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        dc = ImageDraw.Draw(image)
        
        # Draw microphone shape
        if state == TrayState.RECORDING:
            # Recording circle
            dc.ellipse([8, 8, 56, 56], fill=color)
            # Inner white circle
            dc.ellipse([16, 16, 48, 48], fill=(255, 255, 255, 255))
            # Red dot
            dc.ellipse([24, 24, 40, 40], fill=(255, 0, 0, 255))
        else:
            # Microphone body
            dc.ellipse([20, 12, 44, 36], outline=color, width=3)
            # Microphone base
            dc.line([(32, 36), (32, 48)], fill=color, width=3)
            dc.arc([16, 30, 48, 54], start=0, end=180, fill=color, width=3)
            dc.line([(16, 42), (48, 42)], fill=color, width=3)
        
        return image
    
    def _create_menu(self) -> pystray.Menu:
        """Create system tray menu."""
        items = []
        
        # Toggle recording
        label = "🎤 Stop Recording" if self._state == TrayState.RECORDING else "🎤 Start Recording"
        items.append(pystray.MenuItem(label, self._on_toggle, enabled=self._on_toggle is not None))
        
        items.append(pystray.Menu.SEPARATOR)
        
        # Settings
        items.append(pystray.MenuItem("⚙️ Settings", self._on_settings, enabled=self._on_settings is not None))
        
        # Exit
        items.append(pystray.MenuItem("❌ Exit", self._on_exit, enabled=self._on_exit is not None))
        
        return pystray.Menu(*items)
    
    def set_state(self, state: TrayState) -> None:
        """Update tray icon state.
        
        Args:
            state: New state
        """
        self._state = state
        if self._icon:
            self._icon.icon = self._create_image(state)
            self._icon.menu = self._create_menu()
    
    def notify(self, title: str, message: str) -> None:
        """Show notification.
        
        Args:
            title: Notification title
            message: Notification message
        """
        if self._icon:
            self._icon.notify(message, title)
    
    def run(self) -> None:
        """Start tray icon."""
        self._icon = pystray.Icon(
            "whisper-stt",
            icon=self._create_image(self._state),
            title="Whisper STT",
            menu=self._create_menu()
        )
        self._icon.run()
    
    def run_detached(self) -> None:
        """Start tray icon in separate thread."""
        import threading
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
    
    def stop(self) -> None:
        """Stop tray icon."""
        if self._icon:
            self._icon.stop()
            self._icon = None
