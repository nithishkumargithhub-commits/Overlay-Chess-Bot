import os
import random
import chess
import chess.engine
from openings_and_styles import OpeningAndStyleManager, Playstyle, TimeControl

class ChessEngine:
    def __init__(self, stockfish_path=None, style=Playstyle.STANDARD, time_control=TimeControl.CLASSICAL):
        self.style_mgr = OpeningAndStyleManager(style=style, time_control=time_control)
        if stockfish_path is None:
            local_sf = os.path.join(os.path.dirname(__file__), "engine", "stockfish.exe")
            if os.path.exists(local_sf):
                stockfish_path = local_sf
            else:
                stockfish_path = "stockfish"

        self.stockfish_path = stockfish_path
        self._engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            if not os.path.exists(self.stockfish_path):
                print(f"[Engine] Stockfish binary not found at '{self.stockfish_path}'. Attempting auto-download...")
                try:
                    from download_stockfish import download_stockfish
                    downloaded = download_stockfish()
                    if os.path.exists(downloaded):
                        self.stockfish_path = downloaded
                except Exception as dl_err:
                    print(f"[Engine] Auto-download failed: {dl_err}")

            if os.path.exists(self.stockfish_path):
                self._engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
                self._engine.configure({"Threads": 2, "Hash": 64})
                print(f"[Engine] Loaded Stockfish from: {self.stockfish_path}")
            else:
                print(f"[Engine] Warning: Stockfish not found at '{self.stockfish_path}'. Using internal fallback.")
        except Exception as e:
            print(f"[Engine] Error starting Stockfish: {e}. Using internal fallback.")
            self._engine = None

    def close(self):
        if self._engine:
            try:
                self._engine.quit()
            except Exception:
                pass
            self._engine = None

    def evaluate_and_choose_move(self, board: chess.Board, humanize_pct=0.20):
        """
        Calculates a strong chess move according to core rules:
        - Most of the time plays near-optimal / strong moves.
        - Roughly 15-25% of the time, plays a slightly weaker / human-like move.
        - Hard constraint: Prioritize winning. Never blunder material or allow forced mate.
        """
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None, 0, "No legal moves"

        if len(legal_moves) == 1:
            return legal_moves[0], 0, "Only legal move"

        # 1. Opening Book Check
        if self.style_mgr:
            book_mv = self.style_mgr.get_book_move(board)
            if book_mv:
                return book_mv, 35, f"Opening Book ({self.style_mgr.style.upper()})"

        if self._engine:
            try:
                return self._stockfish_choose_move(board, legal_moves, humanize_pct)
            except Exception as e:
                print(f"[Engine] Stockfish query error: {e}. Falling back to internal engine.")

        return self._fallback_choose_move(board, legal_moves, humanize_pct)

    def _stockfish_choose_move(self, board: chess.Board, legal_moves, humanize_pct):
        multipv_count = min(4, len(legal_moves))
        # Analyze with MultiPV
        info = self._engine.analyse(
            board,
            chess.engine.Limit(time=0.15, depth=14),
            multipv=multipv_count
        )

        candidates = []
        for pv_info in info:
            pv = pv_info.get("pv", [])
            if not pv:
                continue
            move = pv[0]
            score_obj = pv_info.get("score")
            if score_obj is None:
                continue

            # PovScore from perspective of the player whose turn it is
            pov_score = score_obj.pov(board.turn)
            if pov_score.is_mate():
                mate_moves = pov_score.mate()
                # Positive mate = we mate opponent; negative = opponent mates us
                cp_val = 20000 - abs(mate_moves) * 100 if mate_moves > 0 else -20000 + abs(mate_moves) * 100
            else:
                cp_val = pov_score.score()

            candidates.append({"move": move, "score": cp_val})

        if not candidates:
            # Fallback quick play
            res = self._engine.play(board, chess.engine.Limit(time=0.1))
            return res.move, 0, "Stockfish single play"

        # Apply playstyle bonuses (Tal, Karpov, Blitz)
        if self.style_mgr:
            candidates = self.style_mgr.apply_style_bonus(board, candidates)

        # Sort candidates descending by score
        candidates.sort(key=lambda c: c["score"], reverse=True)
        best = candidates[0]
        best_score = best.get("raw_score", best["score"])

        # Decision logic:
        # If in critical state (we are losing, score < 0, or forced mate either way),
        # ALWAYS play the best move to prioritize winning!
        is_critical = best_score < 50 or best_score > 15000 or board.is_check()

        # Controlled human-like randomness (15-25% of the time)
        chosen = best
        reason = "Optimal engine move"
        if not is_critical and len(candidates) > 1 and random.random() < humanize_pct:
            # Evaluate weaker candidates:
            # Drop cannot exceed 65 centipawns, and absolute score must stay solid (>= 60 cp)
            human_alternatives = []
            for cand in candidates[1:]:
                drop = best_score - cand["score"]
                if drop <= 65 and cand["score"] >= 60:
                    human_alternatives.append((cand, drop))

            if human_alternatives:
                chosen, drop = random.choice(human_alternatives)
                reason = f"Humanized move (drop: -{drop}cp, eval: +{chosen['score']/100:.2f})"

        return chosen["move"], chosen["score"], reason

    def _fallback_choose_move(self, board: chess.Board, legal_moves, humanize_pct):
        """Pure-Python basic minimax fallback if Stockfish executable is unavailable."""
        piece_vals = {
            chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
            chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000
        }
        scored = []
        for move in legal_moves:
            board.push(move)
            # Evaluate material
            val = 0
            for sq, piece in board.piece_map().items():
                v = piece_vals.get(piece.piece_type, 0)
                val += v if piece.color == board.turn else -v
            if board.is_checkmate():
                val = 20000
            elif board.is_stalemate():
                val = 0
            board.pop()
            scored.append({"move": move, "score": -val})

        scored.sort(key=lambda s: s["score"], reverse=True)
        if random.random() < humanize_pct and len(scored) > 1 and (scored[0]["score"] - scored[1]["score"] < 50):
            return scored[1]["move"], scored[1]["score"], "Fallback humanized"
        return scored[0]["move"], scored[0]["score"], "Fallback best move"

    def check_game_status(self, board: chess.Board):
        """Returns (is_over: bool, status_message: str)"""
        if board.is_checkmate():
            winner = "Black" if board.turn == chess.WHITE else "White"
            return True, f"Checkmate! {winner} wins."
        if board.is_stalemate():
            return True, "Stalemate! Game is a draw."
        if board.is_insufficient_material():
            return True, "Draw due to insufficient material."
        if board.can_claim_threefold_repetition():
            return True, "Draw by threefold repetition."
        if board.can_claim_fifty_moves():
            return True, "Draw by 50-move rule."
        if board.is_check():
            return False, "Check!"
        return False, "In progress"

if __name__ == "__main__":
    engine = ChessEngine()
    b = chess.Board()
    mv, sc, reason = engine.evaluate_and_choose_move(b)
    print(f"Chosen move: {mv} (Score: {sc}cp, Reason: {reason})")
    status, msg = engine.check_game_status(b)
    print(f"Status: {status}, Message: {msg}")
    engine.close()
