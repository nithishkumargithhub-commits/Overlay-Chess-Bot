"""Opening book theory and GM playstyles (Tal, Karpov, Blitz, Stockfish)."""
import random
import chess

# Built-in Master Opening Repertoire
OPENING_BOOK = {
    # Initial Position (White choices)
    "": ["e2e4", "d2d4", "c2c4", "g1f3"],

    # Responses to 1. e4
    "e2e4": ["c7c5", "e7e5", "e7e6", "c7c6"], # Sicilian, Open, French, Caro-Kann

    # 1. e4 e5
    "e2e4 e7e5": ["g1f3", "f1c4", "d2d4"], # Open Game
    "e2e4 e7e5 g1f3": ["b8c6", "g8f6"],
    "e2e4 e7e5 g1f3 b8c6": ["f1b5", "f1c4", "d2d4"], # Ruy Lopez, Italian, Scotch
    "e2e4 e7e5 g1f3 b8c6 f1b5": ["a7a6", "g8f6"], # Morphy defense / Berlin
    "e2e4 e7e5 g1f3 b8c6 f1c4": ["f8c5", "g8f6"], # Giuoco Piano / Two Knights

    # 1. e4 c5 (Sicilian)
    "e2e4 c7c5": ["g1f3", "c2c3", "b1c3"],
    "e2e4 c7c5 g1f3": ["d7d6", "e7e6", "b8c6"],
    "e2e4 c7c5 g1f3 d7d6": ["d2d4"],
    "e2e4 c7c5 g1f3 d7d6 d2d4": ["c5d4"],
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4": ["f3d4"],
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4": ["g8f6"],
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6": ["b1c3"],
    "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3": ["a7a6", "g7g6"], # Najdorf / Dragon

    # 1. d4 (Queen's Pawn)
    "d2d4": ["d7d5", "g8f6", "e7e6"],
    "d2d4 d7d5": ["c2c4", "g1f3", "c1f4"], # QG, London System
    "d2d4 d7d5 c2c4": ["e7e6", "c7c6", "d5c4"], # QGD, Slav, QGA
    "d2d4 g8f6": ["c2c4", "g1f3", "c1f4"],
    "d2d4 g8f6 c2c4": ["e7e6", "g7g6", "c7c5"], # Nimzo/Indian/Benoni

    # 1. c4 (English)
    "c2c4": ["e7e5", "c7c5", "g8f6"],
}

class Playstyle:
    TAL = "tal"         # Aggressive / Tactical / King Attacks
    KARPOV = "karpov"   # Positional / Solid / Endgame Mastery
    BLITZ = "blitz"     # Fast / Low-Risk / High Speed
    STANDARD = "standard" # Balanced / Humanized Stockfish

class TimeControl:
    CLASSICAL = "classical" # 1.5s - 9.5s
    RAPID = "rapid"         # 1.0s - 4.5s
    BLITZ = "blitz"         # 0.5s - 2.2s
    BULLET = "bullet"       # 0.2s - 0.8s

class OpeningAndStyleManager:
    def __init__(self, style=Playstyle.STANDARD, time_control=TimeControl.CLASSICAL):
        self.style = style
        self.time_control = time_control

    def get_book_move(self, board: chess.Board):
        """Looks up the current move sequence in the Master Opening Repertoire."""
        uci_moves = " ".join([m.uci() for m in board.move_stack])
        candidates = OPENING_BOOK.get(uci_moves)
        if candidates:
            # Filter only legal moves
            legal_uci = [m.uci() for m in board.legal_moves]
            valid = [c for c in candidates if c in legal_uci]
            if valid:
                chosen_uci = random.choice(valid)
                return chess.Move.from_uci(chosen_uci)
        return None

    def apply_style_bonus(self, board: chess.Board, candidate_moves_with_scores):
        """
        Adjusts candidate move scores based on the selected playstyle.
        candidate_moves_with_scores: list of dicts [{'move': Move, 'score': int (cp)}]
        """
        if self.style == Playstyle.STANDARD or not candidate_moves_with_scores:
            return candidate_moves_with_scores

        styled = []
        for cand in candidate_moves_with_scores:
            mv = cand["move"]
            score = cand["score"]
            bonus = 0

            # Style adjustments:
            if self.style == Playstyle.TAL:
                # Aggressive bonuses
                if board.gives_check(mv):
                    bonus += 35
                if board.is_capture(mv):
                    bonus += 25
                # Attack toward opponent king
                opp_king_sq = board.king(not board.turn)
                if opp_king_sq is not None:
                    dist = chess.square_distance(mv.to_square, opp_king_sq)
                    if dist <= 2:
                        bonus += 20

            elif self.style == Playstyle.KARPOV:
                # Positional bonuses: central control, king safety, castling
                if board.is_castling(mv):
                    bonus += 40
                # Center control squares e4, d4, e5, d5
                if mv.to_square in (chess.E4, chess.D4, chess.E5, chess.D5):
                    bonus += 25
                # Avoid early reckless queen sorties
                piece = board.piece_at(mv.from_square)
                if piece and piece.piece_type == chess.QUEEN and len(board.move_stack) < 10:
                    bonus -= 30

            elif self.style == Playstyle.BLITZ:
                # Fast, simple, solid moves
                if board.is_castling(mv):
                    bonus += 30
                if board.is_capture(mv):
                    bonus += 15

            styled.append({"move": mv, "score": score + bonus, "raw_score": score})

        styled.sort(key=lambda x: x["score"], reverse=True)
        return styled

    def get_time_bounds(self):
        """Returns (min_delay, max_delay) based on time control."""
        if self.time_control == TimeControl.BULLET:
            return 0.2, 0.8
        elif self.time_control == TimeControl.BLITZ:
            return 0.5, 2.2
        elif self.time_control == TimeControl.RAPID:
            return 1.0, 4.5
        else: # CLASSICAL
            return 1.5, 9.5

if __name__ == "__main__":
    mgr = OpeningAndStyleManager(style=Playstyle.TAL, time_control=TimeControl.BLITZ)
    b = chess.Board()
    book_mv = mgr.get_book_move(b)
    print("Initial book move:", book_mv)
    print("Time bounds for Blitz:", mgr.get_time_bounds())
