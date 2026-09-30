"""Transparent click-through Augmented Reality (AR) overlay for chessboards."""
import math
import tkinter as tk
import ctypes
import chess

user32 = ctypes.windll.user32
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
GWL_EXSTYLE = -20

class ChessAROverlay:
    """
    Transparent click-through canvas overlaid directly on top of the live chessboard.
    Renders best move arrows, threat heatmaps, and evaluation metrics.
    """
    TRANSPARENT_COLOR = "#000001"

    def __init__(self, root=None):
        self.is_external_root = root is not None
        self.root = tk.Toplevel(root) if self.is_external_root else tk.Tk()
        self.root.title("Chess AR Overlay")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.config(bg=self.TRANSPARENT_COLOR)

        try:
            self.root.attributes("-transparentcolor", self.TRANSPARENT_COLOR)
        except Exception:
            pass

        self.canvas = tk.Canvas(self.root, bg=self.TRANSPARENT_COLOR, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.bounds = None # (x, y, w, h)
        self.orientation = "white"
        self.visible = False

        self._enable_click_through()

    def _enable_click_through(self):
        """Ensures all mouse clicks pass completely through the overlay window."""
        try:
            self.root.update_idletasks()
            hwnd = self.root.winfo_id()
            # If winfo_id is a child, get top parent
            parent_hwnd = user32.GetParent(hwnd)
            target_hwnd = parent_hwnd if parent_hwnd else hwnd

            style = user32.GetWindowLongW(target_hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(target_hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT)
        except Exception as e:
            print(f"[AR Overlay] Warning setting click-through: {e}")

    def update_position(self, bounds, orientation="white"):
        """Aligns the AR window to the exact chessboard screen position."""
        self.bounds = bounds
        self.orientation = orientation
        x, y, w, h = bounds
        # Extend slightly for evaluation sidebar
        geo_str = f"{w + 60}x{h}+{x}+{y}"
        self.root.geometry(geo_str)
        self.canvas.config(width=w + 60, height=h)
        self.visible = True
        self.root.deiconify()
        self._enable_click_through()

    def hide(self):
        self.visible = False
        self.root.withdraw()

    def clear(self):
        self.canvas.delete("all")

    def _get_square_center(self, sq_name):
        if not self.bounds:
            return None
        _, _, w, h = self.bounds
        file_idx = ord(sq_name[0].lower()) - ord('a')
        rank_idx = int(sq_name[1]) - 1

        sq_w = w / 8.0
        sq_h = h / 8.0

        if self.orientation == "white":
            col = file_idx
            row = 7 - rank_idx
        else:
            col = 7 - file_idx
            row = rank_idx

        cx = (col + 0.5) * sq_w
        cy = (row + 0.5) * sq_h
        return cx, cy

    def draw_arrow(self, from_sq, to_sq, color="#00e676", width=7):
        """Draws an arrow indicating a candidate or best move."""
        p1 = self._get_square_center(from_sq)
        p2 = self._get_square_center(to_sq)
        if not p1 or not p2:
            return

        x1, y1 = p1
        x2, y2 = p2

        dx = x2 - x1
        dy = y2 - y1
        dist = math.hypot(dx, dy)
        if dist < 5:
            return

        # Shorten arrow head slightly so it points cleanly into square center
        shorten = min(15.0, dist * 0.2)
        end_x = x2 - (dx / dist) * shorten
        end_y = y2 - (dy / dist) * shorten

        # Draw circle on origin square
        self.canvas.create_oval(x1 - 8, y1 - 8, x1 + 8, y1 + 8, fill=color, outline="")

        # Draw main arrow line
        self.canvas.create_line(x1, y1, end_x, end_y, fill=color, width=width,
                                arrow=tk.LAST, arrowshape=(16, 20, 8), capstyle=tk.ROUND, joinstyle=tk.ROUND)

    def draw_threat_heatmap(self, board: chess.Board):
        """
        Calculates square control and highlights:
        - Attacked pieces in red
        - Pinned / king check in gold
        - Defended outposts in green
        """
        if not self.bounds:
            return

        _, _, w, h = self.bounds
        sq_w = w / 8.0
        sq_h = h / 8.0

        # Opponent color
        opp_color = not board.turn

        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece is None:
                continue

            sq_name = chess.square_name(sq)
            center = self._get_square_center(sq_name)
            if not center:
                continue

            cx, cy = center
            rx1 = cx - sq_w * 0.44
            ry1 = cy - sq_h * 0.44
            rx2 = cx + sq_w * 0.44
            ry2 = cy + sq_h * 0.44

            # Is our piece attacked by opponent?
            if piece.color == board.turn:
                attackers = board.attackers(opp_color, sq)
                defenders = board.attackers(board.turn, sq)

                if piece.piece_type == chess.KING and board.is_check():
                    # King in check: glowing gold ring
                    self.canvas.create_rectangle(rx1, ry1, rx2, ry2, outline="#ffd600", width=4)
                elif attackers and len(attackers) > len(defenders):
                    # Free / hanging piece: red warning
                    self.canvas.create_rectangle(rx1, ry1, rx2, ry2, outline="#ff1744", width=3)
                elif attackers:
                    # Contested piece: orange outline
                    self.canvas.create_rectangle(rx1, ry1, rx2, ry2, outline="#ff9100", width=2)

    def draw_hud_badge(self, eval_str, move_str, delay_str=None):
        """Draws a sleek floating telemetry badge beside the board."""
        if not self.bounds:
            return
        _, _, w, _ = self.bounds
        bx = w + 8
        by = 20

        # Background card
        self.canvas.create_rectangle(bx, by, bx + 50, by + 120, fill="#1e1e1e", outline="#333333", width=2)

        # Move badge
        self.canvas.create_text(bx + 25, by + 20, text=move_str, fill="#00e676", font=("Segoe UI", 10, "bold"))

        # Eval badge
        eval_color = "#ffffff"
        if eval_str.startswith("+"):
            eval_color = "#00e676"
        elif eval_str.startswith("-"):
            eval_color = "#ff5252"
        self.canvas.create_text(bx + 25, by + 50, text=eval_str, fill=eval_color, font=("Segoe UI", 11, "bold"))

        # Delay
        if delay_str:
            self.canvas.create_text(bx + 25, by + 85, text=f"⏱ {delay_str}", fill="#e040fb", font=("Segoe UI", 8))

    def update_view(self, board: chess.Board, best_move: chess.Move = None, eval_str="", delay_str=None):
        """Refreshes all AR annotations in one atomic update."""
        self.clear()
        if best_move:
            from_sq = chess.square_name(best_move.from_square)
            to_sq = chess.square_name(best_move.to_square)
            self.draw_arrow(from_sq, to_sq, color="#00e676", width=8)

        self.draw_threat_heatmap(board)

        if best_move and eval_str:
            move_san = board.san(best_move)
            self.draw_hud_badge(eval_str, move_san, delay_str)

if __name__ == "__main__":
    overlay = ChessAROverlay()
    overlay.update_position((200, 200, 600, 600), "white")
    b = chess.Board()
    overlay.update_view(b, chess.Move.from_uci("e2e4"), eval_str="+0.3", delay_str="2.5s")
    overlay.root.after(1500, overlay.root.destroy)
    overlay.root.mainloop()
