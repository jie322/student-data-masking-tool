# 重新生成便携 EXE 的工具脚本；开发者手动运行，日常脱敏不会执行它。
"""收集运行资源，构建便携单文件 EXE；不包含开发环境、原始公开数据或处理结果。"""
import importlib.metadata
import shutil
import subprocess
import sys
from pathlib import Path


# ROOT 为项目目录；STAGE 为本次打包使用的资源暂存目录。
ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "build" / "desktop-assets" / "app"


# 准备资源副本和许可证，再调用 PyInstaller，将 desktop.py 作为打包入口。
def main():
    # 清理上次的暂存副本之前核对路径范围，避免误删项目之外的目录。
    if STAGE.exists():
        if not STAGE.resolve().is_relative_to(ROOT / "build"):
            raise ValueError("构建资源路径超出项目的 build 目录。")
        shutil.rmtree(STAGE)
    STAGE.mkdir(parents=True)
    # 将页面、脚本、Python 算法和第三方库复制到打包暂存区。
    for name in ("index.html", "sw.js", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, STAGE / name)
    for name in ("css", "js", "py", "static", "vendor"):
        shutil.copytree(ROOT / name, STAGE / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # 程序内只附带三份操作用表格；原始公开数据和处理结果不随程序打包。
    (STAGE / "sample_data").mkdir()
    for name in ("students_100.csv", "students_100.xlsx", "students_edge_cases.csv"):
        shutil.copy2(ROOT / "sample_data" / name, STAGE / "sample_data" / name)
    # 收集所用组件的许可文件，随运行资源保留。
    licenses = STAGE / "licenses"
    licenses.mkdir()
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, licenses / "CPython-LICENSE.txt")
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"]
        for item in distribution.files or []:
            if item.name.upper().startswith(("LICENSE", "COPYING", "NOTICE")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    folder = licenses / name
                    folder.mkdir(exist_ok=True)
                    shutil.copy2(source, folder / item.name)
    # 启动打包命令：onefile=单个 EXE，windowed=运行时不显示控制台。
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "学生信息脱敏工具", "--icon", str(ROOT / "static" / "favicon.ico"),
        "--add-data", str(STAGE) + ";app", "--hidden-import", "desktop_verify",
        "--exclude-module", "PyQt5", "--exclude-module", "PyQt6", "--exclude-module", "PySide6",
        "--distpath", str(ROOT.parent), "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"), str(ROOT / "desktop.py"),
    ], cwd=ROOT, check=True)
    # 打包产物放在项目上一级，输出实际文件大小便于确认。
    executable = ROOT.parent / "学生信息脱敏工具.exe"
    print(f"构建完成：{executable}（{executable.stat().st_size / 1_000_000:.1f} MB）")


if __name__ == "__main__":
    main()
