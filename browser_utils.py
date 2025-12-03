import platform, subprocess, re
try:
    import winreg
except ImportError:
    winreg = None

def get_installed_chrome_major():
    # Windows detection
    if platform.system().lower() == "windows" and winreg:
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                key = winreg.OpenKey(root, r"Software\\Google\\Chrome\\BLBeacon")
                version, _ = winreg.QueryValueEx(key, "version")
                return int(str(version).split(".")[0])
            except Exception:
                continue
    # Linux/macOS detection
    for cmd in ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]:
        try:
            output = subprocess.check_output([cmd, "--version"], stderr=subprocess.STDOUT, text=True)
            match = re.search(r"(\d+)\.", output)
            if match:
                return int(match.group(1))
        except Exception:
            continue
    return None
