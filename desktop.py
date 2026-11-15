"""Windows 桌面应用程序启动入口模块。

负责配置跨平台多进程支持 (multiprocessing.freeze_support) 并启动本地 WebView2 嵌入式视窗与专用服务；
若初始化异常则调用 Win32 原生对话框弹出友好错误提示。
"""
import ctypes
import multiprocessing

from desktop_app.application import main


if __name__ == "__main__":
    # 冻结可执行文件环境下的子进程支持，防止多进程调用时循环递归拉起主窗口
    multiprocessing.freeze_support()
    try:
        main()
    except Exception:
        # 桌面独立运行无终端输出环境，调用 Win32 API 弹出系统级中文错误诊断对话框
        ctypes.windll.user32.MessageBoxW(
            None, "程序启动失败。请确认 Microsoft Edge WebView2 运行时已安装后重试。",
            "学生信息脱敏工具", 0x10,
        )
        raise SystemExit(1)
