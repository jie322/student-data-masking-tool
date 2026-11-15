/**
 * DOM 操作与虚拟视图构建工具模块 (DOM Helper & UI Component Builder)。
 * 封装安全的 DOM 节点创建、文本防 XSS 转义注入与规范化数据表格渲染函数。
 */

/**
 * 依据元素 ID 快速定位 DOM 节点的辅助函数。
 * @param {string} id 页面元素 ID。
 * @returns {HTMLElement|null}
 */
export const $ = (id) => document.getElementById(id);

/**
 * 创建具有指定标签、文本内容与类名的 DOM 元素。
 * 使用 textContent 进行纯文本赋值，防范潜在的 DOM-XSS 跨站脚本攻击。
 * @param {string} tag HTML 标签名称。
 * @param {string} [text] 节点纯文本内容。
 * @param {string} [className] CSS 样式类名。
 * @returns {HTMLElement}
 */
export function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}

/**
 * 根据表头与行数据二维数组动态构建具备横向滚动条的响应式数据展示表格。
 * @param {string[]} columns 表头列名集合。
 * @param {any[][]} rows 行级数据列表。
 * @returns {HTMLDivElement} 包裹 table 节点的滚动容器。
 */
export function table(columns, rows) {
  const wrap = element("div", undefined, "table-scroll");
  const node = element("table", undefined, "data-table");
  const head = element("thead");
  const header = element("tr");
  const body = element("tbody");

  columns.forEach((c) => header.append(element("th", c)));
  head.append(header);

  for (const row of rows) {
    const tr = element("tr");
    columns.forEach((_, i) => tr.append(element("td", row[i] == null ? "" : String(row[i]))));
    body.append(tr);
  }

  node.append(head, body);
  wrap.append(node);
  return wrap;
}
