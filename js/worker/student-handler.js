/**
 * 学生信息脱敏任务适配处理服务 (Student Tool Worker Task Handler)。
 * 负责主线程与 Python 算法沙箱的输入输出桥接：
 * 虚拟内存文件挂载、Pyodide 全局环境注入、脱敏管道调度、输出二进制流转移及沙箱临时文件安全回收。
 */
import { lastTracebackLine } from "./errors.js";

/**
 * 处理面向学生信息表的各类脱敏业务任务。
 * @param {any} pyodide Pyodide 运行实例。
 * @param {Object} msg 主线程派发的任务负载。
 * @param {Function} post 结果回传主线程回调。
 */
export function handleStudent(pyodide, msg, post) {
  const extension = [".csv", ".tsv", ".xlsx"].includes(msg.extension) ? msg.extension : ".invalid";
  // 使用数字请求标识符命名虚拟路径，杜绝源文件名进入虚拟文件系统
  const stem = "/tmp/student-" + String(msg.id).replace(/\D/g, "");
  const source = stem + "-src" + extension;
  const destination = stem + "-out" + extension;

  try {
    // 将二进制字节写入沙箱虚拟内存文件系统 (MEMFS)
    pyodide.FS.writeFile(source, new Uint8Array(msg.buffer));
    pyodide.globals.set("_student_source", source);
    pyodide.globals.set("_student_destination", destination);

    let json;
    if (msg.type === "student-inspect") {
      // 执行文件结构解析与列名智能推断
      json = pyodide.runPython("import json\njson.dumps(student.inspect_file(_student_source), ensure_ascii=False)");
    } else {
      pyodide.globals.set("_student_rules", JSON.stringify(msg.rules));
      pyodide.globals.set("_student_policy", msg.policy);
      // 分流执行样本预览 (preview_file) 与全量批处理 (process_file)
      const call = msg.type === "student-preview"
        ? "student.preview_file(_student_source, json.loads(_student_rules), _student_policy)"
        : "student.process_file(_student_source, _student_destination, json.loads(_student_rules), _student_policy)";
      json = pyodide.runPython("import json\njson.dumps(" + call + ", ensure_ascii=False)");
    }

    const result = JSON.parse(json);
    // 全量处理且未阻断导出时，提取并转移导出文件二进制字节流 (Transferable ArrayBuffer)
    if (msg.type === "student-process" && !result.blocked) {
      const bytes = pyodide.FS.readFile(destination);
      const buffer = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
      post({ type: "student-result", id: msg.id, result, buffer }, [buffer]);
    } else {
      post({ type: "student-result", id: msg.id, result });
    }
  } catch (err) {
    // 安全异常净化：仅允许预定义的安全业务提示抛出至前端，屏蔽底层完整 Traceback，防止敏感数据或系统路径泄露
    const safeErrors = [
      "只支持 CSV", "表头存在", "文件中没有", "单个文件", "字段类型",
      "保留位数", "请先为该列", "必填或邮箱", "异常处理方式", "缺少本次",
      "有字段未配置", "请至少配置", "不能删除全部",
    ];
    const last = lastTracebackLine(String(err.message));
    const known = safeErrors.some((prefix) => last.startsWith("ValueError: " + prefix));
    post({
      type: "student-result",
      id: msg.id,
      error: known ? last.slice(12) : "文件读取或处理失败，请检查文件格式、编码和表格内容。",
    });
  } finally {
    // 强制执行内存沙箱临时文件安全擦除，释放虚拟文件系统资源
    for (const path of [source, destination]) {
      try { pyodide.FS.unlink(path); } catch { /* 忽略尚未创建或已被清理的文件 */ }
    }
    if (pyodide) {
      pyodide.runPython("globals().pop('_student_rules', None)\nNone");
    }
  }
}
