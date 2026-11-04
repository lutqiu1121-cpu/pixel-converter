# 全能像素转换器 · Pixel Converter

把一张图片压成像素画（默认 32×32），支持预设尺寸 / 自定义宽高，Alpha 二值化去毛边，
像素级预览（棋盘格透明底），一键导出 PNG。

> 🌐 **在线试玩**：<https://lutqiu1121-cpu.github.io/pixel-converter/>
> 📦 **下载 APK**：[`pixel-converter-1.1.apk`](../../releases/download/v1.1.0/pixel-converter-1.1.apk)（25 KB）

同一份 HTML 有两个身份：

- **网页版**：`index.html`，浏览器直接打开就能用。
- **Android App**：`dist/pixel-converter-1.1.apk`，装到手机上是一个独立应用，
  选图走系统相册/文件选择器，保存直接进系统相册 `Pictures/PixelConverter/`。

整个 App 只有一个 WebView 壳，所有图像处理逻辑仍然是那份 HTML 里的 `<canvas>` 代码。

## 下载安装

从 [Releases](../../releases/latest) 下载 `pixel-converter-1.1.apk`，手机上点开安装即可
（APK 用 debug 证书签名，首次安装需要允许"从未知来源安装"）。

- 版本：1.1（versionCode 2）
- 最小系统：Android 7.0（API 24）
- 目标系统：Android 14（API 34）
- 体积：约 25 KB
- SHA-256：`91b7ea04879d8cfd5c5c1714663425e2f13dec18713fa758267c8d8c1a5f3d03`
- 不申请任何权限（Android 10+ 走 MediaStore 存图；Android 9 及以下存到应用自己的图片目录）

## 怎么用

1. 点「📂 点击选择图片」或直接点画布选一张图；
2. 选预设尺寸（16/24/32/48/64/128）或在「自定义尺寸」里填宽高（1–512）；
3. 点「💾 保存到相册」（网页版是「⬇️ 下载 PNG」）。按钮一直可见，没选图时点它会提示先选图。

原图会被最近邻算法直接缩放、不插值，然后做 Alpha 二值化（<128 变全透明，否则全不透明），
所以输出是干净的硬边像素图。

## 打包（不依赖 Gradle）

手机上用 Termux + Android SDK 的 `aapt2 / d8 / apksigner` 就够了：

```bash
./build.sh      # 产物：dist/pixel-converter-1.1.apk
```

脚本做的事情：

| 步骤 | 工具 | 说明 |
| --- | --- | --- |
| 1 | `scripts/make-icons.py` | 纯标准库手写 PNG，生成各密度图标 + 自适应图标前景 |
| 1 | `scripts/make-assets.py` | 把根目录 `index.html` 变换成 `android/assets/index.html`（注入原生保存桥） |
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
  make-assets.py                页面注入（只加桥接，不动原逻辑）
  make-icons.py                 图标生成
build.sh                        一键打包
dist/                           产物
```

## 壳层只补了三件事

1. `<input type="file">` 的系统选图 —— `WebChromeClient#onShowFileChooser` + `onActivityResult`
2. 保存 PNG —— JS 桥 `window.AndroidBridge.savePng(dataUrl, fileName)`，
   原生侧 `Base64` 解码后写 MediaStore（Android 10+ 无需权限）
3. 返回键优先回退网页历史

网页版里 `window.AndroidBridge` 不存在，自动退回 `<a download>`，两份代码共用一套保存逻辑。

## 版本记录

- **v1.1**：下载/保存按钮改为常驻显示（未选图时提示先选图）；`alert` 在 App 里走系统对话框，轻提示走 Toast；版本号改为单一来源（`build.sh`）。
- **v1.0**：首个版本，网页版 + WebView APK。

## 已知限制

- 用 debug 证书签名，不适合上架；要发布请换自己的 keystore（`KEYSTORE=` / `KS_PASS=` / `KEY_ALIAS=`）。
- 保存位置固定为相册 `Pictures/PixelConverter/`，没有做成"另存为"对话框。
- 网页版依赖较新的 Chromium（用到 `repeating-conic-gradient` 画棋盘格），老浏览器棋盘格会变成纯色。

## License

MIT
