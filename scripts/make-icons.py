#!/usr/bin/env python3
"""纯标准库生成 APK 图标（本机没有 Pillow，就直接手写 PNG）。

主体是一只像素马克杯（Cup 的像素编辑器的"杯子"）：
杯身奶油色、杯口一圈深色咖啡、右边一个小把手、上方两缕蒸汽。

产物：
  res/mipmap-mdpi..xxxhdpi/ic_launcher.png        传统图标（带深色圆角底）
  res/mipmap-xxxhdpi/ic_launcher_foreground.png   自适应图标前景（透明底）
  res/mipmap-anydpi-v26/ic_launcher.xml           自适应图标声明
  res/values/colors.xml                           自适应图标底色
"""
import pathlib
import struct
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES = ROOT / "android" / "res"

BG = (0x2C, 0x2C, 0x2C)

# 像素调色板：B 杯身 / D 杯身暗部 / C 咖啡 / H 把手 / S 蒸汽
PALETTE = {
    "B": (0xF2, 0xE4, 0xD0),
    "D": (0xD3, 0xBF, 0xA5),
    "C": (0x5B, 0x3A, 0x29),
    "H": (0xDC, 0xC8, 0xAE),
    "S": (0xB8, 0xB8, 0xB8),
}

# 10 列 x 7 行：杯口 + 深色咖啡液面 + 杯壁，下面一个更宽的托盘
CUP_ROWS = [
    ".BBBBBBBD.....",
    ".BCCCCCCDHH...",
    ".BBBBBBBD..H..",
    ".BBBBBBBD..H..",
    ".BBBBBBBDHH...",
    "..BBBBBB......",
    "DDDDDDDDDD....",
    ".DDDDDDDD.....",
]


assert len({len(r) for r in CUP_ROWS}) == 1, "CUP_ROWS 每行长度必须一致"


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
    cols = len(CUP_ROWS[0])
    rows = len(CUP_ROWS)

    cover = 0.66 if not with_bg else 0.62          # 主体占画布比例
    art_w = size * cover
    cell = art_w / cols
    gx = (size - art_w) / 2
    gy = (size - rows * cell) / 2
    radius = size * 0.22

    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            r = g = b = a = 0

            if with_bg and rounded_rect_alpha(x + 0.5, y + 0.5, size, radius) > 0:
                r, g, b, a = BG[0], BG[1], BG[2], 255

            # 像素图案（每格 4x4 超采样做抗锯齿）
            hit = {}
            for sy in range(4):
                for sx in range(4):
                    px = x + (sx + 0.5) / 4 - gx
                    py = y + (sy + 0.5) / 4 - gy
                    if 0 <= px < cols * cell and 0 <= py < rows * cell:
                        ch = CUP_ROWS[int(py // cell)][int(px // cell)]
                        if ch != ".":
                            hit[ch] = hit.get(ch, 0) + 1

            if hit:
                # 覆盖率最高的字符决定这一像素的颜色，用它的占比做 alpha
                ch, count = max(hit.items(), key=lambda kv: kv[1])
                sa = count / 16.0
                fr, fg_, fb = PALETTE[ch]
                # 竖向轻微渐变，避免整块死板
                shade = 0.86 + 0.14 * (1 - (y - gy) / max(art_w, 1))
                shade = min(max(shade, 0.0), 1.0)
                fr = int(fr * shade)
                fg_ = int(fg_ * shade)
                fb = int(fb * shade)

                if a == 0:
                    r, g, b, a = fr, fg_, fb, int(255 * sa)
                else:
                    k = sa
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
    print("  mipmap-anydpi-v26/ic_launcher.xml")

    colors = '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="ic_launcher_background">#2C2C2C</color>
</resources>
'''
    (RES / "values" / "colors.xml").write_text(colors, encoding="utf-8")
    print("  values/colors.xml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
