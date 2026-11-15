"""本地 Web 模式独立启动入口模块。

在开发或无 GUI 依赖环境下，拉起轻量 HTTP 静态资源服务（监听 127.0.0.1:8000），
使用户可通过现代主流浏览器直接访问并运行纯前端 WebAssembly 脱敏引擎。
"""
from pathlib import Path

from desktop_app.server import create_server


def main():
    """启动本地 HTTP 服务，服务静态资源并监听 8000 端口。"""
    # 静态服务根目录锚定为项目工程根目录，保障路径解析一致性
    server = create_server(Path(__file__).resolve().parent, port=8000)
    print("本地服务已就绪，请在浏览器中访问：http://127.0.0.1:8000/index.html", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在停止本地服务...", flush=True)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
