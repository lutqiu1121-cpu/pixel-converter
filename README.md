# 神隐录像素编辑器 · Pixel Editor

（原名「全能像素转换器」）

把一张图片压成像素画（默认 32×32），自动漫水填充去掉白底、保留透明，
再用手动微调笔刷擦除/恢复像素，最后一键导出 PNG。

同一份 HTML 有两个身份：

- **网页版**：`index.html`，浏览器直接打开就能用。
- **Android App**：`dist/pixel-converter-1.2.apk`，装到手机上是一个独立应用，
  选图走系统相册/文件选择器，保存直接进系统相册 `Pictures/PixelConverter/`。

整个 App 只有一个 WebView 壳，所有图像处理逻辑仍然是那份 HTML 里的 `<canvas>` 代码。

> 🌐 **在线试玩**：<https://lutqiu1121-cpu.github.io/pixel-converter/>
> 📦 **下载 APK**：[`pixel-converter-1.2.apk`](../../releases/download/v1.2.0/pixel-converter-1.2.apk)（约 29 KB）

## 下载安装

从 [Releases](../../releases/latest) 下载 `pixel-converter-1.2.apk`，手机上点开安装即可
（APK 用 debug 证书签名，首次安装需要允许"从未知来源安装"）。

- 版本：1.2（versionCode 3）
- 最小系统：Android 7.0（API 24）
- 目标系统：Android 14（API 34）
- 体积：约 29 KB
- SHA-256：`a677a1e8d3a93614f2146e87921d2329a21e1c4e4500d7ce7aa1c6d8730f376c`
- 不申请任何权限（Android 10+ 走 MediaStore 存图；Android 9 及以下存到应用自己的图片目录）

## 怎么用

1. 点「📂 点击选择图片」选一张图（画布会自动按预设尺寸重采样，最近邻、不插值）。
2. 去白底：默认勾选「🪄 智能去除白底」，从图像四条边做**漫水填充**，
   只清掉连通到边缘的白色区域，内部白点会保留；「容差」滑杆 200–255 控制"多白才算白"。
3. 手动微调：点「🛠️ 开启手动微调模式」，在画布上直接画。
   - 🧽 擦除：把像素变透明
   - 🖌️ 恢复：从原始底图把该像素画回来（颜色和透明度都还原）
   - 笔刷 1/2/3 px，↩️ 撤销最多回退 10 步
4. 点「⬇️ 生成并保存」。保存前会再做一次边缘硬化（<128 透明 / 其余不透明），
   避免"恢复"出来的半透明毛边在游戏里发白。

保存通道按环境自动选：**App 内**直接写系统相册（原生桥，弹 Toast 提示路径）；
**手机浏览器**走 `navigator.share` 分享面板；都不支持时退回显示图片"长按保存"。

## 打包（不依赖 Gradle）

手机上用 Termux + Android SDK 的 `aapt2 / d8 / apksigner` 就够了：

```bash
./build.sh      # 产物：dist/pixel-converter-1.2.apk
```

脚本做的事情：

| 步骤 | 工具 | 说明 |
| --- | --- | --- |
| 1 | `scripts/make-icons.py` | 纯标准库手写 PNG，生成各密度图标 + 自适应图标前景 |
| 1 | `scripts/make-assets.py` | 把根目录 `index.html` 变换成 `android/assets/index.html`（注入原生保存拦截） |
| 2 | `aapt2 compile` | 编译 `res/` |
| 3 | `aapt2 link` | 链接 manifest + 资源 + assets，出壳 APK |
| 4 | `javac` + `d8` | 编译 `MainActivity` 并转成 `classes.dex` |
| 5 | `zip` | 把 `classes.dex` 塞进 APK（并校验 `resources.arsc` 未压缩、4 字节对齐） |
| 6 | `apksigner` | 用 `~/.android/debug.keystore` 签名（含 v1/v2/v3） |

版本号只在 `build.sh` 顶部改（`VERSION_NAME` / `VERSION_CODE`）；manifest 里不写，否则会盖掉命令行参数。

可用环境变量覆盖工具路径：`JAVA_HOME`、`ANDROID_SDK`、`BUILD_TOOLS`、`ANDROID_JAR`、`AAPT2`、`KEYSTORE`。

> 注意：`build-tools` 里自带的 `aapt2` 是 x86_64 主机二进制，手机上跑不了，
> 所以脚本默认用 aarch64 版 `aapt2`（`AAPT2=` 可改）。

## 目录结构

```
index.html                      网页版（唯一需要维护的页面）
android/
  AndroidManifest.xml
  src/com/dsharness/pixelconverter/MainActivity.java   WebView 壳 + 选图 + 存图桥
  assets/index.html             build.sh 生成，别手改
  res/                          图标 / 应用名
scripts/
  make-assets.py                页面注入（只加保存拦截，不动原逻辑）
  make-icons.py                 图标生成
build.sh                        一键打包
dist/                           产物
```

## 壳层只补了四件事

1. `<input type="file">` 的系统选图 —— `WebChromeClient#onShowFileChooser` + `onActivityResult`
2. 保存 PNG —— JS 桥 `window.AndroidBridge.savePng(dataUrl, fileName)`，
   原生侧 `Base64` 解码后写 MediaStore（Android 10+ 无需权限）
3. 返回键优先回退网页历史
4. `alert` / 轻提示 —— `onJsAlert` 走系统对话框，`AndroidBridge.toast()` 走 Toast

保存这一路由注入脚本在 `document` 上做**捕获阶段**拦截（`stopPropagation`），
这样页面自己那段 `navigator.share → 长按保存` 的兜底逻辑在 App 里不会执行
——WebView 既不支持 Web Share，也不给 `<img>` 长按菜单。
浏览器里注入脚本直接 `return`，页面行为与原来完全一致。

> 早先版本用的是「clone 掉按钮再重挂监听」，这版不行：按钮的 `display` 由页面在
> `img.onload` 里控制，clone 出来的副本收不到那个更新，会一直隐藏。捕获阶段拦截不碰 DOM，绕开了这个问题。

## 版本记录

- **v1.2**：改名「神隐录像素编辑器」；新增漫水填充去白底 + 容差滑杆、手动微调（擦除/恢复笔刷、1/2/3px、撤销 10 步）；保存改为 `navigator.share` 优先 + 长按保存兜底，App 内经捕获阶段拦截走原生相册。
- **v1.1**：下载/保存按钮改为常驻显示（未选图时提示先选图）；版本号改为单一来源（`build.sh`）。
- **v1.0**：首个版本，网页版 + WebView APK。

## 已知限制

- 用 debug 证书签名，不适合上架；要发布请换自己的 keystore（`KEYSTORE=` / `KS_PASS=` / `KEY_ALIAS=`）。
- 保存位置固定为相册 `Pictures/PixelConverter/`，没有做成"另存为"对话框。
- WebView 里没有 `navigator.share`，因此 App 内不会弹系统分享面板，直接进相册。
- 网页版依赖较新的 Chromium（用到 `repeating-conic-gradient` 画棋盘格），老浏览器棋盘格会变成纯色。

## License

MIT
