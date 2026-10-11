# 文档索引

[English](README.md) · **简体中文**

项目的源语言是中文。有英文版的文档，英文文件是译文；两者不一致时以中文为准。

## 从这里开始

| 文档 | 内容 | 语言 |
| --- | --- | --- |
| [README](../README.zh-CN.md) | 项目是什么、安装、配置模型服务商 | [English](../README.md) · [中文](../README.zh-CN.md) |
| [CONTRIBUTING](../CONTRIBUTING.zh-CN.md) | 怎样参与：红线、检查命令、提交与拉取请求 | [English](../CONTRIBUTING.md) · [中文](../CONTRIBUTING.zh-CN.md) |
| [AGENTS.md](../AGENTS.md) | 给人和编码代理看的项目规则：红线、常用命令、写法规范 | 中文 |
| [课程大纲](course-plan.md) | 完整课程表，由 `curriculum/catalog.json` 生成 | [English](course-plan.en.md) · [中文](course-plan.md) |

## 架构与作者指南

都在 [architecture/](architecture/) 下。

| 文档 | 内容 | 语言 |
| --- | --- | --- |
| [平台架构](architecture/platform.md) | 架构、当前边界与长期课程设计 | [English](architecture/platform.en.md) · [中文](architecture/platform.md) |
| [前端结构](architecture/frontend-workspace.md) | 页面、模块、界面层的诚实规则、动效、界面文案与多语言 | [English](architecture/frontend-workspace.en.md) · [中文](architecture/frontend-workspace.md) |
| [事件信封 v2](architecture/event-envelope-v2.md) | 运行事件、span、运行存储与 SSE 续读 | [English](architecture/event-envelope-v2.en.md) · [中文](architecture/event-envelope-v2.md) |
| [模型接入与执行证据](architecture/multi-provider-review.md) | 原生 HTTP 与 LiteLLM 接入，执行证据怎样标注 | [English](architecture/multi-provider-review.en.md) · [中文](architecture/multi-provider-review.md) |
| [新增课程](architecture/adding-lessons.md) | 课程脚手架、实现清单、内容 v2、节奏与读码规范、多语言运行时、独立运行器与独立页面 | [English](architecture/adding-lessons.en.md) · [中文](architecture/adding-lessons.md) |
| [课程本地化](architecture/localizing-lessons.md) | 双语运行时与英文译文的逐课清单、踩过的坑、英文写法 | [English](architecture/localizing-lessons.en.md) · [中文](architecture/localizing-lessons.md) |
| [术语与代码名](architecture/terminology.md) | 术语表规则、代码说明、统一用词表、英文文本的检查 | [English](architecture/terminology.en.md) · [中文](architecture/terminology.md) |
| [开发验证](architecture/validation.md) | 有哪些测试和校验、怎样运行 | [English](architecture/validation.en.md) · [中文](architecture/validation.md) |
| [课程来源与教学取舍](architecture/reference-study.md) | 固定版本的参考教程、许可证、阅读范围，以及各课借鉴了什么 | [English](architecture/reference-study.en.md) · [中文](architecture/reference-study.md) |

## 历史记录（只有中文）

下面这些文档记录写作当时的调研、计划和来源，留作追溯，不翻译。与上面的文档不一致时，以上面的文档为准，它们描述的是现状。

| 文档 | 记录的内容 |
| --- | --- |
| [curriculum-research.md](architecture/curriculum-research.md) | 参考教程对照调研，以及它给平台重构定下的约束（2026-10-01） |
| [redesign-plan.md](architecture/redesign-plan.md) | 平台重构的五个阶段，2026-10-02 完成 |
| [curriculum-plan-2026-10.md](architecture/curriculum-plan-2026-10.md) | 2026 年 10 月课程工作的执行顺序与各课取舍 |
| [content-depth.md](architecture/content-depth.md) | 2026-10-04 的内容审计，以及由此定下的讲解深度规范 |
| [onboarding-sources.md](architecture/onboarding-sources.md) | “开始之前”导学各章的来源与内容边界 |
| [chapter2-sources.md](architecture/chapter2-sources.md) | 第二章的来源与取舍 |
| [context-state-sources.md](architecture/context-state-sources.md) | `messages-context` 与 `application-state` 的来源 |
| [budget-memory-sources.md](architecture/budget-memory-sources.md) | `context-budget`、`context-compaction`、`persistent-memory`、`memory-lifecycle` 的来源 |

## 项目政策

| 文档 | 语言 |
| --- | --- |
| [SECURITY.md](../SECURITY.md) | 英文 |
| [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) | 英文 |
| [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) | 中英 |

## 验证记录

| 文档 | 说明 |
| --- | --- |
| [verification/live-runs-2026-10-12.md](verification/live-runs-2026-10-12.md) | 运行时双语化后，每个练习用真实模型中英文各跑一次的记录（英文） |
