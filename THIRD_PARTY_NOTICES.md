# 项目来源与第三方组件

## 项目来源

本项目基于 [Alvsok/anonymizer](https://github.com/Alvsok/anonymizer) 二次开发，保留原有 Git 提交及 [Apache-2.0 许可证](LICENSE)。

本次开发增加了学生信息表处理模块、中文规则配置、异常行处理、处理前预览、敏感残留检查、明暗主题和 Windows 桌面入口，并拆分了页面与 Python 业务模块。保留的通用匿名化模块仍用于兼容原接口及其测试。

## 第三方组件

| 组件 | 用途 | 许可证与来源 |
| --- | --- | --- |
| Pyodide | 在浏览器中运行 Python | [MPL-2.0](https://github.com/pyodide/pyodide/blob/main/LICENSE)；运行资源位于 `vendor/pyodide/` |
| CPython | Python 解释器与标准库 | [Python 许可证](https://docs.python.org/3/license.html)；浏览器标准库包含在 `vendor/pyodide/python_stdlib.zip` |
| micropip | Pyodide 的 Python 包安装支持 | [MPL-2.0](https://github.com/pyodide/micropip)；原始 wheel 位于 `vendor/pyodide/` |
| openpyxl | 读写 XLSX 表格 | [MIT](https://openpyxl.readthedocs.io/en/stable/)；原始 wheel 位于 `vendor/wheels/`，其中保留许可文件 |
| et_xmlfile | openpyxl 的 XML 写出支持 | [MIT](https://pypi.org/project/et-xmlfile/)；原始 wheel 位于 `vendor/wheels/`，其中保留许可文件 |
| JSZip | 在页面中生成结果压缩包 | 使用其 MIT 授权；完整许可见 [vendor/jszip/LICENSE.markdown](vendor/jszip/LICENSE.markdown) |
| pywebview | 桌面窗口与系统保存对话框 | [BSD-3-Clause](https://github.com/r0x0r/pywebview) |
| pythonnet | Windows 桌面端的 .NET 桥接 | [MIT](https://github.com/pythonnet/pythonnet) |
| PyInstaller | 构建 Windows 可执行程序 | [GPL-2.0 及打包例外](https://pyinstaller.org/en/stable/license.html) |

桌面依赖由 `requirements-desktop.txt` 安装，构建脚本会收集已安装组件的许可文件。各组件的版权和具体条款以其原始许可为准。

## 数据来源

公开资料的来源、作者、许可及整理过程见 [公开数据说明](public_data/数据来源与使用说明.md) 和 [sources.json](public_data/sources.json)。公开数据采用各自的使用条款，不因存放于本仓库而改用项目源码许可证。
