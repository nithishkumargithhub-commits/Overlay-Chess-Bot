"""Reliable mouse controller with deliberate delays and verified interaction methods."""
import ctypes
import time
import math
import random

user32 = ctypes.windll.user32

# Mouse event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

class MouseController:
    def __init__(self):
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    def get_cursor_pos(self):
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _set_cursor_pos(self, x, y):
        user32.SetCursorPos(int(round(x)), int(round(y)))

    def _human_curve(self, start_x, start_y, end_x, end_y, duration=0.22, steps=25):
        """
        Generates a natural human-like Bézier curve between (start_x, start_y)
        and (end_x, end_y) with subtle curve deflection.
        """
        dx = end_x - start_x
        dy = end_y - start_y
        dist = math.hypot(dx, dy)
        if dist < 4:
            self._set_cursor_pos(end_x, end_y)
            return

        mid_x = (start_x + end_x) / 2.0
        mid_y = (start_y + end_y) / 2.0
        angle = math.atan2(dy, dx) + math.pi / 2
        deviation = (random.random() - 0.5) * min(dist * 0.18, 35)
        ctrl_x = mid_x + math.cos(angle) * deviation
        ctrl_y = mid_y + math.sin(angle) * deviation

        sleep_per_step = max(0.002, duration / steps)
        for i in range(1, steps + 1):
            t = i / steps
            t_eased = t * t * (3.0 - 2.0 * t) # smooth ease-in-out
            curr_x = (1 - t_eased)**2 * start_x + 2 * (1 - t_eased) * t_eased * ctrl_x + (t_eased**2) * end_x
            curr_y = (1 - t_eased)**2 * start_y + 2 * (1 - t_eased) * t_eased * ctrl_y + (t_eased**2) * end_y
            self._set_cursor_pos(curr_x, curr_y)
            time.sleep(sleep_per_step)

        self._set_cursor_pos(end_x, end_y)

    def move_to(self, x, y, duration=0.20):
        cur_x, cur_y = self.get_cursor_pos()
        self._human_curve(cur_x, cur_y, x, y, duration=duration)

    def _press_and_release(self, hold_min=0.045, hold_max=0.085):
        """Deliberate mouse click without rushing."""
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(random.uniform(hold_min, hold_max))
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

    def execute_click_click(self, from_pt, to_pt):
        """
        Executes move via strict Click -> Click procedure:
        1. Move mouse to center of piece.
        2. Wait 150–250 ms.
        3. Click (press & release mouse button).
        4. Wait 200–350 ms.
        5. Move mouse to exact center of destination square.
        6. Wait 150–250 ms.
        7. Click again.
        8. Wait 400–600 ms for board to update.
        """
        fx, fy = from_pt
        tx, ty = to_pt

        # 1. Move to center of piece
        self.move_to(fx, fy, duration=random.uniform(0.18, 0.25))

        # 2. Wait 150–250 ms
        time.sleep(random.uniform(0.150, 0.250))

        # 3. Click
        self._press_and_release()

        # 4. Wait 200–350 ms
        time.sleep(random.uniform(0.200, 0.350))

        # 5. Move to exact center of destination square
        self.move_to(tx, ty, duration=random.uniform(0.18, 0.25))

        # 6. Wait 150–250 ms
        time.sleep(random.uniform(0.150, 0.250))

        # 7. Click again
        self._press_and_release()

        # 8. Wait 400–600 ms for board to update
        time.sleep(random.uniform(0.400, 0.600))

    def execute_drag_and_drop(self, from_pt, to_pt):
        """
        Executes move via strict Drag-and-Drop procedure:
        1. Move mouse to center of piece.
        2. Wait 150–250 ms.
        3. Press mouse button (down).
        4. Wait 200–350 ms.
        5. Move mouse to exact center of destination square.
        6. Wait 150–250 ms.
        7. Release mouse button (up).
        8. Wait 400–600 ms for board to update.
        """
        fx, fy = from_pt
        tx, ty = to_pt

        # 1. Move to center of piece
        self.move_to(fx, fy, duration=random.uniform(0.18, 0.25))

        # 2. Wait 150–250 ms
        time.sleep(random.uniform(0.150, 0.250))

        # 3. Press down
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)

        # 4. Wait 200–350 ms
        time.sleep(random.uniform(0.200, 0.350))

        # 5. Move to destination square
        self.move_to(tx, ty, duration=random.uniform(0.22, 0.32))

        # 6. Wait 150–250 ms
        time.sleep(random.uniform(0.150, 0.250))

        # 7. Release up
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        # 8. Wait 400–600 ms for board to update
        time.sleep(random.uniform(0.400, 0.600))

    def click(self, x=None, y=None):
        if x is not None and y is not None:
            self.move_to(x, y)
        self._press_and_release()

if __name__ == "__main__":
    mc = MouseController()
    pos = mc.get_cursor_pos()
    print(f"MouseController loaded. Cursor position: {pos}")
