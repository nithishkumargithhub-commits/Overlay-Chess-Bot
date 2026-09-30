"""Chessboard square difference recognition and legal move detection."""
import cv2
import numpy as np
import chess
from board_detector import BoardDetector

class BoardRecognizer:
    def __init__(self, detector: BoardDetector):
        self.detector = detector
        self.prev_board_crop = None
        self.prev_square_images = {} # square_name -> numpy crop
        self.empty_square_baseline = {} # (is_light) -> median color

    def extract_square_crops(self, board_crop):
        """
        Splits an 8x8 board crop into 64 square images mapped to chess square names ('a1'..'h8').
        """
        if board_crop is None:
            return {}

        h, w = board_crop.shape[:2]
        sq_w = w / 8.0
        sq_h = h / 8.0

        crops = {}
        for row in range(8):
            for col in range(8):
                # Calculate square name according to orientation
                if self.detector.orientation == "white":
                    file_char = chr(ord('a') + col)
                    rank_char = str(8 - row)
                else:
                    file_char = chr(ord('h') - col)
                    rank_char = str(1 + row)

                sq_name = file_char + rank_char
                y1 = int(row * sq_h)
                y2 = int((row + 1) * sq_h)
                x1 = int(col * sq_w)
                x2 = int((col + 1) * sq_w)

                crops[sq_name] = board_crop[y1:y2, x1:x2]

        return crops

    def compute_square_diffs(self, current_crops):
        """
        Compares current square crops with previous crops.
        Returns a dictionary of square_name -> float change score.
        """
        if not self.prev_square_images:
            return {sq: 0.0 for sq in current_crops}

        diffs = {}
        for sq, curr_img in current_crops.items():
            prev_img = self.prev_square_images.get(sq)
            if prev_img is None or curr_img.shape != prev_img.shape:
                diffs[sq] = 0.0
                continue

            # Compute difference in LAB or Grayscale color space
            diff = cv2.absdiff(curr_img, prev_img)
            # Sample inner 75% to ignore square boundary antialiasing
            sh, sw = diff.shape[:2]
            inner = diff[int(sh*0.12):int(sh*0.88), int(sw*0.12):int(sw*0.88)]
            score = np.mean(inner)
            diffs[sq] = float(score)

        return diffs

    def detect_move_from_diffs(self, board: chess.Board, current_crops, threshold=12.0):
        """
        Matches detected square differences against legal moves in the chess.Board.
        Returns the matching chess.Move or None.
        """
        diffs = self.compute_square_diffs(current_crops)
        if not diffs:
            return None

        # Filter squares with significant change
        active_squares = [sq for sq, score in diffs.items() if score > threshold]
        if not active_squares:
            return None

        # Sort active squares by diff score descending
        active_squares.sort(key=lambda s: diffs[s], reverse=True)

        best_move = None
        best_score = -1.0

        for move in board.legal_moves:
            from_sq = chess.square_name(move.from_square)
            to_sq = chess.square_name(move.to_square)

            s_from = diffs.get(from_sq, 0.0)
            s_to = diffs.get(to_sq, 0.0)

            # A valid move must significantly change both source and destination
            if s_from < threshold or s_to < threshold:
                continue

            move_score = s_from + s_to

            # Handle castling (4 squares change)
            if board.is_castling(move):
                if move.to_square in (chess.G1, chess.G8):
                    rook_from = "h1" if move.to_square == chess.G1 else "h8"
                    rook_to = "f1" if move.to_square == chess.G1 else "f8"
                else:
                    rook_from = "a1" if move.to_square == chess.C1 else "a8"
                    rook_to = "d1" if move.to_square == chess.C1 else "d8"
                move_score += diffs.get(rook_from, 0.0) + diffs.get(rook_to, 0.0)

            if move_score > best_score:
                best_score = move_score
                best_move = move

        return best_move

    def update_state(self, board_crop):
        """Updates the stored reference snapshot."""
        self.prev_board_crop = board_crop.copy() if board_crop is not None else None
        if board_crop is not None:
            self.prev_square_images = self.extract_square_crops(board_crop)

    def verify_move_completed(self, move: chess.Move, pre_move_crops, current_crops, threshold=8.0):
        """
        Verifies whether the piece actually moved from move.from_square to move.to_square.
        Returns (success: bool, diff_from: float, diff_to: float).
        """
        if not pre_move_crops or not current_crops:
            return False, 0.0, 0.0

        from_name = chess.square_name(move.from_square)
        to_name = chess.square_name(move.to_square)

        curr_from = current_crops.get(from_name)
        prev_from = pre_move_crops.get(from_name)
        curr_to = current_crops.get(to_name)
        prev_to = pre_move_crops.get(to_name)

        if curr_from is None or prev_from is None or curr_to is None or prev_to is None:
            return False, 0.0, 0.0

        sh, sw = curr_from.shape[:2]
        # Inner 75% region of square
        y1, y2 = int(sh * 0.12), int(sh * 0.88)
        x1, x2 = int(sw * 0.12), int(sw * 0.88)

        diff_from = float(np.mean(cv2.absdiff(curr_from[y1:y2, x1:x2], prev_from[y1:y2, x1:x2])))
        diff_to = float(np.mean(cv2.absdiff(curr_to[y1:y2, x1:x2], prev_to[y1:y2, x1:x2])))

        # Both squares must reflect the change
        success = (diff_from > threshold) and (diff_to > threshold)
        return success, diff_from, diff_to

    def is_initial_position(self, current_crops):
        """
        Heuristic to detect if the board is in starting position
        (ranks 3, 4, 5, 6 should be uniformly empty).
        """
        if len(current_crops) != 64:
            return False

        empty_ranks = ['3', '4', '5', '6']
        variances = []
        for file in 'abcdefgh':
            for rank in empty_ranks:
                sq = file + rank
                crop = current_crops.get(sq)
                if crop is not None:
                    # Empty square has very low standard deviation
                    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                    variances.append(np.std(gray))

        if not variances:
            return False

        avg_empty_var = np.mean(variances)
        # Empty chess squares have very low texture variance (typically < 8)
        return avg_empty_var < 15.0

if __name__ == "__main__":
    detector = BoardDetector()
    recognizer = BoardRecognizer(detector)
    print("BoardRecognizer initialized.")
