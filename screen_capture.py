import ctypes
import struct
import numpy as np
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

# Ensure process is DPI aware so we get real native screen coordinates
try:
    user32.SetProcessDPIAware()
except Exception:
    pass

class ScreenCapture:
    def __init__(self):
        self._ensure_desktop_access()

    def _ensure_desktop_access(self):
        """Attaches to the active input desktop if running in an interactive session."""
        try:
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                user32.CloseDesktop(hdesk)
        except Exception:
            pass

    def get_screen_dimensions(self):
        self._ensure_desktop_access()
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        return w, h

    def capture_screen(self, region=None):
        """
        Captures the screen or a specific region (left, top, width, height).
        Returns a BGR numpy array compatible with OpenCV.
        """
        self._ensure_desktop_access()
        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        if region is None:
            left, top, width, height = 0, 0, screen_w, screen_h
        else:
            left, top, width, height = region
            # Clamp to screen bounds
            left = max(0, min(left, screen_w - 1))
            top = max(0, min(top, screen_h - 1))
            width = max(1, min(width, screen_w - left))
            height = max(1, min(height, screen_h - top))

        hdc_screen = user32.GetDC(0)
        if not hdc_screen:
            return None

        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
        oldbmp = gdi32.SelectObject(hdc_mem, hbmp)

        # SRCCOPY = 0x00CC0020
        gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, 0x00CC0020)

        # Get DIBits (BGRA format)
        bmpinfo = struct.pack('IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(width * height * 4)
        gdi32.GetDIBits(hdc_mem, hbmp, 0, height, buf, bmpinfo, 0)

        # Cleanup GDI handles
        gdi32.SelectObject(hdc_mem, oldbmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)

        # Convert to numpy array (H, W, 4) BGRA
        raw = np.frombuffer(buf, dtype=np.uint8).reshape((height, width, 4))
        # Return BGR for OpenCV
        bgr = raw[:, :, :3].copy()
        return bgr

if __name__ == "__main__":
    cap = ScreenCapture()
    w, h = cap.get_screen_dimensions()
    print(f"Screen dimensions: {w}x{h}")
    frame = cap.capture_screen()
    if frame is not None:
        print(f"Captured frame shape: {frame.shape}, mean color: {frame.mean(axis=(0,1))}")
    else:
        print("Failed to capture frame")
