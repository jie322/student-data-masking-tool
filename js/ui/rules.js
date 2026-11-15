/**
 * 脱敏规则配置表单视图渲染与同步模块 (Rule Specification UI Component)。
 * 负责全局列级规则网格渲染、表头合并同名列复用、字段类型变更时的默认掩码位数重置及输入有效性边界管控。
 */
import { files, rules, state } from "../state.js";
import { types, modes } from "../config.js";
import { $, element } from "./dom.js";
import { invalidate, setBusy } from "./feedback.js";

/**
 * 封装标准化下拉单选选择框组件。
 * @param {Object} options 键值对选项映射表。
 * @param {string} selected 当前选中键名。
 * @param {string} label 无障碍辅助阅读文本。
 * @param {Function} onChange 值变更回调。
 * @returns {HTMLSelectElement}
 */
export function selectControl(options, selected, label, onChange) {
  const select = element("select");
  select.setAttribute("aria-label", label);
  for (const [value, title] of Object.entries(options)) {
    const option = element("option", title);
    option.value = value;
    select.append(option);
  }
  select.value = selected;
  select.addEventListener("change", () => {
    onChange(select.value);
    invalidate();
  });
  return select;
}

/**
 * 封装带标签包装的复选框控制组件。
 * @param {string} label 复选框旁展示文本。
 * @param {boolean} checked 是否勾选。
 * @param {Function} onChange 勾选状态变更回调。
 * @returns {HTMLLabelElement}
 */
export function checkboxControl(label, checked, onChange) {
  const wrap = element("label", undefined, "check-label");
  const input = element("input");
  input.type = "checkbox";
  input.checked = checked;
  input.addEventListener("change", () => {
    onChange(input.checked);
    invalidate();
  });
  wrap.append(input, document.createTextNode(label));
  return wrap;
}

/**
 * 重新渲染规则配置数据表（按列名聚合呈现）。
 */
export function renderRules() {
  $("rulesBody").replaceChildren();

  for (const [column, rule] of rules) {
    const tr = element("tr");
    const typeCell = element("td");
    const modeCell = element("td");
    const digits = element("td");
    const extra = element("td");

    // 字段语义类别下拉选择框：动态关联重置推荐位数
    typeCell.append(
      selectControl(types, rule.type, `${column}的字段类型`, (value) => {
        const defaults = { phone: [3, 4], identity: [3, 2], email: [1, 0], name: [1, 0], identifier: [4, 0] };
        rule.type = value;
        [rule.prefix, rule.suffix] = defaults[value] || [0, 0];
        rule.mode = value === "other" ? "keep" : ["address", "text"].includes(value) ? "full" : "mask";
        renderRules();
      })
    );

    // 脱敏操作模式下拉选择框
    modeCell.append(
      selectControl(modes, rule.mode, `${column}的处理方式`, (value) => {
        rule.mode = value;
        renderRules();
      })
    );

    // 前后缀保留字符数数值输入框：动态绑定禁用态（非掩码模式或邮箱后缀禁用）
    for (const key of ["prefix", "suffix"]) {
      if (key === "suffix") digits.append(element("span", "/", "slash"));
      const input = element("input");
      input.type = "number";
      input.min = "0";
      input.max = "6";
      input.value = rule[key];
      input.setAttribute("aria-label", `${column}保留${key === "prefix" ? "前" : "后"}位数`);
      input.dataset.inactive = String(rule.mode !== "mask" || (rule.type === "email" && key === "suffix"));
      input.disabled = input.dataset.inactive === "true";
      input.addEventListener("input", () => {
        rule[key] = input.value === "" ? null : Number(input.value);
        invalidate();
      });
      digits.append(input);
    }

    // 必填与域名保留特殊开关
    extra.append(checkboxControl("必填校验", rule.required, (value) => { rule.required = value; }));
    if (rule.type === "email") {
      extra.append(checkboxControl("保留域名", rule.keep_domain, (value) => { rule.keep_domain = value; }));
    }

    tr.append(element("td", column), typeCell, modeCell, digits, extra);
    $("rulesBody").append(tr);
  }

  if (!rules.size) {
    const tr = element("tr");
    const td = element("td", "导入表格后显示中文字段配置。", "empty");
    td.colSpan = 5;
    tr.append(td);
    $("rulesBody").append(tr);
  }
  setBusy(state.busy);
}

/**
 * 汇总当前所有有效文件表头列名，重建规则字典（默认保留用户已有调优参数，支持重置回退）。
 * @param {boolean} [reset=false] 是否强制放弃自定义调整并重置为系统推荐值。
 */
export function rebuildRules(reset = false) {
  const previous = new Map(rules);
  rules.clear();
  for (const file of files) {
    if (file.meta) {
      for (const sheet of file.meta.sheets) {
        for (const column of sheet.columns) {
          if (!rules.has(column)) {
            rules.set(column, !reset && previous.has(column) ? previous.get(column) : { ...sheet.rules[column] });
          }
        }
      }
    }
  }
  renderRules();
}
