#!/usr/bin/env python3
"""纯标准库生成 APK 图标（本机没有 Pillow，就直接手写 PNG）。

产物：
  res/mipmap-mdpi..xxxhdpi/ic_launcher.png   传统图标（带深色圆角底）
  res/mipmap-xxxhdpi/ic_launcher_foreground.png  自适应图标前景（透明底）
  res/mipmap-anydpi-v26/ic_launcher.xml      自适应图标声明
  res/values/colors.xml                      自适应图标底色
"""
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "android" / "res"

BG = (0x2C, 0x2C, 0x2C)
HEART = (0xFF, 0x5A, 0x5A)

# 7x6 像素心形：X = 实心
HEART_ROWS = [
    ".XX.XX.",
    "XXXXXXX",
    "XXXXXXX",
    ".XXXXX.",
    "..XXX..",
    "...X...",
]


def write_png(path: pathlib.Path, width: int, height: int, rgba: bytearray) -> None:
    """rgba: width*height*4，逐行 filter 0 后 zlib 压缩。"""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw.extend(rgba[y * stride:(y + 1) * stride])
    comp = zlib.compress(bytes(raw), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def rounded_rect_alpha(x: float, y: float, size: float, radius: float) -> float:
    """点 (x,y) 在圆角矩形内的覆盖率（0/1，边缘本身不再做细分）。"""
    r = radius
    cx = min(max(x, r), size - r)
    cy = min(max(y, r), size - r)
    dx, dy = x - cx, y - cy
    return 1.0 if dx * dx + dy * dy <= r * r else 0.0


def render(size: int, with_bg: bool) -> bytearray:
    """渲染一张 size×size 的 RGBA 图。with_bg=True 时画深色圆角底。"""
    rgba = bytearray(size * size * 4)
    cover = 0.62 if not with_bg else 0.58           # 心形占画布比例
    heart_w = size * cover
    cell = heart_w / len(HEART_ROWS[0])
    gx = (size - heart_w) / 2
    gy = (size - len(HEART_ROWS) * cell) / 2
    radius = size * 0.22

    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            r = g = b = a = 0

            if with_bg and rounded_rect_alpha(x + 0.5, y + 0.5, size, radius) > 0:
                r, g, b, a = BG[0], BG[1], BG[2], 255

            # 心形（4x4 超采样做一点抗锯齿）
            hit = 0
            for sy in range(4):
                for sx in range(4):
                    px = x + (sx + 0.5) / 4 - gx
                    py = y + (sy + 0.5) / 4 - gy
                    if 0 <= px < heart_w and 0 <= py < len(HEART_ROWS) * cell:
                        col = int(px // cell)
                        row = int(py // cell)
                        if HEART_ROWS[row][col] == "X":
                            hit += 1
            if hit:
                sa = hit / 16.0
                # 竖向轻微渐变，让心形不那么平
                shade = 0.82 + 0.18 * (1 - (y - gy) / max(heart_w, 1))
                shade = min(max(shade, 0.0), 1.0)
                fr, fg_, fb = (int(c * shade) for c in HEART)
                if a == 0:
                    r, g, b, a = fr, fg_, fb, int(255 * sa)
                else:
                    k = sa          # 前景覆盖背景
                    r = int(fr * k + r * (1 - k))
                    g = int(fg_ * k + g * (1 - k))
                    b = int(fb * k + b * (1 - k))
                    a = 255

            rgba[i] = r
            rgba[i + 1] = g
            rgba[i + 2] = b
            rgba[i + 3] = a
    return rgba


def main() -> int:
    legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    for density, size in legacy.items():
        out = RES / f"mipmap-{density}" / "ic_launcher.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        write_png(out, size, size, render(size, True))
        print(f"  {out.relative_to(ROOT)}  {size}x{size}")

    fg = RES / "mipmap-xxxhdpi" / "ic_launcher_foreground.png"
    write_png(fg, 432, 432, render(432, False))
    print(f"  {fg.relative_to(ROOT)}  432x432")

    xml = '''<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@color/ic_launcher_background" />
    <foreground android:drawable="@mipmap/ic_launcher_foreground" />
</adaptive-icon>
'''
    (RES / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    (RES / "mipmap-anydpi-v26" / "ic_launcher.xml").write_text(xml, encoding="utf-8")
    print(f"  {pathlib.Path('mipmap-anydpi-v26/ic_launcher.xml')}")

    colors = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#2C2C2C</color>
</resources>
'''
    (RES / "values" / "colors.xml").write_text(colors, encoding="utf-8")
    print(f"  {pathlib.Path('values/colors.xml')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
