#!/usr/bin/env python3
"""把根目录 index.html 变换成 APK 内 assets/index.html。

只做两件事情，原页面的功能代码一行都不改：

1. 追加一段脚本：在 document 上做**捕获阶段**拦截「生成并保存」按钮的点击，
   抢在页面自己的 async handler 之前把画布存进系统相册（原生桥 savePng）。
   浏览器里没有桥，脚本直接 return，页面行为与原来完全一致
   （navigator.share → 长按保存兜底）。
2. 追加一点移动端手感样式（去掉点按高亮、禁止长按选中文字）。
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
DST = ROOT / "android" / "assets" / "index.html"

INJECT = """
    <!-- ==== Android 壳注入（由 scripts/make-assets.py 生成，勿手改本文件） ==== -->
    <style>
        html, body { -webkit-tap-highlight-color: transparent; -webkit-user-select: none; user-select: none; }
        canvas { touch-action: none; }
    </style>
    <script>
    (function () {
        // 原生桥的存在决定"保存"走哪条路；网页版里没有它，这段脚本完全不动手
        var bridged = !!(window.AndroidBridge && window.AndroidBridge.savePng);
        if (!bridged) return;

        var btn = document.getElementById('downloadBtn');
        if (btn) btn.textContent = '💾 生成并保存到相册';

        // 页面里的 hasImage 是顶层 let，同一 realm 的后续脚本也能读到
        function pageHasImage() {
            try { if (typeof hasImage === 'boolean') return hasImage; } catch (e) {}
            return true;
        }

        // 捕获阶段拦在 document 上：页面自己那个 async handler 不会被执行，
        // 于是 App 内不走 navigator.share（WebView 不支持）也不用"长按保存"。
        document.addEventListener('click', function (e) {
            var el = e.target;
            while (el && el !== document && el.id !== 'downloadBtn') el = el.parentElement;
            if (!el || el.id !== 'downloadBtn') return;

            e.preventDefault();
            e.stopPropagation();

            if (!pageHasImage()) {
                if (window.AndroidBridge.toast) {
                    window.AndroidBridge.toast('请先点击上方蓝色按钮选择一张图片！');
                }
                return;
            }

            var canvas = document.getElementById('canvas');
            if (!canvas) return;
            var ctx = canvas.getContext('2d', { willReadFrequently: true });

            // 与页面保存前一致：再硬化一次边缘，避免"恢复"回来的半透明毛边发白
            var imgData = ctx.getImageData(0, 0, canvas.width, canvas.height);
            var d = imgData.data;
            for (var i = 0; i < d.length; i += 4) {
                if (d[i + 3] < 128) { d[i + 3] = 0; } else { d[i + 3] = 255; }
            }
            ctx.putImageData(imgData, 0, 0);

            window.AndroidBridge.savePng(
                canvas.toDataURL('image/png'),
                'pixel_' + canvas.width + 'x' + canvas.height + '.png'
            );
        }, true);
    })();
    </script>
</body>"""


def main() -> int:
    html = SRC.read_text(encoding="utf-8")
    if "</body>" not in html:
        print("index.html 缺少 </body>，无法注入", file=sys.stderr)
        return 1
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(html.replace("</body>", INJECT.lstrip("\n"), 1), encoding="utf-8")
    print(f"assets/index.html 已生成 ({DST.stat().st_size} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
