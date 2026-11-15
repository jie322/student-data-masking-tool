/**
 * 脱敏处理结果、统计看板与异常审计视图渲染模块 (Processing Results & Audit UI Component)。
 * 负责渲染批处理宏观指标看板、工作表多级折叠前瞻预览面板及异常事件溯源审计表格。
 */
import { $, element, table } from "./dom.js";

/**
 * 渲染脱敏结果视图集（包含统计面板、多工作表折叠预览及结构化问题表格）。
 * @param {Array} results 各文件处理结果集。
 * @param {Object} summary 批次聚合统计字典。
 * @param {boolean} blocked 是否处于熔断阻断状态。
 * @param {boolean} [previewOnly=false] 是否为样本预览模式。
 */
export function renderResults(results, summary, blocked, previewOnly = false) {
  // 依据执行模式（样本前瞻 vs 全量批处理）及阻断状态切换上下文提示
  const message = previewOnly
    ? (blocked ? "样本检查发现问题，请根据下方记录修正规则或源数据，再次预览。" : "已按当前规则生成脱敏预览。仅检查各表前 10 行，确认效果后请开始批量脱敏。")
    : (blocked ? "导出已阻止。请点击预览核对处理结果，并根据异常位置修正规则或源数据。" : "处理与导出检查已完成。点击下方预览按钮，核对脱敏后的数据。");

  const state = element("div", message, "result-state" + (blocked ? " blocked" : ""));
  const stats = element("div", undefined, "stats");

  const labels = previewOnly
    ? { input_rows: "取样行数", output_rows: "样本保留行数", masked_cells: "样本脱敏单元格", anomaly_rows: "样本异常行数", skipped_rows: "样本隔离行数", residual_cells: "样本敏感残留" }
    : { input_rows: "导入行数", output_rows: "保留行数", masked_cells: "脱敏单元格", anomaly_rows: "异常行数", skipped_rows: "隔离行数", residual_cells: "敏感残留" };

  for (const [key, label] of Object.entries(labels)) {
    const stat = element("div", undefined, "stat");
    stat.append(element("b", String(summary[key] || 0)), element("span", label));
    stats.append(stat);
  }

  $("resultSummary").className = "";
  $("resultSummary").replaceChildren(state, stats);

  // 逐个文件及工作表构建带有独立可折叠交互的脱敏前瞻面板
  for (const { file, result } of results) {
    for (const [sheetIndex, sheet] of result.sheets.entries()) {
      const item = element("div", undefined, "preview-item");
      const heading = element("div", undefined, "preview-item-heading");
      const rows = sheet.rows.slice(0, 10);
      const toggle = element("button", rows.length ? `预览前 ${rows.length} 行` : "暂无可预览数据");
      const panel = element("div", undefined, "preview-panel");

      panel.id = `result-preview-${file.index}-${sheetIndex}`;
      panel.hidden = true;
      toggle.type = "button";
      toggle.disabled = rows.length === 0;
      toggle.setAttribute("aria-controls", panel.id);
      toggle.setAttribute("aria-expanded", "false");

      // 懒加载模式渲染表格 DOM，支持多次切换展开与收起
      const togglePreview = () => {
        const note = previewOnly
          ? `仅预览原表前 10 行中的保留数据，当前显示 ${rows.length} 行；原表共 ${file.meta.sheets[sheetIndex].count} 行。完整检查将在批量脱敏时进行。`
          : `当前显示处理后的前 ${rows.length} 行，共保留 ${sheet.count} 行。`;
        if (!panel.hasChildNodes()) {
          panel.append(table(sheet.columns, rows), element("p", note, "preview-note"));
        }
        const expanded = panel.hidden;
        panel.hidden = !expanded;
        toggle.setAttribute("aria-expanded", String(expanded));
        toggle.textContent = expanded ? "收起预览" : `预览前 ${rows.length} 行`;
      };

      toggle.addEventListener("click", togglePreview);
      // 前瞻预览模式默认自动展开首屏视图
      if (previewOnly && rows.length) {
        togglePreview();
      }

      heading.append(
        element("p", `文件${file.index} · ${file.source.name} · ${sheet.label} · ${previewOnly ? "样本" : ""}保留 ${sheet.count} 行`, "preview-title"),
        toggle
      );
      item.append(heading, panel);
      $("resultPreview").append(item);
    }
  }

  // 聚合批次内所有文件的异常告警事件，界面截取展示前 100 条记录
  const issues = results.flatMap(({ file, result }) => result.issues.map((issue) => ({ file: file.index, ...issue })));
  if (issues.length) {
    const box = element("div", undefined, "issue-box");
    box.append(
      element("h3", `${previewOnly ? "样本" : ""}异常与处理记录（${issues.length} 项）`),
      table(
        ["文件", "数据表", "原始行号", "列位置", "处理说明"],
        issues.slice(0, 100).map((i) => ["文件" + i.file, i.sheet, i.row, i.column || "整行", i.reason])
      ),
      element("p", previewOnly ? "此处仅记录预览样本的问题，不包含异常原文。完整处理后可下载处理报告。" : "此处最多显示 100 项；处理报告保留全部位置记录，不包含异常原文。", "preview-note")
    );
    $("issues").append(box);
  }
}
