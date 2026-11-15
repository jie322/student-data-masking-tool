"""桌面应用程序生命周期管理模块：负责资源路径探测、环回轻量服务拉起、WebView2 视窗渲染与退出资源销毁。"""
import logging
import sys
from pathlib import Path

import webview

from .bridge import DesktopApi
from .server import start_server


def main():
    """桌面应用程序主生命周期驱动函数：编排静态服务初始化、IPC 桥接注册、视窗渲染与安全退出清理。"""
    # 动态探测应用根目录：在 PyInstaller 冻结打包环境下使用 _MEIPASS 临时释放目录，源码运行环境回退到工程根目录
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    assets = root / "app" if getattr(sys, "frozen", False) else root
    logging.getLogger("pywebview").setLevel(logging.CRITICAL)
    webview.settings["ALLOW_DOWNLOADS"] = True

    # 启动绑定本地环回接口 (127.0.0.1) 的轻量 HTTP 静态资源服务，操作系统动态分配空闲端口规避冲突
    server, thread = start_server(assets)

    # 识别交付自动化验证参数 (--self-test)，自检模式下隔离主题偏好存储以保障纯净环境
    verifying = "--self-test" in sys.argv
    preferences = Path(sys.argv[sys.argv.index("--self-test") + 1]).parent / ".theme-check.json" if verifying else None

    # 初始化原生桌面交互桥接 API 实例（提供原生文件保存对话框与偏好持久化）
    api = DesktopApi(preferences)

    # 创建基于微软 Edge WebView2 渲染内核的原生视窗，注入 JavaScript 宿主桥接对象
    window = webview.create_window(
        "学生信息脱敏工具",
        f"http://127.0.0.1:{server.server_port}/index.html",
        width=1280, height=900, min_size=(900, 650),
        background_color="#101824", text_select=True, hidden=verifying, js_api=api,
    )
    api._window = window

    callback = None
    if verifying:
        from desktop_verify import verify
        callback = lambda: verify(window, Path(sys.argv[sys.argv.index("--self-test") + 1]))

    try:
        # 启动 GUI 主事件循环，强制开启隐身模式 (private_mode) 隔绝历史数据与缓存残留，并注入全中文本地化字典
        webview.start(
            callback, gui="edgechromium", private_mode=True,
            localization={"global.ok": "确定", "global.cancel": "取消", "global.quit": "退出",
                          "global.saveFile": "保存文件", "windows.fileFilter.allFiles": "所有文件",
                          "windows.fileFilter.otherFiles": "其他文件类型"},
        )
    finally:
        # 视窗关闭后触发优雅终止流程，立即停止静态服务并回收套接字与线程资源
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
