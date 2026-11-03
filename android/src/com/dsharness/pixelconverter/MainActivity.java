package com.dsharness.pixelconverter;

import android.app.Activity;
import android.content.ContentValues;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.provider.MediaStore;
import android.util.Base64;
import android.util.Log;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.File;
import java.io.FileOutputStream;
import java.io.OutputStream;

/**
 * 全能像素转换器：一个把本地 index.html 装进 WebView 的极薄原生壳。
 *
 * 只补三件纯浏览器做不到（或做起来很别扭）的事：
 *   1. <input type="file"> 的系统选图（WebChromeClient#onShowFileChooser）
 *   2. 点「保存 PNG」时把 data: URL 直接写进系统相册（JS 桥 savePng）
 *   3. 返回键优先回退网页历史
 *
 * 页面本身（缩放、Alpha 二值化、画布预览）全部由 assets/index.html 完成。
 */
public class MainActivity extends Activity {

    private static final String TAG = "PixelConverter";
    private static final int REQ_PICK_IMAGE = 4001;
    private static final String ASSET_URL = "file:///android_asset/index.html";

    private WebView web;
    private ValueCallback<Uri[]> pendingFileCallback;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(0x2C, 0x2C, 0x2C)); // 和页面底色一致，避免白闪
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(true);       // file:///android_asset 需要
        s.setAllowContentAccess(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);

        // 页面自带深色配色，禁止 WebView 的"强制深色"二次染色
        if (Build.VERSION.SDK_INT >= 33) {
            s.setAlgorithmicDarkeningAllowed(false);
        } else if (Build.VERSION.SDK_INT >= 29) {
            s.setForceDark(WebSettings.FORCE_DARK_OFF);
        }

        web.addJavascriptInterface(new NativeBridge(), "AndroidBridge");
        web.setWebViewClient(new WebViewClient()); // 所有跳转都留在 WebView 内

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                             FileChooserParams params) {
                // 上一次没消费的回调必须先还掉，否则页面会"点了没反应"
                if (pendingFileCallback != null) {
                    pendingFileCallback.onReceiveValue(null);
                    pendingFileCallback = null;
                }
                pendingFileCallback = callback;

                Intent pick = new Intent(Intent.ACTION_GET_CONTENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("image/*");
                String[] accept = (params != null) ? params.getAcceptTypes() : null;
                if (accept != null && accept.length == 1
                        && accept[0] != null && accept[0].contains("/")) {
                    pick.setType(accept[0]);
                }
                try {
                    startActivityForResult(
                            Intent.createChooser(pick, "选择图片"), REQ_PICK_IMAGE);
                    return true;
                } catch (Exception e) {
                    Log.w(TAG, "无法拉起选图器", e);
                    pendingFileCallback = null;
                    return false;
                }
            }
        });

        applySystemBars();
        web.loadUrl(ASSET_URL);
    }

    /** 深色状态栏/导航栏 + 浅色图标，跟页面配色统一。 */
    private void applySystemBars() {
        try {
            getWindow().setStatusBarColor(Color.rgb(0x1E, 0x1E, 0x1E));
            getWindow().setNavigationBarColor(Color.rgb(0x1E, 0x1E, 0x1E));
        } catch (Throwable ignored) {
            // 个别 ROM 改了颜色也没关系
        }
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        if (requestCode == REQ_PICK_IMAGE) {
            Uri[] result = null;
            if (resultCode == RESULT_OK && data != null) {
                Uri uri = data.getData();
                if (uri != null) {
                    result = new Uri[]{uri};
                }
            }
            if (pendingFileCallback != null) {
                pendingFileCallback.onReceiveValue(result);
                pendingFileCallback = null;
            }
            return;
        }
        super.onActivityResult(requestCode, resultCode, data);
    }

    @Override
    public void onBackPressed() {
        if (web != null && web.canGoBack()) {
            web.goBack();
            return;
        }
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.removeJavascriptInterface("AndroidBridge");
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }

    // ---------------------------------------------------------------- JS 桥

    private class NativeBridge {

        @JavascriptInterface
        public boolean hasBridge() {
            return true;
        }

        /** 前端：canvas.toDataURL('image/png') → 直接落盘到相册。 */
        @JavascriptInterface
        public void savePng(String dataUrl, String fileName) {
            String message;
            try {
                message = writePng(decodeDataUrl(dataUrl), fileName);
            } catch (Exception e) {
                Log.e(TAG, "保存 PNG 失败", e);
                message = "保存失败：" + e.getMessage();
            }
            toast(message);
        }

        /** 可选：外部传入纯 base64（不带 data: 前缀）。 */
        @JavascriptInterface
        public void saveBase64(String base64, String fileName) {
            String message;
            try {
                message = writePng(Base64.decode(base64, Base64.DEFAULT), fileName);
            } catch (Exception e) {
                Log.e(TAG, "保存 base64 失败", e);
                message = "保存失败：" + e.getMessage();
            }
            toast(message);
        }
    }

    private byte[] decodeDataUrl(String dataUrl) {
        if (dataUrl == null) {
            throw new IllegalArgumentException("图片数据为空");
        }
        String payload = dataUrl;
        if (payload.startsWith("data:")) {
            int comma = payload.indexOf(',');
            if (comma < 0) {
                throw new IllegalArgumentException("不是合法的 data URL");
            }
            payload = payload.substring(comma + 1);
        }
        return Base64.decode(payload, Base64.DEFAULT);
    }

    private String writePng(byte[] bytes, String rawName) throws Exception {
        String fileName = sanitize(rawName);
        if (Build.VERSION.SDK_INT >= 29) {
            // 分区存储：MediaStore 落进 相册/PixelConverter，不需要任何权限
            ContentValues values = new ContentValues();
            values.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
            values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
            values.put(MediaStore.Images.Media.RELATIVE_PATH,
                    Environment.DIRECTORY_PICTURES + "/PixelConverter");
            values.put(MediaStore.Images.Media.IS_PENDING, 1);

            Uri item = getContentResolver()
                    .insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
            if (item == null) {
                throw new Exception("相册拒绝创建条目");
            }
            OutputStream os = getContentResolver().openOutputStream(item);
            if (os == null) {
                throw new Exception("无法打开输出流");
            }
            try {
                os.write(bytes);
                os.flush();
            } finally {
                os.close();
            }
            values.clear();
            values.put(MediaStore.Images.Media.IS_PENDING, 0);
            getContentResolver().update(item, values, null, null);
            return "已保存到相册 Pictures/PixelConverter/" + fileName;
        }

        // API < 29：落到应用私有 Pictures 目录，免运行时权限
        File dir = new File(getExternalFilesDir(Environment.DIRECTORY_PICTURES), "PixelConverter");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new Exception("无法创建目录 " + dir);
        }
        File out = new File(dir, fileName);
        try (FileOutputStream fos = new FileOutputStream(out)) {
            fos.write(bytes);
            fos.flush();
        }
        return "已保存：" + out.getAbsolutePath();
    }

    private String sanitize(String rawName) {
        String name = (rawName == null) ? "" : rawName.trim();
        if (name.length() == 0) {
            name = "pixel.png";
        }
        name = name.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_");
        if (!name.toLowerCase().endsWith(".png")) {
            name = name + ".png";
        }
        return name;
    }

    private void toast(final String text) {
        runOnUiThread(new Runnable() {
            @Override
            public void run() {
                if (web != null) {
                    Toast.makeText(MainActivity.this, text, Toast.LENGTH_LONG).show();
                }
            }
        });
    }
}
