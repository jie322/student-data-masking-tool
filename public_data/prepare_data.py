# 从已保存的公开资料生成中文表格和对照结果；数据来源登记在 SOURCES，不执行网络下载。
"""核验公开下载原件，整理中文导入表，并调用项目引擎生成脱敏对照。"""
import csv
import hashlib
import html
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(PROJECT / "py"))
from student import process_file, read_tables, recommend

# 此处限制公开资料的文件大小，与页面的单文件导入上限分开计算。
PER_FILE = 20_000_000
TOTAL = 200_000_000
ORIGINALS = ROOT / "originals"
IMPORTS = ROOT / "imports"
OUTPUTS = ROOT / "outputs"
SOURCES = [
    {"id":"hk_primary", "name":"香港小学公开资料（2026，简体中文）", "file":"hk_primary_2026_sc.csv", "url":"https://www.chsc.hk/datagovhk/psp_2026_sc.csv", "page":"https://data.gov.hk/sc-data/dataset/chsc-chsc-primary-school-profiles/resource/e224100f-daee-43ac-bcf4-89b8a75928d7", "license":"DATA.GOV.HK 使用条款及家庭与学校合作事宜委员会的知识产权声明", "kind":"公开学校机构及负责人办公联系资料，不是学生个人档案"},
    {"id":"sg_schools", "name":"新加坡教育部学校公开资料", "file":"sg_schools_api.json", "url":"https://data.gov.sg/api/action/datastore_search?resource_id=d_688b934f82c1059ed0a6993d2a829089&limit=1000", "page":"https://data.gov.sg/datasets/d_688b934f82c1059ed0a6993d2a829089/view", "license":"Singapore Open Data Licence（https://data.gov.sg/open-data-licence）", "kind":"公开学校机构及负责人办公联系资料，原件为官方 API 返回的 JSON"},
    {"id":"uci_320", "name":"UCI 葡萄牙中学生成绩", "file":"uci_student_performance.zip", "url":"https://archive.ics.uci.edu/static/public/320/student+performance.zip", "page":"https://archive.ics.uci.edu/dataset/320/student+performance", "license":"CC BY 4.0；Cortez, P. (2008), DOI: 10.24432/C5TG7T", "kind":"真实学校报告与问卷数据，已匿名化；不含姓名、电话、邮箱和身份证号"},
    {"id":"uci_697", "name":"UCI 大学生学籍与学业结果", "file":"uci_student_dropout.zip", "url":"https://archive.ics.uci.edu/static/public/697/predict+students+dropout+and+academic+success.zip", "page":"https://archive.ics.uci.edu/dataset/697/predict+students+dropout+and+academic+success", "license":"CC BY 4.0；Realinho et al.，DOI: 10.24432/C5MC89", "kind":"真实高等教育机构的学生数据，已匿名化；不含完整身份或联系信息"},
    {"id":"oulad", "name":"OULAD 学生学习行为研究子集", "file":"oulad_subset.csv", "url":"https://zenodo.org/records/4264397/files/OULAD_subset_Casalino_et_al.csv?download=1", "page":"https://zenodo.org/records/4264397", "license":"CC BY 4.0；Casalino, Castellano & Vessio，DOI: 10.5281/zenodo.4264397", "kind":"来自真实开放大学学习记录的研究者整理子集，分类值已数字编码；没有直接身份信息"},
]


# 将生成内容写入本目录；写入前检查目标位置、单文件大小和目录总量。
def save(path, content):
    path = path.resolve()
    assert path.is_relative_to(ROOT)
    if len(content) > PER_FILE:
        raise ValueError("单个文件超过 20 MB")
    existing = sum(p.stat().st_size for p in ROOT.rglob("*") if p.is_file() and p.resolve() != path)
    if existing + len(content) > TOTAL:
        raise ValueError("资料总量超过 200 MB")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


# 按给定表头和行写 CSV，使用带 BOM 的 UTF-8，方便表格软件识别中文。
def write_csv(path, columns, rows):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(columns)
    writer.writerows(rows)
    save(path, buffer.getvalue().encode("utf-8-sig"))


# 把原件字节按 UTF-8 读取为二维数据；delimiter 指定逗号或分号分隔。
def parse_csv(content, delimiter=","):
    return list(csv.reader(io.StringIO(content.decode("utf-8-sig")), delimiter=delimiter))


# 更换表头名称和分隔符，保留原数据值，并返回导入文件的行列数。
def translate_csv(name, content, labels, delimiter=","):
    rows = parse_csv(content, delimiter)
    if len(rows[0]) != len(labels):
        raise ValueError("源数据列数改变，请核对字段翻译")
    target = IMPORTS / name
    write_csv(target, labels, rows[1:])
    return {"path":str(target.relative_to(ROOT)), "rows":len(rows)-1, "columns":len(labels)}


# 核验原件、整理六份导入表，再处理学校联系方式并保存来源摘要和前后对照。
def main():
    for folder in (ORIGINALS, IMPORTS, OUTPUTS):
        folder.mkdir(exist_ok=True)
    for name in [s["file"] for s in SOURCES] + ["zenodo_metadata.json"]:
        final = ORIGINALS / name
        part = ORIGINALS / (name + ".part")
        if part.exists():
            if part.stat().st_size > PER_FILE:
                raise ValueError("下载文件超过大小限制")
            part.replace(final)
        if not final.exists():
            raise FileNotFoundError("缺少已下载原件：" + name)
    # 内容与格式核验，拒绝把错误网页当作数据文件。
    hk = list(csv.DictReader(io.StringIO((ORIGINALS / SOURCES[0]["file"]).read_text(encoding="utf-8-sig"))))
    assert hk and {"学校名称", "校长姓名", "学校电话", "学校电邮"}.issubset(hk[0])
    sg_response = json.loads((ORIGINALS / SOURCES[1]["file"]).read_text(encoding="utf-8"))
    assert sg_response["success"] and len(sg_response["result"]["records"]) == sg_response["result"]["total"]
    assert hashlib.md5((ORIGINALS / "oulad_subset.csv").read_bytes()).hexdigest() == "a6e67e3b8440a42e88bd0ef3c0ab1325"
    zenodo_metadata = json.loads((ORIGINALS / "zenodo_metadata.json").read_text(encoding="utf-8"))
    assert zenodo_metadata["metadata"]["license"]["id"] == "cc-by-4.0"

    contact_headers = ["学校名称", "校长姓名", "办公电话", "邮箱", "地址", "传真号码", "地区", "学校网址"]
    hk_fields = ["学校名称", "校长姓名", "学校电话", "学校电邮", "学校地址", "学校传真", "区域", "学校网址"]
    sg_fields = ["school_name", "principal_name", "telephone_no", "email_address", "address", "fax_no", "dgp_code", "url_address"]

    def contact_rows(records, fields):
        # 官方 API 的 na / 缺失占位符转为空值；原始响应和完整原件均保留。
        return [["" if str(r.get(f, "")).strip().lower() in ("na", "n/a", "null", "none", "-", "--") else r.get(f, "") for f in fields] for r in records]

    write_csv(IMPORTS / "01_香港学校公开联系方式.csv", contact_headers, contact_rows(hk, hk_fields))
    sg = sg_response["result"]["records"]
    write_csv(IMPORTS / "02_新加坡学校公开联系方式.csv", contact_headers, contact_rows(sg, sg_fields))
    SOURCES[0]["imports"] = [{"path":"imports/01_香港学校公开联系方式.csv", "rows":len(hk), "columns":8}]
    SOURCES[1]["imports"] = [{"path":"imports/02_新加坡学校公开联系方式.csv", "rows":len(sg), "columns":8}]

    student_labels = ["学校代码", "性别", "年龄", "居住区域类型", "家庭规模", "父母同居状态", "母亲教育程度", "父亲教育程度", "母亲职业类别", "父亲职业类别", "择校原因", "监护人关系", "通学时长分组", "每周学习时长分组", "既往不及格次数", "学校学习支持", "家庭学习支持", "付费补习", "课外活动", "学前教育", "升学意愿", "家庭互联网", "恋爱关系", "家庭关系评分", "空闲时间评分", "外出频率评分", "工作日饮酒评分", "周末饮酒评分", "健康评分", "缺勤次数", "第一阶段成绩", "第二阶段成绩", "最终成绩"]
    with zipfile.ZipFile(ORIGINALS / "uci_student_performance.zip") as outer:
        nested = outer.read("student.zip")
    assert len(nested) <= PER_FILE
    with zipfile.ZipFile(io.BytesIO(nested)) as archive:
        SOURCES[2]["imports"] = []
        for original, translated in (("student-mat.csv", "03_学生数学成绩.csv"), ("student-por.csv", "04_学生葡语成绩.csv")):
            content = archive.read(original)
            save(ORIGINALS / "uci_320" / original, content)
            SOURCES[2]["imports"].append(translate_csv(translated, content, student_labels, ";"))
        save(ORIGINALS / "uci_320" / "student.txt", archive.read("student.txt"))
    dropout_labels = ["婚姻状态", "入学申请方式", "志愿顺序", "课程代码", "日间夜间就读", "入学前学历", "入学前成绩", "国籍代码", "母亲学历代码", "父亲学历代码", "母亲职业代码", "父亲职业代码", "入学成绩", "是否离家就读", "特殊教育需要", "欠费状态", "学费是否缴清", "性别", "奖学金状态", "入学年龄", "国际学生状态", "第一学期学分认可课程数", "第一学期注册课程数", "第一学期考核次数", "第一学期通过课程数", "第一学期成绩", "第一学期未考核课程数", "第二学期学分认可课程数", "第二学期注册课程数", "第二学期考核次数", "第二学期通过课程数", "第二学期成绩", "第二学期未考核课程数", "失业率", "通胀率", "国内生产总值指标", "学业结果"]
    with zipfile.ZipFile(ORIGINALS / "uci_student_dropout.zip") as archive:
        content = archive.read("data.csv")
    save(ORIGINALS / "uci_697" / "data.csv", content)
    SOURCES[3]["imports"] = [translate_csv("05_学生学籍与学业结果.csv", content, dropout_labels, ";")]
    oulad_labels = ["课程代码", "开课学期代码", "性别代码", "最高学历代码", "地区贫困程度分组代码", "年龄分组代码", "既往修读次数", "已修学分", "残障状态代码", "资源点击数", "主页点击数", "论坛点击数", "词汇表点击数", "课程内容点击数", "子页面点击数", "链接点击数", "协作活动点击数", "测验点击数", "平均成绩", "交互次数", "学业结果代码"]
    SOURCES[4]["imports"] = [translate_csv("06_学生学习行为.csv", (ORIGINALS / "oulad_subset.csv").read_bytes(), oulad_labels)]

    results = []
    # 境外办公电话按敏感文本遮盖；学校名称和负责人列采用这里明确设置的规则。
    contact_rules = {c:recommend(c) for c in contact_headers}
    contact_rules["学校名称"] = {**recommend("学号"), "mode":"full", "required":False}
    contact_rules["校长姓名"] = recommend("姓名")
    contact_rules["校长姓名"]["required"] = False
    contact_rules["办公电话"] = {**recommend("补充信息"), "mode":"mask", "prefix":2, "suffix":2}
    contact_rules["传真号码"] = {**recommend("补充信息"), "mode":"full"}
    comparisons = []
    for index, source in enumerate(SOURCES[:2], 1):
        path = ROOT / source["imports"][0]["path"]
        target = OUTPUTS / (path.stem + "_已脱敏.csv")
        result = process_file(path, target, contact_rules, "mask", "public-contact-verification-2026")
        if result["blocked"]:
            raise ValueError("公开联系资料残留校验未通过，暂不提供导出结果")
        results.append({"数据集":source["name"], "处理摘要":result["summary"], "位置记录":result["issues"]})
        before = read_tables(path)[0]["rows"]
        after = read_tables(target)[0]["rows"]
        for a, b in list(zip(before, after))[:3]:
            for position in (0, 1, 2, 3, 4):
                comparisons.append([source["name"], a[0], contact_headers[position], a[position], b[position]])
    write_csv(ROOT / "脱敏前后对照.csv", ["数据集", "学校", "字段", "原始值", "脱敏结果"], comparisons)
    save(OUTPUTS / "处理报告.json", json.dumps(results, ensure_ascii=False, indent=2).encode("utf-8"))
    save(ROOT / "联系方式规则.json", json.dumps(contact_rules, ensure_ascii=False, indent=2).encode("utf-8"))
    # 来源记录中的日期沿用原始下载日期，大小和摘要取自当前保存的原件。
    for source in SOURCES:
        path = ORIGINALS / source["file"]
        source.update({"downloaded_on":"2026-10-31", "bytes":path.stat().st_size, "sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    save(ROOT / "sources.json", json.dumps(SOURCES, ensure_ascii=False, indent=2).encode("utf-8"))

    body = []
    for source in SOURCES[:2]:
        body.append('<section><h2>' + html.escape(source["name"]) + '</h2><p>来源为学校公开办公联系资料，不是学生个人档案。</p><table><thead><tr><th>字段</th><th>原始值</th><th>脱敏结果</th></tr></thead><tbody>')
        sample = [r for r in comparisons if r[0] == source["name"]][:5]
        for row in sample:
            body.append('<tr><td>' + html.escape(str(row[2])) + '</td><td>' + html.escape(str(row[3])) + '</td><td class="masked">' + html.escape(str(row[4])) + '</td></tr>')
        body.append('</tbody></table><p><a href="' + html.escape(source["page"], quote=True) + '">查看公开发布来源</a></p></section>')
    page = '<!DOCTYPE html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>公开数据脱敏效果对照</title><style>body{font:15px/1.7 "Microsoft YaHei",sans-serif;color:#20364b;background:#f3f6f8;max-width:1100px;margin:35px auto;padding:0 22px}h1{font-size:27px}h2{font-size:19px}p{color:#607386}section{background:white;border:1px solid #dce5eb;padding:22px 26px;margin:22px 0;border-radius:6px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;border-bottom:1px solid #e6edf1;padding:12px;overflow-wrap:anywhere}th{background:#edf3f6}.masked{color:#087f83;font-weight:bold}a{color:#087f83}</style><h1>公开数据脱敏效果对照</h1><p>下列结果由项目的学生信息表处理引擎生成。学校办公电话保留来源格式，使用“敏感文本，保留前 2 后 2 位”处理；邮箱隐藏其余用户名与域名，姓名保留首字符，地址全部隐藏。</p>' + ''.join(body) + '<section><h2>如何在工具中复现</h2><p>导入 imports 目录中的学校联系方式 CSV；将校长姓名设为“姓名 / 部分遮盖”，办公电话设为“敏感文本 / 部分遮盖 / 前2后2”，传真设为“敏感文本 / 全部隐藏”，邮箱和地址使用对应规则，再点击“开始批量脱敏”。境外办公电话不应改写为 +86，也不应套用中国大陆手机号格式校验。</p><p><a href="../index.html">打开脱敏工具</a>　<a href="imports/01_香港学校公开联系方式.csv" download>下载中文联系资料表</a>　<a href="outputs/01_香港学校公开联系方式_已脱敏.csv" download>下载对应脱敏结果</a></p></section></html>'
    page = page.replace("将校长姓名设为", "将学校名称设为「学号 / 身份标识 / 全部隐藏」，将校长姓名设为")
    save(ROOT / "脱敏效果对照.html", page.encode("utf-8"))
    inventory = [(p.relative_to(ROOT).as_posix(), p.stat().st_size) for p in ROOT.rglob("*") if p.is_file()]
    assert all(size <= PER_FILE for _, size in inventory)
    assert sum(size for _, size in inventory) <= TOTAL
    print(json.dumps({"导入表":[t for s in SOURCES for t in s["imports"]], "文件数":len(inventory), "总字节数":sum(s for _, s in inventory), "最大文件字节数":max(s for _, s in inventory), "联系方式脱敏摘要":[r["处理摘要"] for r in results]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
