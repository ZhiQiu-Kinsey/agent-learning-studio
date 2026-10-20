"""Local Bailian (DashScope) settings. Copy to local_config.py and fill in real values; local_config.py is git-ignored.

本机百炼配置模板。复制为 local_config.py 后填写真实设置（该文件已被 .gitignore 排除）。
The API key is NOT stored here: set the DASHSCOPE_API_KEY environment variable.
密钥不写在这里，请用环境变量 DASHSCOPE_API_KEY 提供。
"""

# OpenAI-compatible chat-completions URL shown in the Bailian console for your region and workspace.
# 百炼控制台为当前地域和 Workspace 显示的 OpenAI 兼容聊天补全地址。
API_URL = "REPLACE_WITH_YOUR_BAILIAN_CHAT_COMPLETIONS_URL"

# A model ID that works on Bailian and supports tool calling.
# 已在百炼验证可用并支持工具调用的模型 ID。
MODEL = "REPLACE_WITH_YOUR_TOOL_CAPABLE_MODEL"

# Optional: embedding requests (retrieval lessons). Without these lines the platform uses
# text-embedding-v4 and derives the URL from API_URL (/chat/completions -> /embeddings).
# 可选：Embedding 请求（检索课使用）。不写时默认 text-embedding-v4，地址由 API_URL 推导
# （把 /chat/completions 换成 /embeddings）。
# EMBEDDING_MODEL = "text-embedding-v4"
# EMBEDDING_API_URL = "REPLACE_WITH_YOUR_BAILIAN_EMBEDDINGS_URL"
