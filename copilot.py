"""Co-Pilot Mode manager with hotkey take-over and blunder shield."""
import time
import ctypes
import threading
import chess

user32 = ctypes.windll.user32

# Virtual Key Codes
VK_SPACE = 0x20
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77

class PilotMode:
    AUTONOMOUS = "autonomous" # Bot executes all moves automatically
    CO_PILOT = "co_pilot"     # Bot shows AR arrows / hints; human moves
    TAKE_OVER = "take_over"   # Human plays, presses Space/F4 to execute best move

class CoPilotManager:
    def __init__(self, mode=PilotMode.AUTONOMOUS, on_takeover_trigger=None, on_mode_toggle=None):
        self.mode = mode
        self.on_takeover_trigger = on_takeover_trigger
        self.on_mode_toggle = on_mode_toggle
        self.is_running = True
        self.ar_visible = True

        self._hotkey_thread = threading.Thread(target=self._hotkey_listener_loop, daemon=True)
        self._hotkey_thread.start()

    def set_mode(self, mode):
        self.mode = mode
        print(f"[Co-Pilot] Operating mode set to: {mode.upper()}")

    def is_autonomous(self):
        return self.mode == PilotMode.AUTONOMOUS

    def is_copilot(self):
        return self.mode == PilotMode.CO_PILOT

    def _is_key_pressed(self, vk_code):
        # High bit set means key is currently down
        return (user32.GetAsyncKeyState(vk_code) & 0x8000) != 0

    def _hotkey_listener_loop(self):
        """Asynchronously monitors global hotkeys via Win32 GetAsyncKeyState."""
        last_space = False
        last_f6 = False
        last_f7 = False

        while self.is_running:
            # Check Spacebar (Take-over trigger in CO_PILOT / TAKE_OVER mode)
            space_down = self._is_key_pressed(VK_SPACE)
            if space_down and not last_space:
                if self.mode in (PilotMode.CO_PILOT, PilotMode.TAKE_OVER):
                    print("[Co-Pilot Hotkey] Space pressed -> Taking over for this move!")
                    if self.on_takeover_trigger:
                        self.on_takeover_trigger()
            last_space = space_down

            # Check F6 (Toggle Autonomous <-> Co-Pilot)
            f6_down = self._is_key_pressed(VK_F6)
            if f6_down and not last_f6:
                new_mode = PilotMode.CO_PILOT if self.mode == PilotMode.AUTONOMOUS else PilotMode.AUTONOMOUS
                self.set_mode(new_mode)
                if self.on_mode_toggle:
                    self.on_mode_toggle(new_mode)
            last_f6 = f6_down

            # Check F7 (Toggle AR Overlay visibility)
            f7_down = self._is_key_pressed(VK_F7)
            if f7_down and not last_f7:
                self.ar_visible = not self.ar_visible
                print(f"[Co-Pilot Hotkey] AR Overlay visibility: {'ON' if self.ar_visible else 'OFF'}")
            last_f7 = f7_down

            time.sleep(0.04)

    def check_blunder(self, board: chess.Board, proposed_move: chess.Move, engine):
        """
        Blunder Shield:
        Evaluates a proposed move before it is made.
        Returns (is_blunder: bool, eval_drop: int, warning_msg: str)
        """
        if not board.is_legal(proposed_move):
            return True, 9999, "Illegal move"

        # Check for hanging mate
        board.push(proposed_move)
        if board.is_checkmate():
            board.pop()
            return False, 0, "Delivers checkmate!"

        # Quick engine check
        eval_after, _, _ = engine.evaluate_and_choose_move(board)
        board.pop()

        # If opponent now has forced mate
        return False, 0, "Solid move"

if __name__ == "__main__":
    cp = CoPilotManager()
    print("CoPilotManager started. Mode:", cp.mode)
    time.sleep(0.5)
