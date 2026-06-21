"""Global hotkey handling using pynput."""
import sys
import threading
from typing import Callable, Optional
from pynput import keyboard

# Low-level keyboard hook flag set on synthetic/injected events (SendInput,
# keybd_event) — used to ignore our own pyautogui Ctrl+V paste simulation,
# see HotkeyManager._win32_event_filter for why this matters.
_LLKHF_INJECTED = 0x10


class HotkeyManager:
    """Manage global hotkeys."""
    
    def __init__(self):
        """Initialize hotkey manager."""
        self._listener: Optional[keyboard.Listener] = None
        self._hotkeys = {}
        self._pressed_keys = set()
        self._lock = threading.Lock()
        self._running = False
        
    def register_hotkey(
        self,
        combination: str,
        on_press: Callable,
        on_release: Optional[Callable] = None
    ) -> None:
        """Register a hotkey combination.
        
        Args:
            combination: Hotkey string (e.g., 'ctrl+shift+space')
            on_press: Callback when hotkey is pressed
            on_release: Callback when hotkey is released
        """
        keys = self._parse_combination(combination)
        self._hotkeys[combination] = {
            'keys': keys,
            'on_press': on_press,
            'on_release': on_release,
            'is_pressed': False
        }
        print(f"Registered hotkey: {combination}")
    
    def _parse_combination(self, combination: str) -> set:
        """Parse hotkey string into set of keys."""
        parts = combination.lower().split('+')
        keys = set()
        
        key_map = {
            # generic 'ctrl'/'alt'/'shift' map to the left variant; presses of
            # either physical side are normalized to this same value by
            # _normalize() before matching, so both sides trigger the hotkey
            'ctrl': keyboard.Key.ctrl_l,
            'ctrl_l': keyboard.Key.ctrl_l,
            'ctrl_r': keyboard.Key.ctrl_l,
            'alt': keyboard.Key.alt_l,
            'alt_l': keyboard.Key.alt_l,
            'alt_r': keyboard.Key.alt_l,
            'shift': keyboard.Key.shift_l,
            'shift_l': keyboard.Key.shift_l,
            'shift_r': keyboard.Key.shift_l,
            'space': keyboard.Key.space,
            'tab': keyboard.Key.tab,
            'enter': keyboard.Key.enter,
            'esc': keyboard.Key.esc,
            'up': keyboard.Key.up,
            'down': keyboard.Key.down,
            'left': keyboard.Key.left,
            'right': keyboard.Key.right,
        }
        
        for part in parts:
            part = part.strip()
            if part in key_map:
                keys.add(key_map[part])
            elif part.startswith('f') and part[1:].isdigit():
                # Function keys F1-F12
                keys.add(getattr(keyboard.Key, part))
            elif len(part) == 1:
                # Single character
                keys.add(keyboard.KeyCode.from_char(part))
            else:
                # Try to get key by name
                try:
                    keys.add(getattr(keyboard.Key, part))
                except AttributeError:
                    print(f"Warning: Unknown key '{part}'")
        
        return keys

    # Right-side modifiers are normalized to their left-side equivalent so
    # 'ctrl+shift+space' matches regardless of which physical Ctrl/Shift/Alt
    # key the user presses.
    _SIDE_NORMALIZE = {
        keyboard.Key.ctrl_r:  keyboard.Key.ctrl_l,
        keyboard.Key.shift_r: keyboard.Key.shift_l,
        keyboard.Key.alt_r:   keyboard.Key.alt_l,
    }

    @classmethod
    def _normalize(cls, key):
        return cls._SIDE_NORMALIZE.get(key, key)

    def _on_press(self, key):
        """Handle key press."""
        key = self._normalize(key)
        with self._lock:
            self._pressed_keys.add(key)

            for combo_name, combo_info in self._hotkeys.items():
                if combo_info['keys'].issubset(self._pressed_keys):
                    if not combo_info['is_pressed']:
                        combo_info['is_pressed'] = True
                        if combo_info['on_press']:
                            try:
                                combo_info['on_press']()
                            except Exception as e:
                                print(f"Hotkey press error: {e}")

    def _on_release(self, key):
        """Handle key release."""
        key = self._normalize(key)
        with self._lock:
            self._pressed_keys.discard(key)

            for combo_name, combo_info in self._hotkeys.items():
                if combo_info['is_pressed']:
                    # Check if any required key was released
                    if key in combo_info['keys']:
                        combo_info['is_pressed'] = False
                        if combo_info['on_release']:
                            try:
                                combo_info['on_release']()
                            except Exception as e:
                                print(f"Hotkey release error: {e}")
    
    @staticmethod
    def _win32_event_filter(msg, data):
        """Ignore synthetic/injected key events on Windows.

        KeyboardTyper pastes text by simulating Ctrl+V (pyautogui). That
        synthetic Ctrl-down/Ctrl-up is delivered through this SAME low-level
        keyboard hook — without this filter, our own paste keystroke gets
        mistaken for the user releasing Ctrl, firing _stop_recording() mid
        recording even though the real hotkey is still physically held.
        Returning False here skips on_press/on_release for this event while
        still letting it reach the OS normally (the paste still works).
        """
        if getattr(data, 'flags', 0) & _LLKHF_INJECTED:
            return False
        return True

    def start(self) -> None:
        """Start listening for hotkeys."""
        if self._running:
            return

        kwargs = dict(on_press=self._on_press, on_release=self._on_release)
        if sys.platform == 'win32':
            kwargs['win32_event_filter'] = self._win32_event_filter

        self._listener = keyboard.Listener(**kwargs)
        self._listener.start()
        self._running = True
        print("Hotkey listener started")
    
    def stop(self) -> None:
        """Stop listening for hotkeys."""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
        print("Hotkey listener stopped")
    
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running and self._listener is not None and self._listener.is_alive()
