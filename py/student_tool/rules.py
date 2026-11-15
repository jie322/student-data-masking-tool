"""列级脱敏规则管理模块：负责字段类型推断、默认脱敏策略生成与规则合规性校验。"""

from .constants import ALIASES, MODES, TYPES


def recommend(column):
    """根据表头名称匹配预设别名字典，推荐适用的字段类型与默认脱敏规则。

    Args:
        column: 表头字段名称（如“手机号码”、“身份证号”等）。

    Returns:
        dict: 包含字段类别、脱敏模式、前后缀保留长度及校验开关的推荐规则配置字典。
    """
    # 归一化表头文本：剔除首尾空白、转为小写并过滤内联空格，提升别名字典的匹配容错率
    normalized = str(column).strip().lower().replace(" ", "")
    # 检索别名字典知识库；若未命中则归为普通字段 (other)，交由用户后续人工确认
    kind = next((k for k, names in ALIASES.items() if normalized in names), "other")
    # 确定默认处理模式：普通字段保留，地址和长文本默认全遮盖，其他敏感字段默认掩码遮盖
    mode = {"other": "keep", "address": "full", "text": "full"}.get(kind, "mask")
    # 配置前后缀保留位数 (prefix, suffix)：如手机号保留前3后4、身份证保留前3后2
    prefix, suffix = {"phone": (3, 4), "identity": (3, 2), "name": (1, 0), "email": (1, 0), "identifier": (4, 0)}.get(kind, (0, 0))
    return {"type": kind, "mode": mode, "prefix": prefix, "suffix": suffix, "keep_domain": False, "required": kind in ("identifier", "name")}


def validate_rules(rules):
    """全量校验列规则字典的合法性与安全性，拦截非法类型、无效位数及高隐私泄露风险配置。

    Args:
        rules: 映射“列名 -> 规则字典”的配置映射表。

    Raises:
        ValueError: 规则结构不合法、数值越界或安全边界被打破时抛出异常。
    """
    if not isinstance(rules, dict):
        raise ValueError("规则必须按列配置。")
    for rule in rules.values():
        if not isinstance(rule, dict) or rule.get("type") not in TYPES or rule.get("mode") not in MODES:
            raise ValueError("字段类型或处理方式无效。")
        prefix, suffix = rule.get("prefix", 0), rule.get("suffix", 0)
        # 保留位数必须是严格整数类型且位于合规闭区间 [0, 6]，杜绝负数、小数或布尔值注入
        if type(prefix) is not int or type(suffix) is not int or not (0 <= prefix <= 6 and 0 <= suffix <= 6):
            raise ValueError("保留位数必须是 0 至 6 的整数。")
        if rule["type"] == "other" and rule["mode"] not in ("keep", "full", "drop"):
            raise ValueError("请先为该列选择敏感字段类型，再配置部分遮盖。")
        if rule["mode"] == "mask":
            # 依据字段固有长度定义保留字符安全上界，防止用户过度保留导致隐私暴露
            limits = {"phone": 10, "identity": 14, "identifier": 6, "text": 6, "address": 6, "name": 1, "email": 2}
            if prefix + suffix > limits.get(rule["type"], 0):
                raise ValueError("保留位数过多，可能暴露完整字段，请减少保留位数或选择全部隐藏。")
        if type(rule.get("keep_domain", False)) is not bool or type(rule.get("required", False)) is not bool:
            raise ValueError("必填或邮箱域名开关无效。")
