// 限制的是本模块主动使用的网络接口。origin 指“协议 + 地址 + 端口”，相同 origin 才是当前服务。
// Worker 单独限制网络访问，只允许读取当前本地服务的资源。
// 这是程序自身的防误用保护；部署时的浏览器策略仍见根目录 _headers。
// 包装资源读取接口并返回已读取的依赖地址集合；真实部署策略另由 _headers 约束。
export function installNetworkGuard() {
  const OWN_ORIGIN = self.location.origin;
  const fetchedVendorUrls = new Set();
  // 先保存原本的读取函数，再安装检查入口；通过检查后才调用真正的读取。
  const realFetch = self.fetch.bind(self);
  self.fetch = (input, init) => {
    const url = typeof input === "string" ? input : input.url;
    const resolved = new URL(url, OWN_ORIGIN);
    // 不同地址或端口的资源请求会被拒绝，减少误把处理过程连向外部地址的机会。
    if (resolved.origin !== OWN_ORIGIN) {
      return Promise.reject(new Error("blocked: cross-origin fetch from worker: " + url));
    }
    if (resolved.pathname.includes("/vendor/")) fetchedVendorUrls.add(resolved.href);
    return realFetch(input, init);
  };
  // 关闭本项目没有使用的另外两种连接方式，避免误用它们绕过约定流程。
  self.XMLHttpRequest = function () {
    throw new Error("blocked: XMLHttpRequest is not used by this app");
  };
  self.WebSocket = function () {
    throw new Error("blocked: WebSocket is not used by this app");
  };

  return fetchedVendorUrls;
}
