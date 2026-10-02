# 开发验证

后端测试检查以下内容：课程目录、清单、内容 v2 schema、迁移与译文层、示意契约、实验选择器命中、课程用词（术语、中英并列、裸英文词、代码说明）、节奏与读码规范（每课新概念不超过 5 个、predict 在第一道微测之前、批注锚点与密度、课程文本与源码不写死课号）、输入校验、执行预算、取消、模型适配、事件信封、运行存储、录制和 SQLite 记忆。前端单元测试（vitest）覆盖舞台推导、回放时钟、选择器、导览、预测、进度迁移与快捷键。浏览器测试检查首页、导学、课程地图、五个场景、运行与回放、命令面板、主题、减少动画、响应式布局、无障碍（axe-core）和可信扩展回退。

## 后端与课程数据

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/export_curriculum.py --check
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe scripts/term_report.py           # 逐课用词问题；加 --lesson <slug> --full 看明细
```

源码改动让批注行号移动时，先运行 `scripts/realign_notes.py` 按锚点重新对准，再跑 `validate_lessons`。

清单校验包括 planned 草稿，但不会解锁课程。用词检查只针对可运行课程；中文术语有没有收录要靠作者通读，见 [术语与代码名](terminology.md)。新增课程既需要结构校验，也需要实际行为与教学验收。

## 前端与浏览器

```powershell
npm.cmd --prefix frontend run build
Set-Location frontend
npx.cmd vitest run               # 纯逻辑单元测试，含内容类型、i18n 与选择器基线
npm.cmd run i18n:check           # 各语言的翻译键一致
Set-Location ..
.\.venv\Scripts\python.exe run_web.py
# 后端保持运行，在另一个终端执行：
Set-Location frontend
npx.cmd playwright test
```

浏览器测试默认访问 http://127.0.0.1:8765，使用系统 Chrome。可通过 AGENT_LAB_URL 设置测试入口。

## 测试模式与真实运行

自动化测试通过网络边界使用后端内部确定性模型适配器，同时执行真实 Python 工具。本地数据库测试使用临时目录；学生网页只提供真实运行。模拟响应不能作为真实模型质量的证明。

代表性真实模型验证需明确模型、样本、调用数量及校验标准，另外报告结果。后端运行时可用 `scripts/run_live.py <课程 slug> [练习 id] --url <地址>` 真实运行练习并打印事件摘要（会产生模型用量）。模型完成、HTTP 成功、工具执行与任务验收是不同结论。运行轨迹和截图属于本机诊断资料，保存在被忽略的 .runtime 目录；SQLite 学习记忆也不提交到仓库。
