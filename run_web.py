"""在 IDE 中运行本文件，网页服务会继承 IDE 的百炼环境变量。"""
import uvicorn

if __name__ == "__main__":
    print("AgentStart 教学平台：http://127.0.0.1:8765", flush=True)
    uvicorn.run("server.app:app", host="127.0.0.1", port=8765, log_level="warning", access_log=False)
