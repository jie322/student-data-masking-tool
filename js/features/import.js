/**
 * 文件导入与预解析处理模块 (File Import & Inspection Feature)。
 * 负责文件格式校验、基于 Web Crypto SHA-256 的跨文件内容去重、分发元数据解析任务并更新全局规则表。
 */
import { files, state } from "../state.js";
import { request } from "../services/engine.js";
import { invalidate, log, notice, setBusy } from "../ui/feedback.js";
import { renderFiles } from "../ui/files.js";
import { rebuildRules } from "../ui/rules.js";

/**
 * 批量导入并预解析用户选取的表格文件。
 * @param {File[]} selected 用户选取的 File 对象集合。
 */
export async function importFiles(selected) {
  if (state.busy || !state.ready) return;
  setBusy(true);
  notice();
  invalidate();
  let duplicates = 0;

  try {
    for (const source of selected) {
      const index = state.fileSequence++;
      const extension = source.name.slice(source.name.lastIndexOf(".")).toLowerCase();
      const record = { source, index, extension };

      // 强校验支持的文件后缀与 25MB 大小限制阈值
      if (![".csv", ".tsv", ".xlsx"].includes(extension) || source.size > 25 * 1024 * 1024) {
        record.error = "格式不支持或文件超过 25 MB。";
        files.push(record);
        continue;
      }

      // 计算文件内容的 SHA-256 密码学指纹，实施严格的内容级去重（防同名改名重复提交）
      const buffer = await source.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", buffer);
      record.hash = Array.from(new Uint8Array(digest), (v) => v.toString(16).padStart(2, "0")).join("");

      if (files.some((f) => f.hash === record.hash)) {
        duplicates++;
        continue;
      }

      try {
        // 向 Worker 投递 Transferable ArrayBuffer，执行零拷贝沙箱元数据抽取 (student-inspect)
        const response = await request("student-inspect", { extension, buffer }, [buffer]);
        record.meta = response.result;
        log(`文件${index}导入完成，共 ${record.meta.row_count} 行。`);
      } catch (error) {
        record.error = error.message;
        log(`文件${index}导入失败，未记录文件内容。`);
      }
      files.push(record);
    }

    // 重新构建字段规则映射表并渲染文件卡片
    rebuildRules();
    renderFiles();
    if (duplicates) {
      notice(`已跳过 ${duplicates} 个内容完全相同的文件，避免重复导入。`);
    }
  } catch {
    notice("读取文件失败，请重新选择文件。", true);
  } finally {
    setBusy(false);
  }
}

/**
 * 快速加载系统内置样例数据集（如 students_100.csv / students_edge_cases.csv）。
 * @param {string} name 样例文件名。
 */
export async function loadSample(name) {
  if (state.busy || !state.ready) return;
  try {
    const response = await fetch("sample_data/" + name);
    if (!response.ok) throw new Error();
    await importFiles([new File([await response.blob()], name, { lastModified: 0 })]);
  } catch {
    notice("无法读取学生信息表，请检查本地服务是否启动。", true);
  }
}
