"""Raw window I/O for Caves of Qud: capture the window, send keys to it.

Usage:
  python win.py shot out.png        capture the game window (no focus change)
  python win.py key <vk-name> ...   focus the game and tap keys (e.g. key down down return)
"""
import ctypes, ctypes.wintypes as wt, sys, time
from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32")
user32.SetProcessDPIAware()

def find_window(title="CavesOfQud"):
    hwnd = user32.FindWindowW(None, title)
    if not hwnd:
        raise SystemExit(f"window '{title}' not found")
    return hwnd

def client_size(hwnd):
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    return r.right - r.left, r.bottom - r.top

def capture(hwnd):
    w, h = client_size(hwnd)
    hdc = user32.GetDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h)
    gdi32.SelectObject(mdc, bmp)
    # PW_CLIENTONLY | PW_RENDERFULLCONTENT: works for DirectX windows, even if covered
    ok = user32.PrintWindow(hwnd, mdc, 1 | 2)
    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG),
                    ("biPlanes", wt.WORD), ("biBitCount", wt.WORD), ("biCompression", wt.DWORD),
                    ("biSizeImage", wt.DWORD), ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                    ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]
    bih = BIH(ctypes.sizeof(BIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bih), 0)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    return ok, Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)

VK = {"return": 0x0D, "escape": 0x1B, "space": 0x20, "left": 0x25, "up": 0x26, "right": 0x27,
      "down": 0x28, "tab": 0x09, "backspace": 0x08}
for i in range(10):
    VK[f"num{i}"] = 0x60 + i
EXTENDED = {0x25, 0x26, 0x27, 0x28}

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", _U)]

def vk_of(name):
    if name in VK:
        return VK[name]
    if len(name) == 1:
        return user32.VkKeyScanW(ord(name)) & 0xFF
    raise SystemExit(f"unknown key {name}")

def tap(vk):
    scan = user32.MapVirtualKeyW(vk, 0)
    ext = 1 if vk in EXTENDED else 0
    for up in (0, 2):
        inp = INPUT(type=1)
        inp.ki = KEYBDINPUT(vk, scan, up | ext, 0, 0)
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(0.03)

def focus(hwnd):
    # Alt tap lets a background process take the foreground
    user32.keybd_event(0x12, 0, 0, 0); user32.keybd_event(0x12, 0, 2, 0)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)
    return user32.GetForegroundWindow() == hwnd

if __name__ == "__main__":
    hwnd = find_window()
    if sys.argv[1] == "shot":
        ok, img = capture(hwnd)
        img.save(sys.argv[2])
        print("printwindow", ok, "size", img.size)
    elif sys.argv[1] == "post":
        # background keys via window messages (no focus change); Unity may ignore these
        for k in sys.argv[2:]:
            vk = vk_of(k); scan = user32.MapVirtualKeyW(vk, 0)
            ext = (1 << 24) if vk in EXTENDED else 0
            user32.PostMessageW(hwnd, 0x100, vk, 1 | (scan << 16) | ext)
            time.sleep(0.05)
            user32.PostMessageW(hwnd, 0x101, vk, 1 | (scan << 16) | ext | (3 << 30))
            time.sleep(0.1)
    elif sys.argv[1] == "key":
        print("focused", focus(hwnd))
        for k in sys.argv[2:]:
            tap(vk_of(k)); time.sleep(0.1)
