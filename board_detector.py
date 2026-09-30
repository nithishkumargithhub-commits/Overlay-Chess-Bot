"""Chessboard localization and coordinate mapping using computer vision."""
import os
import json
import cv2
import numpy as np

class BoardDetector:
    def __init__(self, config_file="board_config.json"):
        self.config_file = config_file
        self.cached_bounds = None # (x, y, w, h)
        self.orientation = "white" # "white" if white is at bottom, "black" if black is at bottom
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    self.cached_bounds = tuple(data["bounds"])
                    self.orientation = data.get("orientation", "white")
                    print(f"[BoardDetector] Loaded config: bounds={self.cached_bounds}, orientation={self.orientation}")
            except Exception as e:
                print(f"[BoardDetector] Error loading config: {e}")

    def save_config(self, bounds, orientation="white"):
        self.cached_bounds = bounds
        self.orientation = orientation
        try:
            with open(self.config_file, "w") as f:
                json.dump({"bounds": list(bounds), "orientation": orientation}, f, indent=2)
            print(f"[BoardDetector] Saved config to {self.config_file}")
        except Exception as e:
            print(f"[BoardDetector] Error saving config: {e}")

    def find_chessboard(self, screen_bgr):
        """
        Scans a BGR screen image for an 8x8 chessboard.
        Returns (x, y, w, h) of the board or None if not found.
        """
        if screen_bgr is None:
            return None

        # If cached bounds are set, first verify if the cached region is still a valid chessboard
        if self.cached_bounds:
            x, y, w, h = self.cached_bounds
            if x + w <= screen_bgr.shape[1] and y + h <= screen_bgr.shape[0]:
                cropped = screen_bgr[y:y+h, x:x+w]
                if self._verify_chessboard_lattice(cropped):
                    return self.cached_bounds

        # Perform automatic detection across the entire screen
        gray = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
        h_screen, w_screen = gray.shape

        # Downscale for faster candidate contour detection if screen is large
        scale = 1.0
        if w_screen > 1600:
            scale = 0.5
            small_gray = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
        else:
            small_gray = gray

        # Edge detection
        blurred = cv2.GaussianBlur(small_gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 100)

        # Dilate edges slightly to close gaps in board borders
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(edges, kernel, iterations=1)

        contours, _ = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        best_candidate = None
        best_score = -1.0

        min_dim = int(240 * scale)
        max_dim = int(1400 * scale)

        for cnt in contours:
            x_s, y_s, w_s, h_s = cv2.boundingRect(cnt)
            if w_s < min_dim or h_s < min_dim or w_s > max_dim or h_s > max_dim:
                continue

            # Chessboard must be nearly square
            aspect = float(w_s) / float(h_s)
            if not (0.92 <= aspect <= 1.08):
                continue

            # Scale back to full resolution
            x = int(x_s / scale)
            y = int(y_s / scale)
            w = int(w_s / scale)
            h = int(h_s / scale)

            # Check boundary
            if x + w > w_screen or y + h > h_screen:
                continue

            # Verify 8x8 checkerboard pattern
            crop = screen_bgr[y:y+h, x:x+w]
            score = self._compute_checkerboard_score(crop)
            if score > 1.2 and score > best_score:
                best_score = score
                best_candidate = (x, y, w, h)

        if best_candidate:
            self.cached_bounds = best_candidate
            # Detect orientation based on bottom and top rank pieces
            self.detect_orientation(screen_bgr, best_candidate)
            return best_candidate

        return None

    def _verify_chessboard_lattice(self, board_crop):
        return self._compute_checkerboard_score(board_crop) > 1.0

    def _compute_checkerboard_score(self, board_crop):
        """
        Evaluates the alternating pattern score of 64 grid cells.
        Returns a positive float; higher means higher confidence of a chessboard.
        """
        if board_crop is None or board_crop.shape[0] < 64 or board_crop.shape[1] < 64:
            return 0.0

        gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        sq_w = w / 8.0
        sq_h = h / 8.0

        group_a = []
        group_b = []

        # Sample inner 50% of each of the 64 squares to avoid border lines
        for r in range(8):
            for c in range(8):
                y1 = int((r + 0.25) * sq_h)
                y2 = int((r + 0.75) * sq_h)
                x1 = int((c + 0.25) * sq_w)
                x2 = int((c + 0.75) * sq_w)
                cell = gray[y1:y2, x1:x2]
                if cell.size == 0:
                    continue
                cell_mean = np.mean(cell)

                if (r + c) % 2 == 0:
                    group_a.append(cell_mean)
                else:
                    group_b.append(cell_mean)

        if not group_a or not group_b:
            return 0.0

        mean_a = np.mean(group_a)
        mean_b = np.mean(group_b)
        std_a = np.std(group_a)
        std_b = np.std(group_b)

        diff = abs(mean_a - mean_b)
        # In a real chessboard, group A and group B should differ significantly in mean
        # while internal variance within each group should be moderate
        score = diff / (0.5 * (std_a + std_b) + 5.0)
        return float(score)

    def detect_orientation(self, screen_bgr, bounds):
        """
        Detects whether White is at the bottom ('white') or Black is at bottom ('black').
        """
        x, y, w, h = bounds
        board = screen_bgr[y:y+h, x:x+w]
        gray = cv2.cvtColor(board, cv2.COLOR_BGR2GRAY)
        sq_h = h / 8.0

        # Sample rank at top (row 0) and rank at bottom (row 7)
        top_rank = gray[int(0.1 * sq_h):int(0.9 * sq_h), :]
        bot_rank = gray[int(7.1 * sq_h):int(7.9 * sq_h), :]

        top_mean = np.mean(top_rank)
        bot_mean = np.mean(bot_rank)

        # Generally, White pieces have higher luminance than Black pieces
        if bot_mean > top_mean:
            self.orientation = "white"
        else:
            self.orientation = "black"

        return self.orientation

    def get_square_center(self, square_name: str, bounds=None, orientation=None):
        """
        Maps a chess square string ('a1' .. 'h8') to screen pixel coordinates (x, y).
        """
        if bounds is None:
            bounds = self.cached_bounds
        if orientation is None:
            orientation = self.orientation
        if bounds is None:
            return None

        bx, by, bw, bh = bounds
        file_char = square_name[0].lower()
        rank_char = square_name[1]

        file_idx = ord(file_char) - ord('a') # 0..7 for a..h
        rank_idx = int(rank_char) - 1        # 0..7 for 1..8

        sq_w = bw / 8.0
        sq_h = bh / 8.0

        if orientation == "white":
            # White at bottom: col 0 is a, row 0 is 8 (top)
            col = file_idx
            row = 7 - rank_idx
        else:
            # Black at bottom: col 0 is h, row 0 is 1 (top)
            col = 7 - file_idx
            row = rank_idx

        cx = int(bx + (col + 0.5) * sq_w)
        cy = int(by + (row + 0.5) * sq_h)
        return cx, cy

    def get_square_rect(self, square_name: str, bounds=None, orientation=None):
        """Returns (x, y, w, h) for a specific square."""
        if bounds is None:
            bounds = self.cached_bounds
        if orientation is None:
            orientation = self.orientation
        if bounds is None:
            return None

        bx, by, bw, bh = bounds
        file_char = square_name[0].lower()
        rank_char = square_name[1]

        file_idx = ord(file_char) - ord('a')
        rank_idx = int(rank_char) - 1

        sq_w = bw / 8.0
        sq_h = bh / 8.0

        if orientation == "white":
            col = file_idx
            row = 7 - rank_idx
        else:
            col = 7 - file_idx
            row = rank_idx

        x = int(bx + col * sq_w)
        y = int(by + row * sq_h)
        return x, y, int(sq_w), int(sq_h)

if __name__ == "__main__":
    detector = BoardDetector()
    print("BoardDetector initialized. Orientation:", detector.orientation)
