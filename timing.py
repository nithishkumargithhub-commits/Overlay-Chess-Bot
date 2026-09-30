"""Natural human-like chess move timing with strict bounds between 2.0s and 9.0s."""
import random
import time
import chess

class ChessTimer:
    def __init__(self, min_delay=2.0, max_delay=9.0, hard_cap=10.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.hard_cap = hard_cap

    def calculate_delay(self, board: chess.Board, chosen_move: chess.Move = None, move_count: int = 1) -> float:
        """
        Calculates a natural human-like thinking delay:
        - Bounded strictly between 2.0 and 9.0 seconds.
        - Never exceeds 10.0 seconds under any circumstance.
        """
        legal_count = len(list(board.legal_moves))
        is_recapture = False
        if chosen_move and board.is_capture(chosen_move):
            is_recapture = True

        if legal_count <= 2 or is_recapture:
            # Snappy response for recaptures or forced moves
            mean = 2.5
            std = 0.4
        elif move_count <= 6:
            # Opening phase
            mean = 3.2
            std = 0.8
        elif board.is_check():
            mean = 4.2
            std = 1.2
        else:
            # Middlegame / Complex positions
            mean = random.choice([3.8, 5.0, 6.5, 7.8])
            std = 1.3

        raw_delay = random.gauss(mean, std)

        # Strictly enforce bounds: between 2.0 and 9.0 seconds
        clamped_delay = max(self.min_delay, min(self.max_delay, raw_delay))
        if clamped_delay >= self.hard_cap:
            clamped_delay = self.max_delay

        return round(clamped_delay, 2)

    def wait_delay(self, delay_sec: float, callback_tick=None, interval=0.1):
        """Waits for the calculated delay."""
        start = time.time()
        end = start + delay_sec
        while time.time() < end:
            remaining = max(0.0, end - time.time())
            if callback_tick:
                callback_tick(remaining, delay_sec)
            time.sleep(min(interval, remaining))

if __name__ == "__main__":
    timer = ChessTimer()
    b = chess.Board()
    for i in range(10):
        d = timer.calculate_delay(b, move_count=i+1)
        assert 2.0 <= d <= 9.0, f"Delay {d} out of bounds!"
        print(f"Sample delay {i+1}: {d}s")
    print("All timing constraints [2.0s - 9.0s] verified!")
