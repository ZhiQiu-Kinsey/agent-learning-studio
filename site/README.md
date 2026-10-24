# 官网（`site/`）

Agent Learning Studio 的静态介绍站，发布在 <https://zhiqiu-kinsey.github.io/agent-learning-studio/>。

它只是介绍页：不运行平台，不调用模型，也不执行工具。平台本身只在学习者自己的电脑上运行，因为后端只绑定 127.0.0.1、需要模型密钥，编码课还会执行模型写的命令，执行环境没有隔离。

## 内容从哪里来

站点不手抄课程数据。`scripts/build-data.mjs` 在 `dev` 和 `build` 之前运行，从仓库生成：

| 生成物（不提交） | 来源 |
| --- | --- |
| `src/generated/curriculum.json` | `curriculum/catalog.json` 加英文层 `catalog.en.json`。课号按目录顺序计算；译文过期时回落到中文原文，页面标 `lang="zh-CN"`。规则与 `server/data_overlay.py` 相同。 |
| `src/generated/recordings.json` 与 `public/data/recordings/` | `lessons/*/recordings/*.json`，原样复制；同一练习、同一运行语言只取最新一份 |
| `public/screenshots/` | `docs/assets/screenshots/{zh-CN,en}/` |

加课、改课或新增录制后，重新构建即可同步。

## 真实运行回放

- 回放区复用平台的 `AgentStage`、`Timeline`、`EventList`、`EventDetail`、`ReplayToolbar`、`ApprovalPanel` 和 `EvidenceBoard`，通过 Vite 别名 `@studio` 直接引用 `frontend/src`，不复制代码。
- 回放状态由 `src/replay/useRecordingPlayer.ts` 提供，使用平台同一个回放时钟（`stage/replay.ts`）：只在已记录的事件上移动游标，不请求模型，也不执行工具。
- 页面写明“真实运行录制”、模型、服务商、SDK 与日期。SDK 标准化的数据标注为 SDK 标准化，不称原始 HTTP 报文。
- 这些组件的第三方依赖都装在 `site/node_modules`，并在 `vite.config.ts` 里去重。构建站点不需要 `frontend/node_modules`。

## 本地预览

```bash
uv run lab.py site     # 按需安装依赖、构建，然后预览 http://127.0.0.1:4173/agent-learning-studio/
```

它依次做的是 `npm --prefix site ci`（依赖没装或锁文件变了时）、`npm --prefix site run build`、`npm --prefix site run preview`。开发时用 `npm --prefix site run dev`。

部署路径默认是 `/agent-learning-studio/`。要在根路径预览，用 `SITE_BASE=/ npm --prefix site run build`。

## 更新录制

录制与平台的“随课录制”是同一份文件，规则见 `docs/architecture/event-envelope-v2.md` 第 6 节。

1. 用真实模型运行练习。例如：
   ```bash
   .venv/bin/python scripts/run_live.py <slug> <练习> --url http://127.0.0.1:8790 --locale en
   ```
   有审批的课加 `--ask-approvals`。
2. 导出录制（会检查密钥和本机路径）：
   ```bash
   .venv/bin/python scripts/export_recording.py --run <run_id> --name <名称>
   ```
3. 校验：
   ```bash
   .venv/bin/python scripts/validate_recordings.py
   ```
4. 提交 `lessons/<课程目录>/recordings/<名称>.json`。

课程源码（`lesson.json` 与 `sources`）一改，录制的 `source_hash` 就会过期，`validate_recordings.py` 会报“源码已变化，请重新录制”，Pages 工作流也会因此失败。这时按上面的步骤重新录制，不要改录制文件。

当前录制都是 2026-10-21 用 Anthropic `claude-haiku-5-5` 经 LiteLLM 录下的。每门课一个练习，中文、英文各一次：

- `chat-request` basic
- `tool-selection` sum
- `rag-citations` grounded
- `hooks-approval` approve-write
- `multi-agent-patterns` multi

## 部署

`.github/workflows/pages.yml` 的触发方式：

- **main 有推送**，且改动涉及 `site/`、课程目录、课程清单、录制、截图，或被复用的前端组件、样式与文案时：先运行 `validate_recordings.py`，再构建 `site/`，然后用 `actions/upload-pages-artifact` 与 `actions/deploy-pages` 发布。
- **拉取请求**：只构建，作为检查。
- **手动触发**（workflow_dispatch）也可以。

第一次发布前，维护者要在仓库 **Settings → Pages → Build and deployment → Source** 选 **GitHub Actions**。

## 约定

- 文案只写在 `src/locales/<语言>/site.json`，组件里不写中文。默认语言按浏览器语言，可在页眉切换，选择存在本机 `localStorage`。
- 动效判断一律走 `frontend/src/motion`。首屏的 WebGL 背景（React Bits Threads）只在完整动效、支持 WebGL 且在屏幕内时挂载，离屏卸载并释放 context。
- 不引用第三方 URL 的脚本和字体，用系统字体栈。
