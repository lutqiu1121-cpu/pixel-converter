#!/usr/bin/env python3
"""把根目录 index.html 变换成 APK 内 assets/index.html。

只做两件事情，原页面的功能代码一行都不改：
1. 追加一段脚本：点「下载 PNG」时优先走 WebView 原生桥保存到系统相册
   （浏览器里仍退回到 <a download>，所以同一个文件两边都能用）。
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
        canvas { touch-action: manipulation; }
    </style>
    <script>
    (function () {
        // 原生桥的存在决定"保存"走哪条路；网页版里没有它，行为与原来完全一致
        var bridged = !!(window.AndroidBridge && window.AndroidBridge.savePng);

        var btn    = document.getElementById('download');
        var canvas = document.getElementById('canvas');
        if (!btn || !canvas) return;

        // 原页面里的 hasImage 是顶层 let，同一 realm 的后续脚本也能读到
        function pageHasImage() {
            try { if (typeof hasImage === 'boolean') return hasImage; } catch (e) {}
            return true;   // 读不到就不拦，交给下游逻辑
        }

        // clone 掉原监听器：网页版仍走 <a download>，App 里改走原生相册保存
        var fresh = btn.cloneNode(true);
        btn.parentNode.replaceChild(fresh, btn);
        if (bridged) fresh.textContent = '💾 保存到相册 (需先选图)';

        fresh.addEventListener('click', function () {
            if (!pageHasImage()) {
                var msg = '请先点击上方蓝色按钮选择一张图片！';
                if (bridged && window.AndroidBridge.toast) {
                    window.AndroidBridge.toast(msg);
                } else {
                    alert(msg);
                }
                return;
            }

            var fileName = 'pixel_' + canvas.width + 'x' + canvas.height + '.png';
            var dataUrl  = canvas.toDataURL('image/png');
            if (bridged) {
                window.AndroidBridge.savePng(dataUrl, fileName);
                return;
            }
            var a = document.createElement('a');
            a.download = fileName;
            a.href = dataUrl;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
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
