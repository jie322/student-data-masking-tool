"""单元格级脱敏核心算法模块：提供敏感字段格式清洗、合规校验、幂等检测及动态掩码遮盖功能。"""

import datetime as dt
import re

from .constants import EMAIL, HIDDEN, INVALID, TOKEN


def normalize_phone(value):
    """清洗电话号码文本：剥除空格、括号、连字符等格式噪声及国别码 (+86 / 0086)，提取标准化 11 位国内号码。"""
    text = re.sub(r"[\s()\-]", "", value)
    if text.startswith("+86"):
        text = text[3:]
    elif text.startswith("0086"):
        text = text[4:]
    return text


def valid_identity(text):
    """按照 GB 11643-1999 标准校验 18 位公民身份号码：结构格式、出生日期有效性及 ISO 7064:1983.MOD 11-2 校验码。"""
    if not re.fullmatch(r"\d{17}[0-9Xx]", text):
        return False
    # 提取第 7~14 位出生日期子串，校验其日历有效性（防止伪造无效月份或闰年错误）
    birth = text[6:14]
    try:
        dt.datetime.strptime(birth, "%Y%m%d")
    except ValueError:
        return False
    if len(text) == 18:
        # 前 17 位乘固定加权因子后对模 11 取余，验证末位校验码（含数字及校验字符 X）
        weights = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        return "10X98765432"[sum(int(n) * w for n, w in zip(text[:17], weights)) % 11] == text[-1].upper()
    return True


def normalized(value, kind):
    """针对不同字段类别执行归一化格式预处理（电话标准化、邮箱小写化、身份证大写化）。"""
    text = str(value).strip()
    return normalize_phone(text) if kind == "phone" else text.lower() if kind == "email" else text.upper() if kind == "identity" else text


def already_masked(text, rule):
    """检测单元格文本是否已符合当前脱敏掩码规则，保障处理幂等性，防止多重重复遮盖。"""
    kind, prefix, suffix = rule["type"], rule.get("prefix", 0), rule.get("suffix", 0)
    if kind == "email":
        local, sep, domain = text.partition("@")
        return bool(sep and re.fullmatch(r"[^*\s@]{0,%d}\*+" % prefix, local) and (domain == "***" or (rule.get("keep_domain") and EMAIL.fullmatch("a@" + domain))))
    if kind in ("phone", "identity"):
        if kind == "phone":
            text = normalize_phone(text)
        lengths = (11,) if kind == "phone" else (18,)
        return any(len(text) == length and re.fullmatch(r"[0-9]{%d}\*{%d}[0-9Xx]{%d}" % (prefix, length - prefix - suffix, suffix), text) for length in lengths if length > prefix + suffix)
    return bool("*" in text and re.fullmatch(r"[^*]{0,%d}\*+[^*]{0,%d}" % (prefix, suffix), text))


def mask_value(value, rule, secret=""):
    """执行单个单元格数据的脱敏处理，返回 (处理后值, 异常代码, 是否脱敏标记)。

    Args:
        value: 原始单元格数据。
        rule: 当前列适用的脱敏规则字典。
        secret: 保留兼容参数（当前基于掩码策略无状态执行，不依赖对称密钥）。

    Returns:
        tuple: (masked_value, issue_code, did_mask_bool) 三元组。
    """
    kind, mode = rule["type"], rule["mode"]
    # 优先检测空值：若列配置开启必填校验 (required)，则触发 "missing" 缺失异常
    if value is None or str(value).strip() == "":
        return "", "missing" if rule.get("required") else None, False
    text = str(value).strip()
    # 原值保留模式：不修改单元格内容，后续在 safety.py 阶段进行全表残留安全审计
    if mode == "keep":
        return value, None, False
    if mode == "drop":
        return None, None, True
    # 已经处于系统占位符状态的内容保持原样，防止二次处理引发格式失真
    if text in (HIDDEN, INVALID):
        return text, None, False
    if mode == "full":
        return HIDDEN, None, True
    # 历史不可逆代号无法基于新规则重新计算，统一转换为完全隐藏占位符并记录告警
    if TOKEN.fullmatch(text):
        return HIDDEN, "remasked", True
    # 若内容已具备合规掩码格式则直接复用；手机号统一补齐国际区号 +86 规范表达
    if "*" in text and already_masked(text, rule):
        masked = "+86 " + normalize_phone(text) if kind == "phone" else text
        return (masked, None, masked != text) if mode == "mask" else (HIDDEN, "remasked", True)
    if "*" in text:
        return INVALID, "format", True
    # 格式规范化并执行严格合规校验；格式不合规时替换为异常占位符并返回 format 告警
    canonical = normalized(value, kind)
    valid = {"phone": lambda: bool(re.fullmatch(r"1[3-9]\d{9}", canonical)), "email": lambda: bool(EMAIL.fullmatch(canonical)), "identity": lambda: valid_identity(canonical)}.get(kind, lambda: True)()
    if not valid:
        return INVALID, "format", True
    prefix, suffix = rule.get("prefix", 0), rule.get("suffix", 0)
    # 电子邮箱按 '@' 切分账户名与域名：账户名至少遮盖1位，域名依据配置决定是否保留
    if kind == "email":
        local, domain = canonical.split("@")
        return local[:min(prefix, max(0, len(local) - 1))] + "***@" + (domain if rule.get("keep_domain") else "***"), None, True
    # 实施动态星号掩码切片：无论原始长度如何，至少遮盖1个字符，防止单字短文本完全泄露
    prefix = min(prefix, max(0, len(canonical) - 1))
    suffix = min(suffix, max(0, len(canonical) - prefix - 1))
    # 拼接掩码文本：保留前缀 + 动态长度星号 + 保留后缀；手机号前置补齐 +86 规范
    masked = canonical[:prefix] + "*" * (len(canonical) - prefix - suffix) + (canonical[-suffix:] if suffix else "")
    return ("+86 " + masked if kind == "phone" else masked), None, True
