# 旧版“原文与代号对照表”模块；当前学生界面使用星号遮盖，不生成可恢复映射。
import json
import random
import secrets


# 表示映射文件格式不符合要求，便于上层捕获并提示。
class MappingError(ValueError):
    pass


# 生成随机种子；同一映射内用它保持后续编号分配可重复。
def new_seed():
    return secrets.token_hex(8)


# 按前缀和位数生成代号，例如前缀加补零的数字编号。
def format_token(prefix, number, width):
    return f"{prefix}-{number:0{width}d}"


# 为新原文分配尚未占用的编号，保持已有原文与编号的关系不变。
def assign_tokens(existing_values, new_values, seed):
    """existing_values: {value: number}, tokens already assigned for this
    entity. new_values: values not in there yet (this function filters out
    anything already present anyway). Returns the FULL value -> number
    dictionary (existing + new).

    Determinism: `to_assign` is sorted before shuffling, so the result
    depends only on the set of new values and on `seed`, never on the row
    order in the file (design.md §3: "a run stays repeatable"). Numbers are
    handed out in shuffled order rather than order of appearance --
    design.md §3: otherwise the token number itself leaks information
    (who came first, who is biggest).
    """
    values = dict(existing_values or {})
    used_numbers = set(values.values())
    to_assign = sorted({v for v in new_values if v not in values})
    if not to_assign:
        return values

    rng = random.Random(seed)
    candidates = []
    n = 1
    while len(candidates) < len(to_assign):
        if n not in used_numbers:
            candidates.append(n)
        n += 1
    rng.shuffle(candidates)

    for value, number in zip(to_assign, candidates):
        values[value] = number
    return values


# 创建一份空映射，包含版本、随机种子和信息类别列表。
def new_mapping():
    return {"version": 1, "seed": new_seed(), "entities": {}}


# 给某一类信息追加新值，保留这类信息此前已经分配的编号。
def update_entity(mapping, entity_name, prefix, width, new_values):
    """Add new values to an entity, creating it if it does not exist yet.
    Mutates and returns `mapping` so calls can be chained."""
    entity = mapping["entities"].setdefault(
        entity_name, {"prefix": prefix, "width": width, "values": {}}
    )
    entity["prefix"] = prefix
    entity["width"] = width
    entity["values"] = assign_tokens(entity["values"], new_values, mapping["seed"])
    return mapping


# 查找某个原值对应的代号；映射中不存在时返回 None。
def token_for(mapping, entity_name, value):
    entity = mapping["entities"].get(entity_name)
    if not entity or value not in entity["values"]:
        return None
    return format_token(entity["prefix"], entity["values"][value], entity["width"])


# 合并配置涉及的多份文件和多列，同一类原值共享一套代号。
def build_mapping(config, values_by_column, existing_mapping=None):
    """config: an AnonConfig dict (`config.py`) -- entities: {name:
    {prefix, width, columns: [{file_pattern, sheet_name, column_name}]}}.
    values_by_column: {file: {sheet: {column: [values...]}}} -- from the
    streaming projection (`engine.extract_unique_values`), collected for
    every file the config refers to.
    existing_mapping: a dictionary to append to (design.md §4), or None to
    create a fresh one with a new seed.

    One entity can span columns from several files/sheets (§5) -- their
    values are merged into a single set before tokens are handed out, and
    that is exactly where cross-file referential integrity comes from.
    """
    mapping = existing_mapping or new_mapping()
    for entity_name, entity_cfg in config["entities"].items():
        all_values = set()
        for col in entity_cfg["columns"]:
            file_values = values_by_column.get(col["file_pattern"], {})
            sheet_values = file_values.get(col["sheet_name"], {})
            all_values.update(sheet_values.get(col["column_name"], []))
        update_entity(mapping, entity_name, entity_cfg["prefix"], entity_cfg["width"], all_values)
    return mapping


# 把保存的 JSON 文字读成映射，并检查必要结构。
def mapping_from_json(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise MappingError(f"invalid JSON: {e}")
    if "entities" not in data or "seed" not in data:
        raise MappingError("dictionary has no 'entities' or 'seed' key -- does not look like mapping.json")
    return data


# 把映射转成 JSON 文字供保存；映射含原文，不能混进脱敏结果包。
def mapping_to_json(mapping):
    return json.dumps(mapping, ensure_ascii=False, indent=2)
