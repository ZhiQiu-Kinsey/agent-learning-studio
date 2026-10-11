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
