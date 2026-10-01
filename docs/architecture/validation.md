# 开发验证

后端测试检查课程目录、清单、输入校验、执行预算、取消、模型适配、事件与 SQLite 记忆。浏览器测试检查导学、导航、课程实验、回放、主题、响应式布局和可信扩展回退。

## 后端与课程数据

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check
```

清单校验包括 planned 草稿，但不会解锁课程。新增课程既需要结构校验，也需要实际行为与教学验收。

## 前端与浏览器

```powershell
npm.cmd --prefix frontend run build
.\.venv\Scripts\python.exe run_web.py
# 后端保持运行，在另一个终端执行：
Set-Location frontend
npx.cmd playwright test
```

浏览器测试默认访问 http://127.0.0.1:8765，使用系统 Chrome。可通过 AGENT_LAB_URL 设置测试入口。

## 测试模式与真实运行

自动化测试通过网络边界使用后端内部确定性模型适配器，同时执行真实 Python 工具。本地数据库测试使用临时目录；学生网页只提供真实运行。模拟响应不能作为真实模型质量的证明。

代表性真实模型验证需明确模型、样本、调用数量及校验标准，另外报告结果。模型完成、HTTP 成功、工具执行与任务验收是不同结论。运行轨迹和截图属于本机诊断资料，保存在被忽略的 .runtime 目录；SQLite 学习记忆也不提交到仓库。
