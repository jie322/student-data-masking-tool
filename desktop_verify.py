# 桌面自检脚本：像使用者一样点按钮，再检查预览、统计和保存的文件。
"""通过桌面内核执行交付检查，输出数量和断言结果，不记录敏感原文。"""
import csv
import io
import json
import time
import xml.etree.ElementTree as ET
import zipfile


# 输入窗口和检查记录保存位置；结束时写中文结果并关闭测试窗口。
def verify(window, destination):
    result = {"检查状态":"未完成"}
    try:
        if not window.events.loaded.wait(30):
            raise AssertionError("桌面页面加载超时")
        # 运行库需要加载时间；等“导入”按钮可用后才开始操作。
        deadline = time.monotonic() + 60
        while window.evaluate_js("document.querySelector('#sampleBtn').disabled"):
            if time.monotonic() > deadline:
                raise AssertionError("处理引擎启动超时")
            time.sleep(0.25)
        result["独立窗口启动"] = "通过"
        # 先切换再切回，检查显示与桌面主题记忆是否一致。
        initial_theme = window.evaluate_js("document.documentElement.dataset.theme")
        window.evaluate_js("document.querySelector('#themeToggle').click()")
        switched_theme = window.evaluate_js("document.documentElement.dataset.theme")
        assert switched_theme != initial_theme, "主题切换失败"
        wait_for(window, f"window.__savedTheme === '{switched_theme}' || (window.pywebview.api.get_theme().then(theme => window.__savedTheme = theme), false)")
        window.evaluate_js("document.querySelector('#themeToggle').click()")
        assert window.evaluate_js("document.documentElement.dataset.theme") == initial_theme, "主题恢复失败"
        result["明暗主题切换与记忆"] = "通过"
        assert not window.evaluate_js("document.querySelector('footer').innerText.includes('Alvsok')"), "页脚说明未移除"
        window.evaluate_js("document.querySelector('#sampleBtn').click()")
        wait_for(window, "document.querySelectorAll('#rulesBody select').length === 32 && !document.querySelector('#previewBtn').disabled")
        assert not window.evaluate_js("Boolean(document.querySelector('#rulesBody option[value=token]'))"), "处理选项中仍有代号替换"
        window.evaluate_js("document.querySelector('#previewBtn').click()")
        wait_for(window, "document.querySelectorAll('#resultPreview tbody tr').length === 10")
        assert not window.evaluate_js("!document.querySelector('#downloads').hidden"), "预览阶段出现下载入口"
        # 读取第一行预览用于核对；这些值只用于断言，不写入运行日志。
        sample = window.evaluate_js("Array.from(document.querySelectorAll('#resultPreview tbody tr:first-child td'), n => n.textContent)")
        assert sample[0] == "2023******" and sample[1] == "李**" and "****" in sample[6] and "***@***" in sample[8], "预览脱敏不正确"
        result["处理前预览"] = {"状态":"通过", "取样行数":10, "生成导出文件":False}
        window.evaluate_js("""fetch('sample_data/students_100.xlsx').then(r => r.blob()).then(blob => {
            const transfer = new DataTransfer();
            transfer.items.add(new File([blob], 'students_100.xlsx'));
            const input = document.querySelector('#fileInput');
            input.files = transfer.files;
            input.dispatchEvent(new Event('change', {bubbles:true}));
        })""")
        wait_for(window, "document.querySelectorAll('#fileList .file-row').length === 2 && !document.querySelector('#previewBtn').disabled")
        window.evaluate_js("document.querySelector('#previewBtn').click()")
        wait_for(window, "document.querySelectorAll('#resultPreview tbody tr').length === 20")
        result["Excel 导入与预览"] = "通过"
        window.evaluate_js("document.querySelector('#processBtn').click()")
        wait_for(window, "!document.querySelector('#processBtn').disabled && document.querySelector('#exportLink').hasAttribute('href')")
        result["完整处理统计"] = window.evaluate_js("Array.from(document.querySelectorAll('#resultSummary .stat b'), n => Number(n.textContent))")
        assert result["完整处理统计"] == [200,200,1800,0,0,0], "整表统计不正确"
        destination.parent.mkdir(parents=True, exist_ok=True)
        # 自检固定一个保存路径，代替人工选择，但仍调用正式保存接口。
        archive = destination.with_suffix(".zip")
        original_dialog = window.create_file_dialog
        # 自检代替用户选择固定保存位置；保存仍由正式桌面接口执行。
        window.create_file_dialog = lambda *_args, **_kwargs: (str(archive.resolve()),)
        try:
            window.evaluate_js("document.querySelector('#exportLink').click()")
            wait_for(window, "document.querySelector('#message').textContent === '文件已保存。'")
        finally:
            window.create_file_dialog = original_dialog
        # 重新打开真正保存下来的结果包，而不只检查界面上有没有下载按钮。
        with zipfile.ZipFile(archive) as bundle:
            names = bundle.namelist()
            assert len(names) == 3 and "处理报告.json" in names, "结果包内容不正确"
            rows = list(csv.reader(io.StringIO(bundle.read("脱敏结果_01.csv").decode("utf-8-sig"))))
            assert len(rows) == 101 and rows[1] == sample, "导出内容与预览不一致"
            with zipfile.ZipFile(io.BytesIO(bundle.read("脱敏结果_02.xlsx"))) as workbook:
                sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
                assert len(sheet.findall(".//{*}sheetData/{*}row")) == 101, "Excel 导出行数不正确"
            assert json.loads(bundle.read("处理报告.json"))["导出状态"] == "检查通过", "导出报告不正确"
        result["结果包检查"] = "通过，CSV 与 Excel 各 100 行，CSV 与预览一致"
        result["检查状态"] = "全部通过"
    except Exception as error:
        result["检查状态"] = "失败"
        result["原因"] = str(error) if isinstance(error, AssertionError) else type(error).__name__
    finally:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        window.destroy()


# 反复查看一个条件是否成立；超时则说明页面没有完成预期操作。
def wait_for(window, condition):
    deadline = time.monotonic() + 40
    while not window.evaluate_js(condition):
        if time.monotonic() > deadline:
            raise AssertionError("桌面操作检查超时")
        time.sleep(0.2)
