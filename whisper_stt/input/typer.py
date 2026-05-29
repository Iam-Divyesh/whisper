"""Keyboard typing simulation using pyautogui."""
import time
import pyautogui
from typing import Optional


class KeyboardTyper:
    """Simulate keyboard input."""
    
    def __init__(self, delay: float = 0.01, use_clipboard_fallback: bool = True):
        """Initialize keyboard typer.
        
        Args:
            delay: Delay between keystrokes in seconds
            use_clipboard_fallback: Use clipboard for fallback typing
        """
        self.delay = delay
        self.use_clipboard_fallback = use_clipboard_fallback
        pyautogui.FAILSAFE = True  # Move mouse to corner to abort
        
    def type_text(self, text: str) -> bool:
        """Type text into active window.
        
        Uses clipboard paste as the primary method since pyautogui.typewrite()
        only supports ASCII characters. Clipboard paste handles Unicode,
        special characters, and non-English text correctly.
        
        Args:
            text: Text to type
            
        Returns:
            True if successful, False otherwise
        """
        if not text:
            return True
        
        # Always prefer clipboard paste — it handles Unicode and is faster
        if self.use_clipboard_fallback:
            result = self._type_via_clipboard(text)
            if result:
                return True
        
        # Fallback to character-by-character typing (ASCII only)
        try:
            # pyautogui.typewrite only supports ASCII printable characters
            ascii_text = text.encode('ascii', errors='ignore').decode('ascii')
            if ascii_text:
                pyautogui.typewrite(ascii_text, interval=self.delay)
            return True
        except Exception as e:
            print(f"Typing error: {e}")
            return False
    
    def _type_via_clipboard(self, text: str) -> bool:
        """Type text using clipboard paste.
        
        Args:
            text: Text to paste
            
        Returns:
            True if successful
        """
        try:
            import pyperclip
            
            # Save current clipboard
            try:
                old_clipboard = pyperclip.paste()
            except Exception:
                old_clipboard = ""
            
            # Copy text to clipboard
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # Paste using hotkey
            pyautogui.hotkey('ctrl', 'v')
            
            time.sleep(0.1)
            
            # Restore clipboard
            try:
                pyperclip.copy(old_clipboard)
            except Exception:
                pass
            
            return True
        except Exception as e:
            print(f"Clipboard fallback error: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """Press a single key.
        
        Args:
            key: Key to press
            
        Returns:
            True if successful
        """
        try:
            pyautogui.press(key)
            return True
        except Exception as e:
            print(f"Key press error: {e}")
            return False
    
    def press_hotkey(self, *keys: str) -> bool:
        """Press a combination of keys.
        
        Args:
            *keys: Keys to press together (e.g., 'ctrl', 'c')
            
        Returns:
            True if successful
        """
        try:
            pyautogui.hotkey(*keys)
            return True
        except Exception as e:
            print(f"Hotkey error: {e}")
            return False
