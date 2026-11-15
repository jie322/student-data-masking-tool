"""Web-Desktop 原生交互桥接模块 (IPC Bridge)：向前端暴露原生文件系统持久化与明暗主题偏好存储接口。"""
import base64
import json
import os
from pathlib import Path

import webview


class DesktopApi:
    """暴露给前端 JavaScript 运行时的原生桥接对象，受限开放受控桌面系统能力。"""

    def __init__(self, preferences=None):
        self._window = None
        # 用户偏好存储在 LOCALAPPDATA 隔离目录下，保障多用户及无权限污染
        self._preferences = preferences or Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "StudentMaskTool" / "preferences.json"

    def get_theme(self):
        """读取持久化的 UI 主题偏好设置；若文件不存在或损坏则优雅回退至默认 dark（暗色）主题。"""
        try:
            settings = json.loads(self._preferences.read_text(encoding="utf-8"))
            theme = settings.get("theme") if isinstance(settings, dict) else None
            return theme if theme in ("dark", "light") else "dark"
        except (OSError, ValueError):
            return "dark"

    def set_theme(self, theme):
        """校验并持久化存储用户主题偏好 (dark / light)。"""
        if theme not in ("dark", "light"):
            return False
        try:
            self._preferences.parent.mkdir(parents=True, exist_ok=True)
            self._preferences.write_text(json.dumps({"theme": theme}), encoding="utf-8")
            return True
        except OSError:
            return False

    def save_export(self, filename, encoded):
        """接收前端打包并完成 Base64 编码的导出产物，调用 Win32 原生保存对话框落盘保存。

        Args:
            filename: 约定白名单中的导出文件名（阻断任意文件写入安全隐患）。
            encoded: 二进制结果包的 Base64 字符串。

        Returns:
            dict: 包含保存状态 (status: "saved" | "cancelled" | "error") 及提示信息的字典。
        """
        # 基于白名单机制强校验文件名及对应扩展名类型，杜绝跨目录或任意文件后缀写入
        types = {"学生信息_脱敏结果.zip": "ZIP 压缩包 (*.zip)", "学生信息_处理报告.json": "JSON 处理报告 (*.json)"}
        if filename not in types or not isinstance(encoded, str):
            return {"status": "error", "message": "导出内容无效，请重新处理。"}
        try:
            # 严格校验并反序列化 Base64 字节流
            data = base64.b64decode(encoded, validate=True)
            # 触发原生系统文件保存选择器
            selected = self._window.create_file_dialog(
                webview.FileDialog.SAVE, save_filename=filename, file_types=(types[filename],))
            # 用户主动取消视为正常交互中断，非程序性异常
            if not selected:
                return {"status": "cancelled"}
            Path(selected[0]).write_bytes(data)
            return {"status": "saved"}
        except Exception:
            return {"status": "error", "message": "保存失败，请选择可写入的位置后重试。"}
