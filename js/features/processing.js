/**
 * 脱敏业务流水线驱动模块 (Data Processing & Preview Pipelines)。
 * 编排轻量样本预览流水线 (previewResults) 与全量批处理导出流水线 (processFiles)，
 * 负责批次进度追踪、熔断阻断判定、内存无损审计报告聚合及 JSZip 结果压缩包生成。
 */
import { files, rules, state } from "../state.js";
import { request } from "../services/engine.js";
import { downloadUrl } from "../services/downloads.js";
import { buildReport } from "../services/report.js";
import { $ } from "../ui/dom.js";
import { invalidate, log, notice, setBusy } from "../ui/feedback.js";
import { renderResults } from "../ui/results.js";

/**
 * 执行前瞻样本脱敏预览流水线（仅处理前 10 行样本，不生成落盘导出文件）。
 */
export async function previewResults() {
  if (state.busy || !files.length) return;

  // 阶段 1：锁定交互状态、初始化进度指示器并使旧数据视图失效
  invalidate("正在按当前规则生成前 10 行的脱敏预览……");
  notice();
  setBusy(true);
  const progress = $("processProgress");
  progress.max = files.length;
  progress.value = 0;
  progress.hidden = false;
  progress.setAttribute("aria-label", "脱敏效果预览进度");

  const results = [], summary = {};
  try {
    for (const file of files) {
      // 始终从源文件克隆独立 ArrayBuffer，杜绝多轮预览引起的数据累积污染
      const buffer = await file.source.arrayBuffer();
      // 向计算沙箱投递 student-preview 任务，携带列规则字典与异常处理策略
      const response = await request(
        "student-preview",
        {
          extension: file.extension,
          buffer,
          rules: Object.fromEntries(rules),
          policy: $("anomalyPolicy").value,
        },
        [buffer]
      );
      results.push({ file, ...response });
      for (const [key, value] of Object.entries(response.result.summary)) {
        summary[key] = (summary[key] || 0) + value;
      }
      progress.value++;
    }

    // 阶段 2：呈现多表前瞻预览与样本统计视图
    renderResults(results, summary, results.some(({ result }) => result.blocked), true);
    log(`脱敏效果预览已完成，共取样 ${summary.input_rows} 行，未生成导出文件。`);
  } catch (error) {
    notice(error.message, true);
    $("resultSummary").textContent = "预览未完成，请修正规则或源数据后重试。";
    log("脱敏效果预览失败，未生成导出文件。");
  } finally {
    progress.hidden = true;
    setBusy(false);
  }
}

/**
 * 执行全量数据批处理脱敏流水线（逐表全量脱敏、安全深度审计、报告聚合与 ZIP 压缩打包）。
 */
export async function processFiles() {
  if (state.busy || !files.length) return;

  // 阶段 1：就绪化处理环境，重置旧结果与下载通道
  invalidate("正在校验规则并处理本次批次……");
  notice();
  setBusy(true);
  const progress = $("processProgress");
  progress.max = files.length;
  progress.value = 0;
  progress.hidden = false;
  progress.setAttribute("aria-label", "批量处理进度");

  const results = [], summary = {};
  try {
    for (const file of files) {
      const buffer = await file.source.arrayBuffer();
      // 向沙箱分发全量脱敏指令 (student-process)，获得脱敏后的二进制流与审计指标
      const response = await request(
        "student-process",
        {
          extension: file.extension,
          buffer,
          rules: Object.fromEntries(rules),
          policy: $("anomalyPolicy").value,
        },
        [buffer]
      );
      results.push({ file, ...response });
      for (const [key, value] of Object.entries(response.result.summary)) {
        summary[key] = (summary[key] || 0) + value;
      }
      progress.value++;
      log(`文件${file.index}处理完成：${response.result.summary.input_rows} 行，${response.result.summary.anomaly_rows} 行异常，${response.result.summary.residual_cells} 处残留。`);
    }

    // 阶段 2：执行批次级熔断判断（任意单表存在残留或触发阻断策略，则全批次禁止导出表格）
    const blocked = results.some(({ result }) => result.blocked);
    renderResults(results, summary, blocked);

    // 阶段 3：构建结构化合规审计报告（仅含行号、列索引与标准原因，严防明文泄漏）
    const report = buildReport(results, summary, blocked, rules, $("anomalyPolicy").selectedOptions[0].textContent);
    const reportText = JSON.stringify(report, null, 2);
    $("reportLink").href = downloadUrl(new Blob([reportText], { type: "application/json" }));
    $("downloads").hidden = false;
    $("exportLink").hidden = blocked;

    // 阶段 4：安全审计通过后，将各脱敏表格与审计报告在客户端纯内存环境中编包打包为 ZIP
    if (!blocked) {
      const zip = new JSZip();
      for (const { file, buffer } of results) {
        zip.file(`脱敏结果_${String(file.index).padStart(2, "0")}${file.extension}`, new Uint8Array(buffer));
      }
      zip.file("处理报告.json", reportText);
      $("exportLink").href = downloadUrl(await zip.generateAsync({ type: "blob" }));
      log(`本批次检查通过，可导出 ${results.length} 个脱敏表格。`);
    } else {
      notice("本批次已阻止表格导出，可下载不含原文的处理报告定位问题。", true);
      log("本批次未通过检查，已阻止表格导出。");
    }
  } catch (error) {
    notice(error.message, true);
    $("resultSummary").textContent = "处理未完成，没有生成导出包。请修正规则后重试。";
    log("规则校验或文件处理失败，未生成导出包。");
  } finally {
    progress.hidden = true;
    setBusy(false);
  }
}
