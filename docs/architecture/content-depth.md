# 讲解深度规范（2026-10-04 起）

依据：2026-10-04 的内容审计。改写前，导学 4 章合计约 6300 字，每课理解场景 1200–3000 字，正文段落平均 55–110 字。概念只有定义，缺少动机、直觉和机制。参考对照：hello-agents 第 1–3 章，深入理解 AI Agent 引言与第一章。

本规范是 [新增课程](adding-lessons.md)“节奏”一节的补充：节奏规则不变（一课一件事、本课新概念 ≤5、先跑一次、每三节一道微测），这里只规定每一节写多深。

## 两层写法：主线 + 深入一层

- **主线**（prose、steps、compare、micro-quiz 等）：学习者顺着读下来就能跑实验、做自检。每一节都要回答“为什么要有它”，不只给定义。
- **深入一层**（`deep-dive` 块，默认折叠）：放背景、机制、手算小例子、真实产品的做法和历史由来。不读它不影响主线；读了能明白“为什么是这样”。深入块不计入“每三节一道微测”的节奏。

## 每节写什么

每个 prose 节按这四步展开，不必每步都单独成段。**第一段第一句写本节结论**（课程大纲取它作小节摘要），问题从第二句起展开：

1. **问题**：没有它会坏在哪？给一个具体场景（真实字段名、真实数字），不要从定义开始。
2. **直觉**：一个类比或一个手算的小例子。类比用完就收，不要连用三个。
3. **机制**：它在请求、响应或程序里具体长什么样，联系本课源码和事件。
4. **边界**：它能证明什么、不能证明什么，常见的误解是什么。

段落写 80–200 字，每节 2–4 段。仍然要短句、先说结论，不写套话。

## 每课的最低要求

| 项 | 要求 |
| --- | --- |
| 理解场景篇幅 | 只数 prose 正文的汉字：约 2000–3000 字（概念卡、微测、参考资料不算）；深入块另计约 800–2000 字 |
| 动机 | 第一节先讲清这一课要解决的问题，可以接上一课的不足 |
| 深入块 | 1–3 个，每个 200–700 字，有标题和一句话 summary；放在相关正文节之后、微测之前，不夹在两节正文中间 |
| 误区 | 至少 1 个 `misconception` 块，写学习者真会有的误解 |
| 参考资料 | 理解场景末尾放 1 个 `references` 块，链接到登记过的参考（见 [reference-study.md](reference-study.md)），只用 https 的 GitHub 或官方文档地址 |
| 与前后课的连接 | 用 `{{lesson:<slug>}}` 指出“上一课留下了什么问题”“下一课会解决什么” |

导学章节同样适用：每章至少 4 节、1 道微测、1 个误区、1–2 个深入块，章末有检查点和参考资料。

## 公式、变量和英文名

- 公式和变量写进反引号代码样式，例如 `exp(2.0) ≈ 7.39`、`top_k=2`。代码样式不参与术语与裸英文检查。正文里不要出现单独的小写字母或小写英文单词。
- 参考资料标题用中文意译，后面括注项目名；英文专名首字母大写，例如“什么是大语言模型（Hugging Face Agents Course）”。
- 参考链接固定到 commit（`/blob/<commit>/路径`），项目必须在 reference-study.md 里登记过。用到的具体文件在汇报里列出，由统稿时补登到第 8 节。

## 深度上限

讲到“直觉 + 手算小例子”为止。

- **可以讲**：Token 与分词的直觉、下一个 Token 预测、概率分布与采样（几个数字手算）、上下文窗口、按 Token 计费，以及模型不记得对话、知识截止、幻觉。
- **不讲**：Transformer 内部结构、QKV 公式、BPE 算法实现、训练细节、缩放法则数据。确实需要提时一句带过，并说明不影响本课。

## 参照哪些资料

- 登记在 [reference-study.md](reference-study.md) 里的参考同等重要：深入理解 AI Agent、Hugging Face Agents Course、Microsoft AI Agents for Beginners、claude-cookbooks、learn-claude-code、hello-agents。
- 每章或每课至少对照其中两份，取各自讲得最好的部分，不以某一份为主。

## 不变的红线

- 运行数据只来自真实事件。正文里的数字如果是编的例子，要说明是“举个编的例子”。walkthrough 和 flow 继续标注为教学示意。
- 术语按 [terminology.md](terminology.md)：课程概念只在引入课第一次出现时写“中文（English）”；新出现的同义叫法先查统一用词表。深入块的文字同样受术语检查。
- 不改实验的事实字段（选择器、对照组输入、预测规则），除非为了修正错误；改了要跑 `tests/test_lesson_experiments.py`。
- 试点范例：`lessons/lesson_sampling_variance/content.json`（2026-10-04 扩写）。
- 参考资料的复用：
  - hello-agents（CC BY-NC-SA）只借鉴组织方式，不复制正文、代码和配图；
  - Apache-2.0 和 MIT 的资料可以改写复用，但不逐句翻译，并在 `references` 里署名。

## 写完自查

```powershell
$env:PYTHONPATH = "tests"   # 单独跑测试模块时需要
.\.venv\Scripts\python.exe scripts/validate_lessons.py
.\.venv\Scripts\python.exe scripts/term_report.py --lesson <slug> --full
.\.venv\Scripts\python.exe scripts/migrate_content.py --check
.\.venv\Scripts\python.exe -m unittest tests.test_lesson_experiments tests.test_lesson_vocabulary
```

逐段对照 `term_report.py --full` 的输出，审读没收录的中文术语和代码名。
