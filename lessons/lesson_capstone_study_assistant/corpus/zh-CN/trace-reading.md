---
doc_id: trace-reading
title: 轨迹阅读笔记
version: 2026-10
license: 本项目原创，随仓库许可证发布
---
## 事件类型 {#events}

一次运行是一串事件：request、response、tool_call、tool_result，最后是 answer 和 done。

request 记录实际发出的请求体，response 记录服务商返回的响应。

## 跨度 {#spans}

一次模型请求或一次工具调用是一个跨度，有开始和结束时间。

同一轮次的事件归在同一个步骤下。

## 读账本 {#reading}

读账本先找耗时最长的一行，再看它是模型请求还是工具调用。

检索返回的片段数在工具结果的 hits 里，用量在响应的 usage 里。

## 回放 {#replay}

回放只读取已经记录的事件，不重新请求模型，也不重新执行工具。
