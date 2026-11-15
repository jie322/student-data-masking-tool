# 学生工具的主要行为检查：字段推荐、手机号邮箱身份证、预览、异常策略、残留和新文件导出。
"""针对毕业设计要求的行为测试，可直接用标准库 unittest 运行。"""
import csv
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openpyxl
from openpyxl.comments import Comment

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "py"))
from student import HIDDEN, INVALID, inspect_file, mask_value, preview_file, process_file, read_tables, recommend, valid_identity, validate_rules

SECRET = "student-rules-verification-2026"


class StudentToolTests(unittest.TestCase):
    # 每个测试先创建独立临时目录，避免改动项目中的源表格。
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    # 把本测试准备的表头与行写入临时文件，作为算法输入。
    def source(self, headers, rows, encoding="utf-8-sig", extension="csv"):
        path = self.root / ("input." + extension)
        with path.open("w", encoding=encoding, newline="") as stream:
            writer = csv.writer(stream, delimiter="\t" if extension == "tsv" else ",")
            writer.writerow(headers); writer.writerows(rows)
        return path

    # 按测试配置运行正式处理入口，返回结果及输出路径便于比较。
    def run_file(self, source, rules=None, policy="mask", destination=None):
        rules = rules or {c: recommend(c) for t in read_tables(source) for c in t["columns"]}
        destination = destination or self.root / ("output" + source.suffix)
        return process_file(source, destination, rules, policy, SECRET), destination

    # 验证中文表头能推荐对应字段，成绩等普通列默认保留。
    def test_chinese_field_recommendations(self):
        self.assertEqual(recommend("手机号")["type"], "phone")
        self.assertEqual(recommend("身份证号")["type"], "identity")
        self.assertEqual(recommend("监护人手机号")["mode"], "mask")
        self.assertEqual(recommend("语文成绩")["mode"], "keep")

    # 验证 +86、括号等不同电话写法得到相同规范结果。
    def test_phone_variants_have_identical_result(self):
        for value in ("13900000001", "+86 13900000001", "008613900000001", "139-0000-0001", "139 0000 0001"):
            with self.subTest(value=value):
                self.assertEqual(mask_value(value, recommend("手机号"), SECRET)[0], "+86 139****0001")

    # 验证大小写和加号邮箱写法，以及域名隐藏开关。
    def test_email_plus_uppercase_and_hidden_domain(self):
        rule = recommend("邮箱")
        for value in ("Student+school@example.test", "student.one@school.example.test"):
            self.assertEqual(mask_value(value, rule, SECRET)[0], "s***@***")
        rule["keep_domain"] = True
        self.assertEqual(mask_value("Student@example.test", rule, SECRET)[0], "s***@example.test")

    # 验证只有一个字的姓名和短邮箱也不会完整暴露。
    def test_one_character_email_and_name_never_expose_whole_value(self):
        self.assertEqual(mask_value("a@example.test", recommend("邮箱"), SECRET)[0], "***@***")
        self.assertEqual(mask_value("李", recommend("姓名"), SECRET)[0], "*")

    # 验证只接受 18 位结构，并检查出生日期与校验位。
    def test_identity_checksum_date_and_strict_18_digits(self):
        rows = read_tables(ROOT / "sample_data/students_100.csv")[0]["rows"]
        self.assertTrue(all(valid_identity(str(row[7])) for row in rows))
        self.assertTrue(all(len(str(row[7])) == 18 for row in rows))
        self.assertFalse(valid_identity("11010820050230001X"))
        self.assertFalse(valid_identity("110108200502020011"))
        self.assertFalse(valid_identity("110108050202001"))

    # 验证格式错误的原文被隐藏，而不是原样输出。
    def test_invalid_formats_use_safe_fallback(self):
        for column, value in (("手机号", "12345"), ("邮箱", "bad@@example.test"), ("身份证号", "123"), ("手机号", "139*00000001")):
            result, code, _ = mask_value(value, recommend(column), SECRET)
            self.assertEqual((result, code), (INVALID, "format"))

    # 验证保留位数过多、负数等配置会被拒绝。
    def test_rules_reject_excessive_and_negative_digits(self):
        for prefix, suffix in ((6, 6), (-1, 0), (1.5, 0), (True, 0), (None, 0)):
            rule = {**recommend("手机号"), "prefix":prefix, "suffix":suffix}
            with self.assertRaises(ValueError): validate_rules({"手机号":rule})

    # 验证未知字段类型与不存在的处理方式不会被执行。
    def test_unknown_types_and_modes_are_rejected(self):
        for field, value in (("type", "unknown"), ("mode", "unknown")):
            with self.assertRaises(ValueError): validate_rules({"手机号":{**recommend("手机号"), field:value}})

    # 验证错误使用规则不能绕过完整身份证原文的残留检查。
    def test_rule_misuse_cannot_leave_identity_raw(self):
        source = self.source(["身份证号"], [["110108200502020019"]])
        result, target = self.run_file(source, {"身份证号":recommend("邮箱")})
        self.assertFalse(result["blocked"])
        self.assertEqual(read_tables(target)[0]["rows"][0][0], INVALID)

    # 验证学号使用星号遮盖，旧代号选项不可重新启用。
    def test_identifiers_use_star_masks_and_token_mode_is_rejected(self):
        rule = recommend("学号")
        self.assertEqual(rule["mode"], "mask")
        self.assertEqual(mask_value("2023000001", rule)[0], "2023******")
        with self.assertRaises(ValueError): validate_rules({"学号":{**rule, "mode":"token"}})

    # 验证重新导入历史代号时全部隐藏，避免误认为原始身份数据。
    def test_legacy_token_is_hidden_when_imported_again(self):
        result, code, _ = mask_value("代号_编号_abcdefghijklmnop", recommend("学号"))
        self.assertEqual((result, code), (HIDDEN, "remasked"))

    # 验证对已有遮盖结果再次处理，结果保持一致；这叫重复处理稳定性。
    def test_repeated_processing_is_idempotent(self):
        source = self.source(["学号", "姓名", "手机号", "邮箱"], [["2023000001", "李明轩", "+86 13962578301", "li.mingxuan001@qq.com"]])
        first, output = self.run_file(source)
        second, again = self.run_file(output, destination=self.root / "again.csv")
        self.assertFalse(first["blocked"] or second["blocked"])
        self.assertEqual(read_tables(output), read_tables(again))

    # 验证预览与正式结果一致，预览不写输出文件且源文件不变。
    def test_preview_matches_batch_without_writing_files_or_changing_source(self):
        original = read_tables(ROOT / "sample_data/students_100.csv")[0]
        tsv = self.source(original["columns"], original["rows"], extension="tsv")
        for source in (ROOT / "sample_data/students_100.csv", ROOT / "sample_data/students_100.xlsx", tsv):
            with self.subTest(extension=source.suffix):
                rules = {c: recommend(c) for c in original["columns"]}
                before_hash = hashlib.sha256(source.read_bytes()).digest()
                before_files = set(self.root.iterdir())
                preview = preview_file(source, rules, secret=SECRET)
                self.assertEqual(set(self.root.iterdir()), before_files)
                self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), before_hash)
                self.assertEqual(preview["summary"]["input_rows"], 10)
                self.assertEqual(preview["summary"]["masked_cells"], 90)
                batch, _ = self.run_file(source, rules)
                self.assertEqual(preview["sheets"][0]["columns"], batch["sheets"][0]["columns"])
                self.assertEqual(preview["sheets"][0]["rows"], batch["sheets"][0]["rows"])

    # 验证每张表仅取十行预览，且不能据此跳过整表检查。
    def test_preview_only_checks_first_ten_rows_per_sheet(self):
        source = self.root / "input.xlsx"
        book = openpyxl.Workbook()
        for i, count in enumerate((13, 14)):
            sheet = book.active if i == 0 else book.create_sheet()
            sheet.append(["手机号", "附言"])
            for row in range(count):
                sheet.append(["13900000001", "联系13900000001" if row == 10 else "正常"])
        book.save(source)
        rules = {c: recommend(c) for c in ("手机号", "附言")}
        preview = preview_file(source, rules, secret=SECRET)
        self.assertEqual(preview["summary"]["input_rows"], 20)
        self.assertEqual([s["count"] for s in preview["sheets"]], [10, 10])
        self.assertFalse(preview["blocked"])
        batch, target = self.run_file(source, rules)
        self.assertEqual(batch["summary"]["input_rows"], 27)
        self.assertTrue(batch["blocked"])
        self.assertFalse(target.exists())

    # 验证预览采用当前配置，而不是缓存的旧规则。
    def test_preview_uses_current_rules_anomaly_policy_and_validation(self):
        source = self.source(["手机号", "成绩"], [["12345", "80"]] + [["13900000001", "90"]] * 11)
        rules = {"手机号":{**recommend("手机号"), "prefix":2, "suffix":2}, "成绩":{**recommend("成绩"), "mode":"drop"}}
        preview = preview_file(source, rules, "skip", SECRET)
        self.assertEqual(preview["summary"]["input_rows"], 10)
        self.assertEqual(preview["summary"]["skipped_rows"], 1)
        self.assertEqual(preview["sheets"][0]["columns"], ["手机号"])
        self.assertEqual(preview["sheets"][0]["rows"], [["+86 13*******01"]] * 9)
        self.assertTrue(preview_file(source, rules, "stop", SECRET)["blocked"])
        rules["手机号"]["mode"] = "keep"
        residual = preview_file(source, rules, secret=SECRET)
        self.assertTrue(residual["blocked"])
        self.assertNotIn("13900000001", json.dumps(residual, ensure_ascii=False))
        rules["手机号"].update(mode="mask", prefix=6, suffix=6)
        with self.assertRaises(ValueError): preview_file(source, rules, secret=SECRET)

    # 验证敏感原文即使落在未识别的其他列，也会阻止导出。
    def test_residual_in_unrecognized_notes_blocks_export(self):
        source = self.source(["手机号", "附言"], [["13900000001", "联系13900000001"]])
        result, target = self.run_file(source)
        self.assertTrue(result["blocked"])
        self.assertFalse(target.exists())
        self.assertEqual(result["summary"]["residual_cells"], 1)
        self.assertNotIn("联系13900000001", json.dumps(result, ensure_ascii=False))

    # 验证带国别码或分隔符的完整手机号仍会被检查。
    def test_formatted_phone_residual_also_blocks_export(self):
        source = self.source(["姓名", "附言"], [["李明轩", "联系+86 139-0000-0001"]])
        result, _ = self.run_file(source)
        self.assertTrue(result["blocked"])

    # 验证单字姓名等短值的遮盖结果重复处理时不变。
    def test_one_character_mask_is_idempotent(self):
        source = self.source(["姓名"], [["李"]])
        _, first = self.run_file(source)
        result, second = self.run_file(first, destination=self.root / "again.csv")
        self.assertFalse(result["blocked"])
        self.assertEqual(read_tables(first), read_tables(second))

    # 验证已识别姓名在其他位置的原文残留会阻止导出。
    def test_known_name_residual_blocks_export(self):
        source = self.source(["姓名", "附言"], [["李明轩", "李明轩需要核对"]])
        result, _ = self.run_file(source)
        self.assertTrue(result["blocked"])

    # 验证选择保留敏感列，也不能跳过导出前的残留检查。
    def test_keep_sensitive_column_cannot_bypass_export_check(self):
        source = self.source(["手机号", "姓名"], [["+86 13962578301", "李明轩"]])
        rules = {"手机号":{**recommend("手机号"), "mode":"keep"}, "姓名":recommend("姓名")}
        result, _ = self.run_file(source, rules)
        self.assertTrue(result["blocked"])

    # 验证跳过异常整行和停止导出两种策略。
    def test_skip_and_stop_policies(self):
        source = self.source(["手机号"], [["12345"], ["13900000001"]])
        masked, _ = self.run_file(source)
        skipped, _ = self.run_file(source, policy="skip")
        stopped, target = self.run_file(source, policy="stop", destination=self.root / "blocked.csv")
        self.assertEqual(masked["summary"]["output_rows"], 2)
        self.assertEqual(skipped["summary"]["output_rows"], 1)
        self.assertTrue(stopped["blocked"])
        self.assertFalse(target.exists())

    # 验证一行的列数与表头不一致时，始终隔离这一行。
    def test_ragged_row_is_always_isolated(self):
        source = self.source(["手机号"], [["13900000001", "unexpected"], ["13900000002"]])
        result, _ = self.run_file(source)
        self.assertEqual(result["summary"]["skipped_rows"], 1)
        self.assertEqual(result["summary"]["output_rows"], 1)

    # 验证必填缺失及重复学号等身份标识能被记录。
    def test_required_empty_and_duplicate_identifier(self):
        source = self.source(["学号", "姓名"], [["S001", "李一"], ["S001", "李二"], ["S003", ""]])
        result, _ = self.run_file(source)
        self.assertEqual(result["summary"]["anomaly_rows"], 2)
        self.assertEqual({i["code"] for i in result["issues"]}, {"duplicate", "missing"})

    # 验证删除敏感列时，成绩等其他列仍正常保留。
    def test_delete_column_and_preserve_scores(self):
        source = self.source(["手机号", "语文成绩"], [["13900000001", "88"]])
        rules = {"手机号":{**recommend("手机号"), "mode":"drop"}, "语文成绩":recommend("语文成绩")}
        result, target = self.run_file(source, rules)
        self.assertFalse(result["blocked"])
        self.assertEqual(read_tables(target)[0], {"columns":["语文成绩"], "rows":[["88"]]})

    # 验证不同中文编码与制表符分隔的表格均可读取。
    def test_utf8_bom_gb18030_and_tsv(self):
        for encoding, extension in (("utf-8-sig", "csv"), ("gb18030", "csv"), ("utf-8", "tsv")):
            with self.subTest(encoding=encoding, extension=extension):
                source = self.source(["手机号"], [["13900000001"]], encoding, extension)
                result, target = self.run_file(source)
                self.assertFalse(result["blocked"])
                self.assertEqual(read_tables(target)[0]["rows"][0][0], "+86 139****0001")

    # 验证疑似公式文字被转义，导出后按普通文本保存。
    def test_formula_injection_is_plain_text(self):
        for formula in ("=1+1", "+SUM(A1)", "@SUM(A1)", "  =1+1", "\t=1+1", "-1+1"):
            source = self.source(["姓名", "成绩"], [["李明轩", formula]])
            result, target = self.run_file(source)
            self.assertFalse(result["blocked"])
            self.assertTrue(read_tables(target)[0]["rows"][0][1].startswith("'"))

    # 验证普通负数不会被误当作危险公式改变。
    def test_plain_negative_number_is_preserved(self):
        source = self.source(["姓名", "统计差值"], [["李明轩", "-3"]])
        result, target = self.run_file(source)
        self.assertFalse(result["blocked"])
        self.assertEqual(read_tables(target)[0]["rows"][0][1], "-3")

    # 验证删列后，问题报告仍指向原表的正确列号。
    def test_residual_location_uses_original_column_after_deletion(self):
        source = self.source(["姓名", "手机号", "附言"], [["李明轩", "13900000001", "联系13900000001"]])
        rules = {"姓名":{**recommend("姓名"), "mode":"drop"}, "手机号":recommend("手机号"), "附言":recommend("附言")}
        result, _ = self.run_file(source, rules)
        self.assertEqual([i["column"] for i in result["issues"] if i["code"] == "residual"], [3])

    # 验证源文件内容未改，并拒绝把输出直接写回源路径。
    def test_source_hash_is_unchanged_and_overwrite_rejected(self):
        source = self.source(["手机号"], [["13900000001"]])
        before = hashlib.sha256(source.read_bytes()).digest()
        self.run_file(source)
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).digest())
        with self.assertRaises(ValueError): self.run_file(source, destination=source)

    # 验证报告不包含敏感原文。
    def test_report_never_includes_sensitive_originals(self):
        source = self.source(["姓名", "手机号"], [["李明轩", "bad-private-phone"]])
        result, _ = self.run_file(source)
        text = json.dumps(result["issues"], ensure_ascii=False)
        self.assertNotIn("bad-private-phone", text)
        self.assertNotIn("李明轩", text)

    # 验证空表头或重复列名会被拒绝导入。
    def test_empty_and_duplicate_headers_rejected(self):
        for headers in (["姓名", "姓名"], ["姓名", ""]):
            with self.assertRaises(ValueError): read_tables(self.source(headers, [["a", "b"]]))

    # 验证隐藏表也参与处理，原始批注不带出，公式文字按规则处理。
    def test_xlsx_hidden_sheets_comments_and_formulas(self):
        source = self.root / "input.xlsx"
        book = openpyxl.Workbook(); sheet = book.active; sheet.title = "姓名不能出现在导出表名"
        sheet.append(["手机号", "成绩"]); sheet.append(["13900000001", "=1+1"])
        sheet["A2"].comment = Comment("原文13900000001", "作者")
        hidden = book.create_sheet("隐藏数据"); hidden.sheet_state = "hidden"; hidden.append(["邮箱"]); hidden.append(["student@example.test"])
        book.save(source)
        result, target = self.run_file(source)
        self.assertFalse(result["blocked"])
        actual = openpyxl.load_workbook(target)
        self.addCleanup(actual.close)
        self.assertEqual(actual.sheetnames, ["数据表1", "数据表2"])
        self.assertIsNone(actual.worksheets[0]["A2"].comment)
        self.assertNotEqual(actual.worksheets[0]["B2"].data_type, "f")
        self.assertEqual(actual.worksheets[1]["A2"].value, "s***@***")

    # 验证项目两种正常学生表共 200 行可在禁止网络连接时处理。
    def test_sample_100_rows_both_formats_no_network(self):
        with patch("socket.socket.connect", side_effect=AssertionError("不能联网")):
            for extension in ("csv", "xlsx"):
                source = ROOT / f"sample_data/students_100.{extension}"
                table = read_tables(source)[0]
                self.assertEqual(len(table["columns"]), 16)
                self.assertNotIn("备注", table["columns"])
                for row in table["rows"]:
                    self.assertRegex(row[6], r"^\+86 1[3-9]\d{9}$")
                    self.assertRegex(row[13], r"^\+86 1[3-9]\d{9}$")
                    self.assertRegex(row[7], r"^\d{17}[0-9X]$")
                    self.assertFalse(any(word in str(row) for word in ("测试学生", "仅供", "虚构", "演示")))
                result, target = self.run_file(source)
                self.assertFalse(result["blocked"])
                self.assertEqual(result["summary"]["input_rows"], 100)
                self.assertEqual(result["summary"]["anomaly_rows"], 0)
                self.assertEqual(result["summary"]["masked_cells"], 900)
                processed = read_tables(target)[0]["rows"]
                self.assertEqual(len(processed), 100)
                self.assertTrue(all(row[6].startswith("+86 ") and row[13].startswith("+86 ") for row in processed))


if __name__ == "__main__":
    unittest.main(verbosity=2)
