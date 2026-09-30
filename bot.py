"""Autonomous Chess Pilot with AR Overlay, Co-Pilot Mode, Playstyles, and Clock Controls."""
import sys
import time
import random
import argparse
import threading
import chess
import cv2
import numpy as np

from screen_stream import LiveScreenStream
from board_detector import BoardDetector
from board_recognizer import BoardRecognizer
from engine import ChessEngine
from mouse_controller import MouseController
from timing import ChessTimer
from openings_and_styles import OpeningAndStyleManager, Playstyle, TimeControl
from copilot import CoPilotManager, PilotMode
from ar_overlay import ChessAROverlay

class AutonomousUserChessPilot:
    """
    Autonomous & Co-Pilot Chess Assistant that plays on behalf of the user.
    Includes:
    - High-speed live background screen streaming (30-60 FPS)
    - Transparent AR Overlay with real-time arrows and threat heatmaps
    - Co-Pilot / Take-Over mode (Spacebar trigger)
    - Opening book and custom playstyles (Tal, Karpov, Blitz, Standard)
    - Dynamic clock time control (Classical, Rapid, Blitz, Bullet)
    """
    def __init__(self, role="opponent", color_mode="auto", pilot_mode=PilotMode.AUTONOMOUS,
                 style=Playstyle.STANDARD, time_control=TimeControl.CLASSICAL,
                 enable_ar=True):
        print("=" * 68)
        role_label = "CHESS OPPONENT BOT (PLAYING AGAINST HUMAN)" if role == "opponent" else "CHESS PILOT (PLAYING FOR USER)"
        print(f"    AUTONOMOUS {role_label}   ")
        print("=" * 68)
        print(f"[*] Bot Role       : {role.upper()}")
        print(f"[*] Operating Mode : {pilot_mode.upper()} (F6 to toggle Co-Pilot)")
        print(f"[*] Playstyle      : {style.upper()} (Tal / Karpov / Blitz / Standard)")
        print(f"[*] Time Control   : {time_control.upper()} (2.0s - 9.0s delay)")
        print(f"[*] Color Mode     : {color_mode.upper()} (Auto-detects board side)")
        print(f"[*] AR Overlay     : {'ENABLED (F7 to toggle)' if enable_ar else 'DISABLED'}")
        print("[*] Hotkeys        : [Space] Instant Move Take-over | [F6] Mode | [F7] AR")
        print("=" * 68)

        self.role = role
        self.color_mode = color_mode
        self.bot_color = chess.BLACK if color_mode == "black" else (chess.WHITE if color_mode == "white" else None)
        self.user_color = self.bot_color
        self.pilot_mode = pilot_mode
        self.enable_ar = enable_ar

        self.stream = LiveScreenStream(target_fps=30)
        self.detector = BoardDetector()
        self.recognizer = BoardRecognizer(self.detector)
        self.engine = ChessEngine(style=style, time_control=time_control)
        self.mouse = MouseController()

        # Dynamic clock bounds from time control
        min_d, max_d = self.engine.style_mgr.get_time_bounds()
        self.timer = ChessTimer(min_delay=min_d, max_delay=max_d, hard_cap=max(min_d + 0.5, max_d + 0.5))

        self.copilot = CoPilotManager(
            mode=pilot_mode,
            on_takeover_trigger=self._on_takeover_pressed,
            on_mode_toggle=self._on_mode_toggled
        )

        self.ar_overlay = ChessAROverlay() if enable_ar else None

        self.board = chess.Board()
        self.board_bounds = None
        self.is_active = True
        self.move_number = 1
        self.has_played_first_move = False
        self.pending_candidate_move = None
        self._takeover_requested = False

    def _on_takeover_pressed(self):
        """Callback when user presses Spacebar in Co-Pilot / Take-Over mode."""
        self._takeover_requested = True

    def _on_mode_toggled(self, new_mode):
        self.pilot_mode = new_mode

    def run(self):
        """Starts the live streaming thread, AR loop, and autonomous play loop."""
        self.stream.start()
        print("\n[+] Live stream started. Scanning for chessboard...")

        consecutive_not_found = 0
        last_candidate_move = None
        candidate_count = 0

        try:
            while self.is_active:
                # Process AR overlay events if active
                if self.ar_overlay and self.ar_overlay.root:
                    try:
                        self.ar_overlay.root.update_idletasks()
                        self.ar_overlay.root.update()
                    except Exception:
                        pass

                # 1. Grab latest live frame
                screen = self.stream.get_latest_frame()
                if screen is None:
                    time.sleep(0.04)
                    continue

                # 2. Board Localization & Calibration
                if self.board_bounds is None:
                    bounds = self.detector.find_chessboard(screen)
                    if bounds:
                        self.board_bounds = bounds
                        bx, by, bw, bh = bounds
                        consecutive_not_found = 0

                        if self.color_mode == "auto":
                            detected_side = self.detector.orientation
                            if self.role == "opponent":
                                self.bot_color = chess.BLACK if detected_side == "white" else chess.WHITE
                            else:
                                self.bot_color = chess.WHITE if detected_side == "white" else chess.BLACK
                        else:
                            self.bot_color = chess.WHITE if self.color_mode == "white" else chess.BLACK

                        self.user_color = self.bot_color
                        bot_str = "BLACK" if self.bot_color == chess.BLACK else "WHITE"
                        print(f"\n[+] Chessboard locked at ({bx}, {by}, {bw}x{bh})")
                        role_descr = "Opponent (Playing against human)" if self.role == "opponent" else "Pilot (Playing for user)"
                        print(f"[+] Orientation: {self.detector.orientation.upper()} | Bot Color: {bot_str} | Role: {role_descr}")

                        # Update AR overlay geometry
                        if self.ar_overlay and self.copilot.ar_visible:
                            self.ar_overlay.update_position(bounds, self.detector.orientation)

                        # Switch live stream to high-speed region capture (50+ FPS)
                        self.stream.set_region(bounds)
                        time.sleep(0.1)

                        board_frame = self.stream.get_latest_frame()
                        self.recognizer.update_state(board_frame)
                        self.has_played_first_move = False
                        print("[+] Calibrated. System ready!")
                    else:
                        consecutive_not_found += 1
                        if consecutive_not_found % 15 == 0:
                            sys.stdout.write(".")
                            sys.stdout.flush()
                        time.sleep(0.2)
                        continue

                # 3. Live Board Region Processing
                board_crop = self.stream.get_latest_frame()
                if board_crop is None:
                    time.sleep(0.03)
                    continue

                # Verify board bounds with debounced lattice check
                if not self.detector._verify_chessboard_lattice(board_crop):
                    obscured_count = getattr(self, "_obscured_count", 0) + 1
                    self._obscured_count = obscured_count
                    if obscured_count >= 20: # ~1.5s of continuous obstruction
                        print("\n[!] Board obscured or closed. Reverting to full-screen scanner...")
                        self.board_bounds = None
                        self.stream.set_region(None)
                        if self.ar_overlay:
                            self.ar_overlay.clear()
                            self.ar_overlay.hide()
                        self._obscured_count = 0
                        time.sleep(0.5)
                        continue
                    else:
                        time.sleep(0.05)
                        continue
                else:
                    self._obscured_count = 0

                curr_crops = self.recognizer.extract_square_crops(board_crop)

                # 4. Check for New Game / Rematch
                if len(self.board.move_stack) > 1 and self.recognizer.is_initial_position(curr_crops):
                    print("\n[*] New game / rematch detected! Resetting board state.")
                    self.board.reset()
                    self.move_number = 1
                    self.has_played_first_move = False
                    self.recognizer.update_state(board_crop)
                    if self.ar_overlay:
                        self.ar_overlay.clear()
                    time.sleep(0.5)
                    continue

                # 5. Check if game is over
                is_over, over_msg = self.engine.check_game_status(self.board)
                if is_over:
                    if self.ar_overlay:
                        self.ar_overlay.clear()
                    time.sleep(1.0)
                    continue

                # 6. Whose turn is it?
                if self.board.turn == self.user_color:
                    # User's turn
                    self._handle_user_turn(board_crop)
                    last_candidate_move = None
                    candidate_count = 0
                else:
                    # Opponent's turn: detect move via diffs
                    detected_move = self.recognizer.detect_move_from_diffs(self.board, curr_crops)
                    if detected_move is not None:
                        if detected_move == last_candidate_move:
                            candidate_count += 1
                        else:
                            last_candidate_move = detected_move
                            candidate_count = 1

                        if candidate_count >= 2:
                            san_move = self.board.san(detected_move)
                            self.board.push(detected_move)
                            self.recognizer.update_state(board_crop)
                            print(f"\n[Opponent Move] {san_move} ({detected_move.uci()})")

                            last_candidate_move = None
                            candidate_count = 0

                            if not self.board.is_game_over() and self.board.turn == self.user_color:
                                self._handle_user_turn(board_crop)
                    else:
                        last_candidate_move = None
                        candidate_count = 0
                        time.sleep(0.04)

        except KeyboardInterrupt:
            print("\n[!] Stopping Autonomous Pilot...")
        finally:
            self.stream.stop()
            self.engine.close()
            if self.ar_overlay and self.ar_overlay.root:
                try:
                    self.ar_overlay.root.destroy()
                except Exception:
                    pass
            print("[+] Pilot shut down cleanly.")

    def _handle_user_turn(self, latest_board_crop):
        """Calculates best move, updates AR visual overlay, and executes if autonomous or take-over triggered."""
        # 1. Evaluate position with Opening Book & Playstyle
        chosen_move, score, reason = self.engine.evaluate_and_choose_move(self.board, humanize_pct=0.20)
        if chosen_move is None:
            return

        self.pending_candidate_move = chosen_move
        delay = self.timer.calculate_delay(self.board, chosen_move, move_count=self.move_number)
        move_san = self.board.san(chosen_move)
        eval_disp = f"{score/100:+.2f}" if abs(score) < 15000 else ("Mate" if score > 0 else "-Mate")

        # 2. Update Transparent AR Overlay
        if self.ar_overlay and self.copilot.ar_visible and self.board_bounds:
            self.ar_overlay.update_view(self.board, chosen_move, eval_str=eval_disp, delay_str=f"{delay}s")

        # 3. Decision depending on Pilot Mode
        if self.copilot.is_copilot():
            # In Co-Pilot mode: Display suggestions only. Do NOT move mouse automatically!
            # If the user presses Spacebar to take over, execute immediately!
            if self._takeover_requested:
                self._takeover_requested = False
                print(f"[Take-Over] Executing requested move: {move_san}")
                self._execute_move_with_verification(chosen_move)
            else:
                # Human is thinking / playing
                time.sleep(0.08)
                return

        elif self.copilot.mode == PilotMode.TAKE_OVER:
            # Only play if Spacebar pressed
            if self._takeover_requested:
                self._takeover_requested = False
                print(f"[Take-Over] Executing: {move_san}")
                self._execute_move_with_verification(chosen_move)
            else:
                time.sleep(0.08)
                return

        else:
            # AUTONOMOUS MODE
            print(f"[Bot] Move chosen: {move_san} ({chosen_move.uci()}) | Delay: {delay}s | Eval: {eval_disp} | {reason}")
            # Natural delay between 2 and 9 seconds
            time.sleep(delay)
            self._execute_move_with_verification(chosen_move)

    def _execute_move_with_verification(self, move: chess.Move) -> bool:
        """
        Executes a move using the strict Reliable Piece Movement procedure:
        - Prefers click -> click.
        - Verifies whether the piece actually moved to the intended square.
        - Retries up to 2 times with 0.8-1.2s delay if move fails.
        - Falls back to drag-and-drop if click-click repeatedly fails.
        """
        from_sq_name = chess.square_name(move.from_square)
        to_sq_name = chess.square_name(move.to_square)

        from_coords = self.detector.get_square_center(from_sq_name)
        to_coords = self.detector.get_square_center(to_sq_name)

        if not from_coords or not to_coords:
            print(f"[!] Could not map {from_sq_name}->{to_sq_name} to screen coordinates.")
            return False

        # Capture pre-move board snapshot for verification
        pre_board_crop = self.stream.get_latest_frame()
        pre_crops = self.recognizer.extract_square_crops(pre_board_crop)

        # Primary interaction method
        preferred_method = getattr(self, "preferred_method", "click_click")
        # Try preferred method first, then fallback to alternative
        alt_method = "drag_and_drop" if preferred_method == "click_click" else "click_click"
        methods_to_try = [preferred_method, alt_method]

        for method in methods_to_try:
            method_name = "Click -> Click" if method == "click_click" else "Drag-and-Drop"
            # Initial attempt + up to 2 retries = 3 attempts per method
            for attempt in range(1, 4):
                if attempt > 1:
                    retry_wait = random.uniform(0.8, 1.2)
                    print(f"[*] Move not detected on board. Waiting {retry_wait:.2f}s before retry {attempt-1}/2 with {method_name}...")
                    time.sleep(retry_wait)
                else:
                    print(f"[*] Executing move {move.uci()} using {method_name}...")

                # 1. Execute piece movement with deliberate timings
                if method == "click_click":
                    self.mouse.execute_click_click(from_coords, to_coords)
                else:
                    self.mouse.execute_drag_and_drop(from_coords, to_coords)

                # 2. Handle pawn promotion if applicable
                if move.promotion:
                    time.sleep(0.18)
                    self.mouse.click(to_coords[0], to_coords[1])

                # 3. Automatic Verification
                post_board_crop = self.stream.get_latest_frame()
                post_crops = self.recognizer.extract_square_crops(post_board_crop)

                verified, diff_from, diff_to = self.recognizer.verify_move_completed(move, pre_crops, post_crops)
                if verified:
                    print(f"[✓ Verified] Move {move.uci()} confirmed on screen! (from_diff={diff_from:.1f}, to_diff={diff_to:.1f})")
                    self.preferred_method = method # Keep working method
                    self.board.push(move)
                    self.move_number += 1
                    self.has_played_first_move = True

                    if self.ar_overlay:
                        self.ar_overlay.clear()

                    time.sleep(0.35)
                    ref_crop = self.stream.get_latest_frame()
                    if ref_crop is not None:
                        self.recognizer.update_state(ref_crop)

                    is_over, over_msg = self.engine.check_game_status(self.board)
                    if is_over:
                        print(f"\n[Game Over] {over_msg}")
                    return True
                else:
                    print(f"[!] Verification failed (diff_from={diff_from:.1f}, diff_to={diff_to:.1f}). Piece did not move.")

            print(f"[!] {method_name} failed after 2 retries. Switching to fallback interaction method...")

        print(f"[Error] Move {move.uci()} failed after all retries and fallback methods.")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous & Co-Pilot Chess Assistant")
    parser.add_argument("--role", choices=["opponent", "player"], default="opponent",
                        help="Bot role: 'opponent' (plays as opponent against human) or 'player' (plays for user)")
    parser.add_argument("--color", choices=["auto", "white", "black"], default="auto",
                        help="Color side: 'auto', 'white', or 'black'")
    parser.add_argument("--mode", choices=["autonomous", "co_pilot", "take_over"], default="autonomous",
                        help="Operation mode: 'autonomous' (auto play), 'co_pilot' (AR visual hints only), or 'take_over' (Spacebar trigger)")
    parser.add_argument("--style", choices=["standard", "tal", "karpov", "blitz"], default="standard",
                        help="Playstyle persona: 'standard', 'tal' (aggressive), 'karpov' (positional), or 'blitz'")
    parser.add_argument("--speed", choices=["classical", "rapid", "blitz", "bullet"], default="classical",
                        help="Time control pace: 'classical' (2-9s), 'rapid' (1-4.5s), 'blitz' (0.5-2.2s), 'bullet' (0.2-0.8s)")
    parser.add_argument("--no-ar", action="store_true", help="Disable the transparent on-board AR overlay")

    args = parser.parse_args()

    pilot = AutonomousUserChessPilot(
        role=args.role,
        color_mode=args.color,
        pilot_mode=args.mode,
        style=args.style,
        time_control=args.speed,
        enable_ar=not args.no_ar
    )
    pilot.run()
