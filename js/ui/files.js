/**
 * 文件列表与前置样本视图渲染模块 (File Queue & Source Sample UI Component)。
 * 渲染导入文件卡片元数据（行数、工作表计数、体积），提供队列动态剔除操作，并可视化展示各表前 5 行原始数据结构。
 */
import { files } from "../state.js";
import { $, element, table } from "./dom.js";
import { rebuildRules } from "./rules.js";
import { invalidate, setBusy } from "./feedback.js";

/**
 * 依据当前内存中的 files 数组重新渲染文件管理列表及源表前瞻样本。
 */
export function renderFiles() {
  $("fileList").replaceChildren();
  $("sourcePreview").replaceChildren();

  for (const file of files) {
    const row = element("div", undefined, "file-row");
    const info = element("div", undefined, "file-info");

    info.append(element("span", file.source.name, "file-name"));
    info.append(
      element(
        "span",
        file.meta
          ? `${file.meta.row_count} 行 · ${file.meta.sheets.length} 个数据表 · ${(file.source.size / 1024).toFixed(1)} KB`
          : file.error,
        "file-meta" + (file.error ? " file-error" : "")
      )
    );

    const remove = element("button", "移除", "quiet");
    remove.setAttribute("aria-label", `移除文件${file.index}`);
    // 从当前会话批次队列中移除所选文件，联动重建规则映射并标记旧视图失效
    remove.addEventListener("click", () => {
      files.splice(files.indexOf(file), 1);
      rebuildRules();
      renderFiles();
      invalidate();
      setBusy(false);
    });

    row.append(element("span", String(file.index).padStart(2, "0"), "file-index"), info, remove);
    $("fileList").append(row);

    // 渲染各工作表前 5 行原始样本数据表格，辅助用户比对原始列名与数据排布
    if (file.meta) {
      for (const sheet of file.meta.sheets) {
        const item = element("div", undefined, "preview-item");
        item.append(
          element("p", `文件${file.index} · ${sheet.label} · 原始样本`, "preview-title"),
          table(sheet.columns, sheet.rows)
        );
        $("sourcePreview").append(item);
      }
    }
  }

  if (!files.length) {
    $("fileList").append(element("p", "尚未导入表格。请选择文件，或导入项目中的学生信息表。", "empty"));
  }
  $("runHint").textContent = files.some((f) => !f.meta)
    ? "请先移除读取失败的文件。"
    : `已导入 ${files.length} 个文件，请核对字段规则。`;
}
