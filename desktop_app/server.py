"""本地环回静态资源服务器模块：为 Web 前端与桌面内嵌视窗提供安全的本地静态资源响应能力。"""
import mimetypes
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class AssetHandler(SimpleHTTPRequestHandler):
    """自定义静态资源请求处理器：强化安全边界，禁止目录遍历探测与请求内容打印。"""

    def log_message(self, *_args):
        """静默处理常规请求日志，避免因打印 URL 引起潜在文件名或参数泄漏。"""
        pass

    def list_directory(self, _path):
        """禁止列举目录文件结构，对于目录访问请求统一返回 404 Not Found。"""
        self.send_error(404)
        return None


def create_server(assets, port=0):
    """构建绑定在 127.0.0.1 环回地址上的多线程 HTTP 服务器实例。

    Args:
        assets: 静态资源物理根目录。
        port: 监听端口号（0 表示由操作系统自动分配可用端口，8000 用于浏览器启动模式）。
    """
    mimetypes.add_type("text/javascript", ".mjs")
    return ThreadingHTTPServer(("127.0.0.1", port), partial(AssetHandler, directory=str(assets)))


def start_server(assets):
    """在守护线程 (daemon thread) 中启动本地资源服务，返回 (server, thread) 元组。"""
    server = create_server(assets)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
