# Autonomous Overlay Chess Pilot & Co-Pilot ♟ (Augmented Reality)

An autonomous chess autopilot and augmented-reality assistant designed to **play on behalf of the user** in live chess games (Chess.com, Lichess, desktop chess apps) with **live background screen streaming** (30–60 FPS in RAM with zero disk I/O).

---

## 🌟 Newly Added Features

### 1. Transparent AR Board Overlay ([`ar_overlay.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/ar_overlay.py))
- **Live Best-Move Arrows**: Renders translucent graphical arrows pointing from the origin square to the target square directly on top of the live chessboard.
- **Dynamic Threat Heatmap**: Automatically highlights undefended pieces in **red**, attacked pieces in **orange**, and check / king danger squares in **gold**.
- **On-Board Telemetry Badge**: Displays real-time Stockfish evaluation and thinking delay beside the board.
- **100% Click-Through**: Built with Windows `WS_EX_LAYERED | WS_EX_TRANSPARENT` so you can click right through the visual overlay.

### 2. Co-Pilot & Instant Take-Over Mode ([`copilot.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/copilot.py))
- **Autonomous Mode**: The pilot evaluates and executes moves automatically on your behalf.
- **Co-Pilot Mode (Ghost Mode)**: Displays AR arrows and threat heatmaps on screen without touching the mouse so you can play manually and learn.
- **Instant Spacebar Take-Over**: In Co-Pilot or Take-Over mode, press **Spacebar** at any moment to make the pilot execute the recommended move instantly!
- **Global Hotkeys**:
  - `[Space]` : Instant Move Execution (Take-over)
  - `[F6]`    : Toggle between Autonomous and Co-Pilot mode
  - `[F7]`    : Toggle AR Overlay visibility On/Off

### 3. Opening Book & GM Playstyles ([`openings_and_styles.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/openings_and_styles.py))
- **Master Opening Repertoire**: Instant theoretical lines for 1. e4 (Sicilian, Open, French, Caro-Kann) and 1. d4 (Queen's Gambit, Slav, Indian Defenses) without spending engine calculation time on moves 1–10.
- **GM Playstyle Personas**:
  - **Mikhail Tal (Aggressive)**: Prefers sharp tactical attacks, open files, piece activity, and king attacks.
  - **Anatoly Karpov (Positional)**: Focuses on pawn structure, center control, king safety, and converting endgames smoothly.
  - **Blitz**: Fast, solid, low-risk moves designed for high-speed play.
  - **Standard**: Balanced Stockfish 19 engine evaluation with humanized variance (15%–25%).

### 4. Clock-Aware Time Controls
Adapts the thinking delay and move calculation speed to your match's time control:
- **Classical**: 1.5s – 9.5s natural thinking delay
- **Rapid**: 1.0s – 4.5s
- **Blitz**: 0.5s – 2.2s
- **Bullet**: 0.2s – 0.8s (near-premove response to prevent flagging)

---

## 🚀 How to Run

### Option A: Floating Control HUD (Recommended)
```bash
python overlay_hud.py
```
Provides dropdowns for Mode (Autonomous / Co-Pilot / Take-Over), Playstyle (Tal / Karpov / Blitz / Standard), Clock Pace, and live evaluation.

### Option B: Terminal CLI with Flags
```bash
# Standard autonomous play
python bot.py

# Co-Pilot mode with Mikhail Tal aggressive style in Blitz
python bot.py --mode co_pilot --style tal --speed blitz

# Take-Over mode where you press Spacebar to play the bot's moves
python bot.py --mode take_over --style karpov --speed rapid
```

---

## 📁 Architecture

- [`ar_overlay.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/ar_overlay.py): Transparent click-through canvas rendering arrows & threat heatmaps.
- [`copilot.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/copilot.py): Mode manager with global Windows hotkeys (`Space`, `F6`, `F7`).
- [`openings_and_styles.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/openings_and_styles.py): GM opening theory, personas (Tal, Karpov, Blitz), and clock bounds.
- [`screen_stream.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/screen_stream.py): High-speed live background screen streamer (30–60 FPS in RAM).
- [`bot.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/bot.py): Main autonomous and co-pilot engine loop.
- [`overlay_hud.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/overlay_hud.py): Always-on-top HUD with full interactive controls.
- [`engine.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/engine.py): Stockfish 19 calculation with opening book and style weights.
- [`board_detector.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/board_detector.py): Computer vision chessboard locator and coordinate mapper.
- [`board_recognizer.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/board_recognizer.py): Real-time square diffing, highlight tracking, and move debouncer.
- [`mouse_controller.py`](file:///c:/Users/nithi/Downloads/projects/Overlay%20Chess%20Player/mouse_controller.py): Smooth Bézier curve mouse controller with natural jitter.
