// 从 Python 的多行报错中取出末行，供学生处理器匹配固定提示；不是直接把整段报错显示给用户。
// Python 报错可能包含堆栈；业务处理器只使用最后一行匹配固定提示。
// 输入报错文字，去掉两端空白并按换行拆开，返回最后一行。
export function lastTracebackLine(message) {
  // PythonError.message 含完整堆栈；这里只取“异常类型: 提示”这一行。
  const lines = message.trim().split("\n");
  return lines[lines.length - 1];
}
