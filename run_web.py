"""Start the web app. Run it from an IDE and the server inherits the IDE's provider environment variables.

启动网页服务；在 IDE 中运行时，服务会继承 IDE 的服务商环境变量。
"""
import uvicorn

if __name__ == "__main__":
    print("Agent Learning Studio: http://127.0.0.1:8765", flush=True)
    uvicorn.run("server.app:app", host="127.0.0.1", port=8765, log_level="warning", access_log=False)
