"""Interactive calibration and visual verification for chessboard coordinates."""
import cv2
import numpy as np
from screen_capture import ScreenCapture
from board_detector import BoardDetector

def calibrate():
    cap = ScreenCapture()
    detector = BoardDetector()

    print("[Calibrate] Capturing screen...")
    screen = cap.capture_screen()
    if screen is None:
        print("[Calibrate] Error: Could not capture screen.")
        return False

    print("[Calibrate] Scanning for chessboard...")
    bounds = detector.find_chessboard(screen)
    if bounds:
        x, y, w, h = bounds
        print(f"[Calibrate] Chessboard detected at: x={x}, y={y}, w={w}, h={h}")
        print(f"[Calibrate] Detected orientation: {detector.orientation}")

        # Draw visual verification
        annotated = screen.copy()
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 3)

        # Draw 8x8 grid
        sq_w = w / 8.0
        sq_h = h / 8.0
        for i in range(9):
            # Vertical lines
            vx = int(x + i * sq_w)
            cv2.line(annotated, (vx, y), (vx, y + h), (0, 255, 255), 1)
            # Horizontal lines
            hy = int(y + i * sq_h)
            cv2.line(annotated, (x, hy), (x + w, hy), (0, 255, 255), 1)

        # Annotate corners e.g. a1, h8
        for sq in ['a1', 'a8', 'h1', 'h8', 'e4', 'e5', 'd4', 'd5']:
            center = detector.get_square_center(sq, bounds)
            if center:
                cv2.circle(annotated, center, 6, (0, 0, 255), -1)
                cv2.putText(annotated, sq, (center[0] + 8, center[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)

        cv2.imwrite("board_detected.png", annotated)
        print("[Calibrate] Saved visual verification image to 'board_detected.png'")
        detector.save_config(bounds, detector.orientation)
        return True
    else:
        print("[Calibrate] No chessboard detected on screen.")
        print("Tip: Make sure the chessboard is fully visible on your screen (e.g. Chess.com or Lichess).")
        return False

if __name__ == "__main__":
    calibrate()
