"""Auto-download official Stockfish binary for Windows."""
import os
import shutil
import urllib.request
import zipfile

def download_stockfish():
    url = "https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip"
    os.makedirs("engine", exist_ok=True)
    target_exe = os.path.join("engine", "stockfish.exe")

    if os.path.exists(target_exe):
        print(f"[Stockfish] Binary already installed at: {target_exe}")
        return target_exe

    zip_path = os.path.join("engine", "stockfish.zip")
    print(f"[Stockfish] Downloading Stockfish from {url}...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(zip_path, "wb") as f:
        shutil.copyfileobj(resp, f)

    print("[Stockfish] Extracting...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall("engine/temp")

    os.remove(zip_path)
    for root, _, files in os.walk("engine/temp"):
        for file in files:
            if file.endswith(".exe"):
                shutil.copy2(os.path.join(root, file), target_exe)
                print(f"[Stockfish] Successfully installed at: {target_exe}")
                break

    shutil.rmtree("engine/temp", ignore_errors=True)
    return target_exe

if __name__ == "__main__":
    download_stockfish()
