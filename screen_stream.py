import ctypes
import struct
import threading
import time
import cv2
import numpy as np

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

try:
    user32.SetProcessDPIAware()
except Exception:
    pass

class LiveScreenStream:
    """
    High-performance live background screen streamer.
    Uses persistent Win32 GDI buffers and a dedicated worker thread
    to stream screen frames in RAM at up to 60 FPS without disk I/O.
    """
    def __init__(self, target_fps=30, region=None):
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self.region = region # (x, y, w, h) or None for full screen

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self._latest_frame = None
        self._frame_count = 0
        self._last_frame_time = 0.0

        # Persistent GDI resources
        self._hdc_screen = None
        self._hdc_mem = None
        self._hbmp = None
        self._oldbmp = None
        self._buf = None
        self._bmpinfo = None
        self._current_w = 0
        self._current_h = 0

    def _ensure_desktop_access(self):
        try:
            hdesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
                user32.CloseDesktop(hdesk)
        except Exception:
            pass

    def _init_gdi_buffers(self, width, height):
        self._cleanup_gdi_buffers()
        self._current_w = width
        self._current_h = height

        self._hdc_screen = user32.GetDC(0)
        self._hdc_mem = gdi32.CreateCompatibleDC(self._hdc_screen)
        self._hbmp = gdi32.CreateCompatibleBitmap(self._hdc_screen, width, height)
        self._oldbmp = gdi32.SelectObject(self._hdc_mem, self._hbmp)

        # 32-bit BGRA top-down bitmap
        self._bmpinfo = struct.pack('IiiHHIIiiII', 40, width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        self._buf = ctypes.create_string_buffer(width * height * 4)

    def _cleanup_gdi_buffers(self):
        if self._hdc_mem and self._oldbmp:
            gdi32.SelectObject(self._hdc_mem, self._oldbmp)
            self._oldbmp = None
        if self._hbmp:
            gdi32.DeleteObject(self._hbmp)
            self._hbmp = None
        if self._hdc_mem:
            gdi32.DeleteDC(self._hdc_mem)
            self._hdc_mem = None
        if self._hdc_screen:
            user32.ReleaseDC(0, self._hdc_screen)
            self._hdc_screen = None

    def set_region(self, region):
        """Switches stream to a specific sub-region (e.g. locked chessboard)."""
        with self._lock:
            self.region = region
            # Force GDI buffer reallocation on next frame
            self._current_w = 0
            self._current_h = 0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        print(f"[LiveStream] Started background live screen capture thread ({self.target_fps} FPS target).")

    def stop(self):
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._cleanup_gdi_buffers()
        print("[LiveStream] Stopped live stream.")

    def get_latest_frame(self):
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def _stream_loop(self):
        self._ensure_desktop_access()

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)

        while self._running:
            t0 = time.time()

            with self._lock:
                reg = self.region

            if reg is None:
                rx, ry, rw, rh = 0, 0, screen_w, screen_h
            else:
                rx, ry, rw, rh = reg
                rx = max(0, min(rx, screen_w - 1))
                ry = max(0, min(ry, screen_h - 1))
                rw = max(1, min(rw, screen_w - rx))
                rh = max(1, min(rh, screen_h - ry))

            # Reallocate GDI buffers if size changed
            if rw != self._current_w or rh != self._current_h:
                self._init_gdi_buffers(rw, rh)

            # BitBlt from screen DC to memory DC
            gdi32.BitBlt(self._hdc_mem, 0, 0, rw, rh, self._hdc_screen, rx, ry, 0x00CC0020)
            gdi32.GetDIBits(self._hdc_mem, self._hbmp, 0, rh, self._buf, self._bmpinfo, 0)

            raw = np.frombuffer(self._buf, dtype=np.uint8).reshape((rh, rw, 4))
            bgr = raw[:, :, :3]

            with self._lock:
                self._latest_frame = bgr.copy()
                self._frame_count += 1
                self._last_frame_time = time.time()

            elapsed = time.time() - t0
            sleep_time = max(0.001, self.frame_interval - elapsed)
            time.sleep(sleep_time)

        self._cleanup_gdi_buffers()

if __name__ == "__main__":
    stream = LiveScreenStream(target_fps=30)
    stream.start()
    time.sleep(0.5)

    t_start = time.time()
    frames_read = 0
    for _ in range(30):
        frame = stream.get_latest_frame()
        if frame is not None:
            frames_read += 1
        time.sleep(0.033)

    stream.stop()
    print(f"Read {frames_read} live frames successfully! Frame shape: {frame.shape if frame is not None else None}")
