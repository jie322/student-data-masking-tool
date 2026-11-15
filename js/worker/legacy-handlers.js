// 保留的通用匿名化流程，使用原文与代号的对应表；当前学生工具的星号遮盖实现不在本文件。
// 原有通用匿名化接口。当前学生页面不发送这些请求，保留用于旧代码兼容。
// 学生信息的遮盖流程请阅读 student-handler.js 和 py/student_tool/。
import { lastTracebackLine } from "./errors.js";

// 把旧的任务类型与处理函数组成对照表，供 worker.js 分发旧请求。
export function createLegacyHandlers(pyodide, post) {
  const analyzeFile = pyodide.runPython("engine.analyze_file");

  // 旧接口：读取表头与样本，并按内容给出通用字段建议。
  function handlePreview(msg) {
    const { id, name, buffer } = msg;
    try {
      const path = "/tmp/" + id + "-" + name;
      pyodide.FS.writeFile(path, new Uint8Array(buffer));
      const result = analyzeFile(path, name).toJs({ dict_converter: Object.fromEntries });
      pyodide.FS.unlink(path);
      post({ type: "preview-result", id, name, sheets: result.sheets });
    } catch (err) {
      post({ type: "error", id, message: err.message });
    }
  }

  // 旧接口：把页面配置交给 Python 校验，返回可保存的 JSON 配置。
  function handleBuildConfig(msg) {
    try {
      pyodide.globals.set("_raw_config_json", JSON.stringify(msg.config));
      const validated = pyodide.runPython(
        "config.config_to_json(config.config_from_json(_raw_config_json))"
      );
      post({ type: "config-result", id: msg.id, json: validated });
    } catch (err) {
      post({ type: "config-result", id: msg.id, error: lastTracebackLine(err.message) });
    }
  }

  // 旧接口：收集指定列的不同值，建立或追加“原文 → 代号”对照。
  function handleBuildMapping(msg) {
    try {
      const flatValues = {};
      for (const f of msg.files) {
        const path = "/tmp/map-" + msg.id + "-" + f.name;
        pyodide.FS.writeFile(path, new Uint8Array(f.buffer));
        pyodide.globals.set("_sheet_columns_json", JSON.stringify(f.sheetColumns));
        pyodide.globals.set("_extract_path", path);
        pyodide.globals.set("_extract_file_pattern", f.name);
        const extractedJson = pyodide.runPython(
          "import json\n" +
            "json.dumps(engine.extract_unique_values(_extract_path, json.loads(_sheet_columns_json), file_pattern=_extract_file_pattern))"
        );
        pyodide.FS.unlink(path);
        const extracted = JSON.parse(extractedJson); // {sheet: {col: {values, unique_count, truncated}}}
        flatValues[f.name] = {};
        for (const [sheetName, cols] of Object.entries(extracted)) {
          flatValues[f.name][sheetName] = {};
          for (const [colName, data] of Object.entries(cols)) {
            flatValues[f.name][sheetName][colName] = data.values;
          }
        }
      }

      pyodide.globals.set("_config_json", JSON.stringify(msg.config));
      pyodide.globals.set("_values_json", JSON.stringify(flatValues));
      pyodide.globals.set("_existing_mapping_json", msg.existingMappingJson || "");

      const mappingJson = pyodide.runPython(
        "import json\n" +
          "from mapping import build_mapping, mapping_from_json, mapping_to_json\n" +
          "_cfg = json.loads(_config_json)\n" +
          "_vals = json.loads(_values_json)\n" +
          "_existing = mapping_from_json(_existing_mapping_json) if _existing_mapping_json else None\n" +
          "mapping_to_json(build_mapping(_cfg, _vals, _existing))"
      );
      post({ type: "mapping-result", id: msg.id, json: mappingJson });
    } catch (err) {
      post({ type: "mapping-result", id: msg.id, error: lastTracebackLine(err.message) });
    }
  }

  // 旧接口：按已有对照表替换指定字段，返回新文件和处理计数。
  function handleMask(msg) {
    const srcPath = "/tmp/mask-src-" + msg.id + "-" + msg.name;
    const outPath = "/tmp/mask-out-" + msg.id + "-" + msg.name;
    try {
      pyodide.FS.writeFile(srcPath, new Uint8Array(msg.buffer));
      pyodide.globals.set("_mask_src_path", srcPath);
      pyodide.globals.set("_mask_out_path", outPath);
      pyodide.globals.set("_mask_file_pattern", msg.name);
      pyodide.globals.set("_mask_config_json", JSON.stringify(msg.config));
      pyodide.globals.set("_mask_mapping_json", msg.mappingJson);

      const summaryJson = pyodide.runPython(
        "import json\n" +
          "_cfg = json.loads(_mask_config_json)\n" +
          "_map = mapping.mapping_from_json(_mask_mapping_json)\n" +
          "_summary = masker.mask_file(_mask_src_path, _mask_out_path, _mask_file_pattern, _cfg, _map)\n" +
          "json.dumps(_summary)"
      );

      const outBytes = pyodide.FS.readFile(outPath);
      const buffer = outBytes.buffer.slice(
        outBytes.byteOffset,
        outBytes.byteOffset + outBytes.byteLength
      );
      pyodide.FS.unlink(srcPath);
      pyodide.FS.unlink(outPath);
      post(
        { type: "mask-result", id: msg.id, name: msg.name, buffer, summary: JSON.parse(summaryJson) },
        [buffer]
      );
    } catch (err) {
      post({ type: "mask-result", id: msg.id, name: msg.name, error: lastTracebackLine(err.message) });
    }
  }

  // 旧接口：凭对照表把代号替换回原文；当前学生界面没有这一入口。
  function handleRestore(msg) {
    const srcPath = "/tmp/restore-src-" + msg.id + "-" + msg.name;
    const outPath = "/tmp/restore-out-" + msg.id + "-" + msg.name;
    try {
      pyodide.FS.writeFile(srcPath, new Uint8Array(msg.buffer));
      pyodide.globals.set("_restore_src_path", srcPath);
      pyodide.globals.set("_restore_out_path", outPath);
      pyodide.globals.set("_restore_mapping_json", msg.mappingJson);

      const summaryJson = pyodide.runPython(
        "import json\n" +
          "_map = mapping.mapping_from_json(_restore_mapping_json)\n" +
          "_summary = restorer.restore_file(_restore_src_path, _restore_out_path, _map)\n" +
          "json.dumps(_summary)"
      );

      const outBytes = pyodide.FS.readFile(outPath);
      const buffer = outBytes.buffer.slice(
        outBytes.byteOffset,
        outBytes.byteOffset + outBytes.byteLength
      );
      pyodide.FS.unlink(srcPath);
      pyodide.FS.unlink(outPath);
      post(
        { type: "restore-result", id: msg.id, name: msg.name, buffer, summary: JSON.parse(summaryJson) },
        [buffer]
      );
    } catch (err) {
      post({ type: "restore-result", id: msg.id, name: msg.name, error: lastTracebackLine(err.message) });
    }
  }

  // 旧接口：汇集通用处理统计并生成 HTML 报告，区别于学生工具的中文位置报告。
  function handleBuildReport(msg) {
    try {
      const filesStats = {};
      const rowCounts = {};
      for (const f of msg.files) {
        const path = "/tmp/report-" + msg.id + "-" + f.name;
        pyodide.FS.writeFile(path, new Uint8Array(f.buffer));
        pyodide.globals.set("_report_path", path);
        pyodide.globals.set("_report_file_pattern", f.name);
        pyodide.globals.set("_report_config_json", JSON.stringify(msg.config));
        const resultJson = pyodide.runPython(
          "import json\n" +
            "_cfg = json.loads(_report_config_json)\n" +
            "_sheets, _rows = report.collect_column_stats(_report_path, _report_file_pattern, _cfg)\n" +
            "json.dumps({'sheets': _sheets, 'rows': _rows})"
        );
        pyodide.FS.unlink(path);
        const parsed = JSON.parse(resultJson);
        filesStats[f.name] = parsed.sheets;
        rowCounts[f.name] = parsed.rows;
      }

      pyodide.globals.set("_report_files_stats_json", JSON.stringify(filesStats));
      pyodide.globals.set("_report_row_counts_json", JSON.stringify(rowCounts));
      pyodide.globals.set("_report_mapping_json", msg.mappingJson);
      pyodide.globals.set("_report_config_json", JSON.stringify(msg.config));

      const htmlText = pyodide.runPython(
        "import json\n" +
          "_files_stats = json.loads(_report_files_stats_json)\n" +
          "_row_counts = json.loads(_report_row_counts_json)\n" +
          "_map = mapping.mapping_from_json(_report_mapping_json)\n" +
          "_cfg = json.loads(_report_config_json)\n" +
          "_rep = report.build_report(_files_stats, _row_counts, _cfg, _map)\n" +
          "report.render_report_html(_rep)"
      );
      post({ type: "report-result", id: msg.id, html: htmlText });
    } catch (err) {
      post({ type: "report-result", id: msg.id, error: lastTracebackLine(err.message) });
    }
  }

  return {
    "preview": handlePreview,
    "build-config": handleBuildConfig,
    "build-mapping": handleBuildMapping,
    "mask": handleMask,
    "restore": handleRestore,
    "build-report": handleBuildReport,
  };
}
