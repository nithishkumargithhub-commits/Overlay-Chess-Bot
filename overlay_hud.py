"""Floating always-on-top HUD overlay with live telemetry and controls."""
import tkinter as tk
from tkinter import ttk
import threading
import time
import chess

from bot import AutonomousUserChessPilot
from openings_and_styles import Playstyle, TimeControl
from copilot import PilotMode

class ChessPilotHUD:
    def __init__(self, root):
        self.root = root
        self.root.title("Autonomous Chess Pilot & Co-Pilot")
        self.root.geometry("420x460+20+20")
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#121212")

        # Styling
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure(".", background="#121212", foreground="#ffffff")
        self.style.configure("TLabel", background="#121212", foreground="#e0e0e0", font=("Segoe UI", 9))
        self.style.configure("Header.TLabel", font=("Segoe UI", 12, "bold"), foreground="#00e676")
        self.style.configure("Status.TLabel", font=("Segoe UI", 11, "bold"), foreground="#29b6f6")
        self.style.configure("TCombobox", fieldbackground="#1e1e1e", background="#333333", foreground="#ffffff")

        # Header
        header = ttk.Label(root, text="♟ CHESS PILOT & CO-PILOT", style="Header.TLabel")
        header.pack(pady=(10, 2))

        sub = tk.Label(root, text="Live Screen Stream • AR Overlay • Co-Pilot Hotkeys",
                       bg="#121212", fg="#888888", font=("Segoe UI", 8))
        sub.pack(pady=(0, 6))

        # Status Label
        self.lbl_status = ttk.Label(root, text="Status: Starting...", style="Status.TLabel")
        self.lbl_status.pack(pady=2)

        # Info Frame
        frame_info = tk.Frame(root, bg="#1e1e1e", padx=12, pady=8)
        frame_info.pack(fill="x", padx=15, pady=5)

        self.lbl_user_color = tk.Label(frame_info, text="Playing As: AUTO-DETECTING",
                                       bg="#1e1e1e", fg="#ffffff", font=("Segoe UI", 9, "bold"))
        self.lbl_user_color.pack(anchor="w", pady=1)

        self.lbl_board = tk.Label(frame_info, text="Board: Scanning screen...",
                                  bg="#1e1e1e", fg="#aaaaaa", font=("Segoe UI", 9))
        self.lbl_board.pack(anchor="w", pady=1)

        self.lbl_last_move = tk.Label(frame_info, text="Last Move: None",
                                      bg="#1e1e1e", fg="#ffca28", font=("Segoe UI", 9))
        self.lbl_last_move.pack(anchor="w", pady=1)

        self.lbl_eval = tk.Label(frame_info, text="Engine Eval: --",
                                 bg="#1e1e1e", fg="#81c784", font=("Segoe UI", 9))
        self.lbl_eval.pack(anchor="w", pady=1)

        self.lbl_delay = tk.Label(frame_info, text="Delay: --",
                                  bg="#1e1e1e", fg="#ba68c8", font=("Segoe UI", 9))
        self.lbl_delay.pack(anchor="w", pady=1)

        # Settings Grid
        frame_settings = tk.Frame(root, bg="#181818", padx=10, pady=8)
        frame_settings.pack(fill="x", padx=15, pady=5)

        # Mode Selector
        tk.Label(frame_settings, text="Mode:", bg="#181818", fg="#cccccc", font=("Segoe UI", 9)).grid(row=0, column=0, sticky="w", pady=3)
        self.combo_mode = ttk.Combobox(frame_settings, values=["Autonomous", "Co-Pilot (Hints only)", "Take-Over (Spacebar)"], state="readonly", width=22)
        self.combo_mode.current(0)
        self.combo_mode.grid(row=0, column=1, sticky="w", padx=8, pady=3)
        self.combo_mode.bind("<<ComboboxSelected>>", self.on_mode_change)

        # Playstyle Selector
        tk.Label(frame_settings, text="Playstyle:", bg="#181818", fg="#cccccc", font=("Segoe UI", 9)).grid(row=1, column=0, sticky="w", pady=3)
        self.combo_style = ttk.Combobox(frame_settings, values=["Standard", "Tal (Aggressive)", "Karpov (Positional)", "Blitz"], state="readonly", width=22)
        self.combo_style.current(0)
        self.combo_style.grid(row=1, column=1, sticky="w", padx=8, pady=3)
        self.combo_style.bind("<<ComboboxSelected>>", self.on_style_change)

        # Time Control Selector
        tk.Label(frame_settings, text="Clock Pace:", bg="#181818", fg="#cccccc", font=("Segoe UI", 9)).grid(row=2, column=0, sticky="w", pady=3)
        self.combo_speed = ttk.Combobox(frame_settings, values=["Classical (1.5-9.5s)", "Rapid (1.0-4.5s)", "Blitz (0.5-2.2s)", "Bullet (0.2-0.8s)"], state="readonly", width=22)
        self.combo_speed.current(0)
        self.combo_speed.grid(row=2, column=1, sticky="w", padx=8, pady=3)
        self.combo_speed.bind("<<ComboboxSelected>>", self.on_speed_change)

        # Control Buttons
        frame_btn = tk.Frame(root, bg="#121212")
        frame_btn.pack(pady=8)

        self.btn_pause = tk.Button(frame_btn, text="Pause Pilot", command=self.toggle_pause,
                                   bg="#37474f", fg="#ffffff", relief="flat", padx=10, pady=4)
        self.btn_pause.grid(row=0, column=0, padx=4)

        self.btn_calib = tk.Button(frame_btn, text="Re-Scan", command=self.recalibrate,
                                   bg="#00695c", fg="#ffffff", relief="flat", padx=10, pady=4)
        self.btn_calib.grid(row=0, column=1, padx=4)

        self.btn_color = tk.Button(frame_btn, text="Switch Color", command=self.toggle_color,
                                   bg="#424242", fg="#ffffff", relief="flat", padx=10, pady=4)
        self.btn_color.grid(row=0, column=2, padx=4)

        # Hotkey Legend
        lbl_legend = tk.Label(root, text="Hotkeys: [Space] Take-over move | [F6] Co-Pilot | [F7] AR",
                              bg="#121212", fg="#777777", font=("Segoe UI", 8))
        lbl_legend.pack(pady=(2, 0))

        self.is_paused = False
        self.pilot = AutonomousUserChessPilot(color_mode="auto", enable_ar=True)
        self.worker_thread = threading.Thread(target=self._run_pilot_loop, daemon=True)
        self.worker_thread.start()

    def on_mode_change(self, event=None):
        idx = self.combo_mode.current()
        modes = [PilotMode.AUTONOMOUS, PilotMode.CO_PILOT, PilotMode.TAKE_OVER]
        self.pilot.copilot.set_mode(modes[idx])
        self.pilot.pilot_mode = modes[idx]

    def on_style_change(self, event=None):
        idx = self.combo_style.current()
        styles = [Playstyle.STANDARD, Playstyle.TAL, Playstyle.KARPOV, Playstyle.BLITZ]
        self.pilot.engine.style_mgr.style = styles[idx]
        print(f"[HUD] Selected Playstyle: {styles[idx].upper()}")

    def on_speed_change(self, event=None):
        idx = self.combo_speed.current()
        speeds = [TimeControl.CLASSICAL, TimeControl.RAPID, TimeControl.BLITZ, TimeControl.BULLET]
        self.pilot.engine.style_mgr.time_control = speeds[idx]
        min_d, max_d = self.pilot.engine.style_mgr.get_time_bounds()
        self.pilot.timer.min_delay = min_d
        self.pilot.timer.max_delay = max_d
        print(f"[HUD] Clock pace: {speeds[idx].upper()} ({min_d}s - {max_d}s)")

    def update_hud(self, status=None, board_pos=None, user_color=None, last_move=None, evaluation=None, delay=None):
        if status:
            self.lbl_status.config(text=f"Status: {status}")
        if board_pos:
            self.lbl_board.config(text=f"Board: {board_pos}")
        if user_color:
            self.lbl_user_color.config(text=f"Playing As: {user_color}")
        if last_move:
            self.lbl_last_move.config(text=f"Last Move: {last_move}")
        if evaluation:
            self.lbl_eval.config(text=f"Eval: {evaluation}")
        if delay:
            self.lbl_delay.config(text=f"Delay: {delay}")

    def toggle_pause(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.config(text="Resume Pilot", bg="#c62828")
            self.lbl_status.config(text="Status: PAUSED", foreground="#ef5350")
        else:
            self.btn_pause.config(text="Pause Pilot", bg="#37474f")
            self.lbl_status.config(text="Status: Active", foreground="#29b6f6")

    def recalibrate(self):
        self.pilot.board_bounds = None
        self.pilot.stream.set_region(None)
        if self.pilot.ar_overlay:
            self.pilot.ar_overlay.clear()
            self.pilot.ar_overlay.hide()
        self.lbl_board.config(text="Board: Scanning...")
        self.lbl_status.config(text="Status: Scanning...", foreground="#ffa726")

    def toggle_color(self):
        if self.pilot.user_color == chess.WHITE:
            self.pilot.user_color = chess.BLACK
            self.pilot.color_mode = "black"
            self.update_hud(user_color="BLACK (Manual)")
        else:
            self.pilot.user_color = chess.WHITE
            self.pilot.color_mode = "white"
            self.update_hud(user_color="WHITE (Manual)")

    def _run_pilot_loop(self):
        self.pilot.stream.start()
        self.update_hud(status="Live stream active. Scanning...")

        last_candidate_move = None
        candidate_count = 0

        while self.pilot.is_active:
            if self.is_paused:
                time.sleep(0.2)
                continue

            try:
                screen = self.pilot.stream.get_latest_frame()
                if screen is None:
                    time.sleep(0.04)
                    continue

                if self.pilot.board_bounds is None:
                    bounds = self.pilot.detector.find_chessboard(screen)
                    if bounds:
                        self.pilot.board_bounds = bounds
                        bx, by, bw, bh = bounds

                        if self.pilot.color_mode == "auto":
                            side = self.pilot.detector.orientation
                            self.pilot.user_color = chess.WHITE if side == "white" else chess.BLACK

                        color_str = "WHITE" if self.pilot.user_color == chess.WHITE else "BLACK"
                        self.update_hud(status="Board locked!", board_pos=f"{bw}x{bh} at ({bx},{by})",
                                        user_color=color_str)

                        if self.pilot.ar_overlay and self.pilot.copilot.ar_visible:
                            self.pilot.ar_overlay.update_position(bounds, self.pilot.detector.orientation)

                        self.pilot.stream.set_region(bounds)
                        time.sleep(0.1)
                        board_crop = self.pilot.stream.get_latest_frame()
                        self.pilot.recognizer.update_state(board_crop)
                    else:
                        time.sleep(0.2)
                        continue

                board_crop = self.pilot.stream.get_latest_frame()
                if board_crop is None:
                    time.sleep(0.03)
                    continue

                if not self.pilot.detector._verify_chessboard_lattice(board_crop):
                    obscured_count = getattr(self, "_obscured_count", 0) + 1
                    self._obscured_count = obscured_count
                    if obscured_count >= 20:
                        self.update_hud(status="Board obscured / waiting...")
                        self.pilot.board_bounds = None
                        self.pilot.stream.set_region(None)
                        if self.pilot.ar_overlay:
                            self.pilot.ar_overlay.clear()
                            self.pilot.ar_overlay.hide()
                        self._obscured_count = 0
                        time.sleep(0.5)
                        continue
                    else:
                        time.sleep(0.05)
                        continue
                else:
                    self._obscured_count = 0

                curr_crops = self.pilot.recognizer.extract_square_crops(board_crop)

                # Reset detection
                if len(self.pilot.board.move_stack) > 1 and self.pilot.recognizer.is_initial_position(curr_crops):
                    self.pilot.board.reset()
                    self.pilot.move_number = 1
                    self.pilot.has_played_first_move = False
                    self.pilot.recognizer.update_state(board_crop)
                    if self.pilot.ar_overlay:
                        self.pilot.ar_overlay.clear()
                    self.update_hud(status="New game detected!", last_move="Game Start")
                    time.sleep(0.5)
                    continue

                # Game over
                is_over, over_msg = self.pilot.engine.check_game_status(self.pilot.board)
                if is_over:
                    self.update_hud(status=over_msg)
                    if self.pilot.ar_overlay:
                        self.pilot.ar_overlay.clear()
                    time.sleep(1.0)
                    continue

                if self.pilot.board.turn == self.pilot.user_color:
                    chosen_move, score, reason = self.pilot.engine.evaluate_and_choose_move(self.pilot.board)
                    if chosen_move:
                        delay = self.pilot.timer.calculate_delay(self.pilot.board, chosen_move, move_count=self.pilot.move_number)
                        move_san = self.pilot.board.san(chosen_move)
                        eval_str = f"{score/100:+.2f}" if abs(score) < 15000 else ("Mate" if score > 0 else "-Mate")
                        self.update_hud(status=f"Thinking... ({reason})", evaluation=eval_str, delay=f"{delay}s")

                        if self.pilot.ar_overlay and self.pilot.copilot.ar_visible and self.pilot.board_bounds:
                            self.pilot.ar_overlay.update_view(self.pilot.board, chosen_move, eval_str=eval_str, delay_str=f"{delay}s")

                        if self.pilot.copilot.is_copilot():
                            if self.pilot._takeover_requested:
                                self.pilot._takeover_requested = False
                                ok = self.pilot._execute_move_with_verification(chosen_move)
                                if ok:
                                    self.update_hud(last_move=f"Pilot (User): {move_san}")
                            else:
                                time.sleep(0.08)
                                continue
                        else:
                            time.sleep(delay)
                            ok = self.pilot._execute_move_with_verification(chosen_move)
                            if ok:
                                self.update_hud(last_move=f"Pilot (User): {move_san}")
                else:
                    self.update_hud(status="Waiting for opponent move...")
                    detected_move = self.pilot.recognizer.detect_move_from_diffs(self.pilot.board, curr_crops)
                    if detected_move is not None:
                        if detected_move == last_candidate_move:
                            candidate_count += 1
                        else:
                            last_candidate_move = detected_move
                            candidate_count = 1

                        if candidate_count >= 2:
                            san_move = self.pilot.board.san(detected_move)
                            self.pilot.board.push(detected_move)
                            self.pilot.recognizer.update_state(board_crop)
                            self.update_hud(last_move=f"Opponent: {san_move}")
                            last_candidate_move = None
                            candidate_count = 0
                    else:
                        last_candidate_move = None
                        candidate_count = 0
                        time.sleep(0.04)

            except Exception as e:
                print(f"[HUD Loop Error] {e}")
                time.sleep(0.5)

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessPilotHUD(root)
    root.mainloop()
