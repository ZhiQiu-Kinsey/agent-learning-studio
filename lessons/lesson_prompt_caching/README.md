# 提示缓存与稳定前缀（`prompt-caching`）

先修：上下文预算与截取窗口（`context-budget`）。本课需要真实模型连接。

同一份 2700 多字的图书馆手册（`handbook.md`，教学用虚构资料）连续问几次，看服务商复用了多少开头。三组的规则、手册和问题完全相同，只改“动态行”（请求序号与发送时间）放在哪里：

| 练习 | `layout` | 动态行的位置 | 模型请求 |
| --- | --- | --- | --- |
| 动态内容在前 | `dynamic_first` | 系统提示词第一行 | `repeats` 次（默认 4） |
| 稳定前缀 | `stable_prefix` | 最后一条 user 消息末尾 | `repeats` 次 |
| 稳定前缀 + 预热 | `warmup` | 同上，先发 1 次只要求回复“已读”的预热请求 | 1 + `repeats` 次 |

`repeats` 取 3–5，`lesson.json` 的 `max_rounds` 为 6（预热 + 5 次测量）。

## 每次请求记录什么

每次请求发一条记录事件：服务商报告命中（大于 0）时是 `lesson.cache_hit`，报告为 0 时是 `lesson.cache_miss`，响应里没有缓存字段时是 `lesson.cache_unreported`。记录包括：

- `prefix_hash`：最后一条消息之前的全部消息（本课就是 system）按固定键顺序序列化后，取 sha256 前 12 位；
- `shared_prefix_chars`：这次与上一次请求序列化后从头逐字相同的字符数；
- `input_tokens`、`cached_tokens`、`cache_write_tokens`、`field`、`ratio`：由 `cache_usage.py` 的 `normalize_cache_usage` 从响应 `usage` 归一化得到；
- `elapsed_ms`：运行器在 `context.complete` 前后计时，比 `response` 事件的 `duration_ms` 多出记录事件的几毫秒。

`normalize_cache_usage` 读三种写法（字段名 2026-10-03 按各家文档核对）：

| 服务商 / 接口 | 命中字段 | 全部输入 |
| --- | --- | --- |
| OpenAI 兼容接口（含百炼） | `usage.prompt_tokens_details.cached_tokens` | `prompt_tokens`（已含命中） |
| DeepSeek 官方接口 | `usage.prompt_cache_hit_tokens` | `prompt_tokens`；没有时用命中加 `prompt_cache_miss_tokens` |
| Anthropic | `usage.cache_read_input_tokens` | `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` |

哪个缓存字段都没有、或值不是非负整数时，`cached_tokens` 为 `None`，报告写“未报告”，命中比例不计算；绝不当成 0。

## 会话标记

系统提示词第一行（动态内容在前组是第二行）有一行会话标记。`isolate_run` 为 `true`（默认）时，它是本次运行随机生成的 8 位十六进制字符串：同一次运行内不变，不破坏前缀；不同运行之间不同，上一次运行留下的缓存用不上，三组实验互不影响。设为 `false` 时固定为“不隔离”，可以观察跨运行的复用；报告的第三项检查会指出“前缀在本次运行里第一次出现却报告命中”的请求。

## 离线测试

`fixtures.py` 只服务自动化测试：它记住本次运行里发过的请求，按“与之前某次请求从头相同的字符数”编造命中数（每 2 个字符算 1 个 Token，64 个一档向下取整）。动态内容在前与稳定前缀两组按 OpenAI 兼容格式返回；“稳定前缀 + 预热”组故意不返回任何缓存字段，用来测试“未报告”。测试还用 `style` 参数切换 DeepSeek 与 Anthropic 写法。离线报告会注明数字来自夹具。

```powershell
.\.venv\Scripts\python.exe -m unittest lessons.lesson_prompt_caching.test_lesson -v
```

服务商的最小可缓存长度、命中粒度和有效期以其当前文档和响应实际报告为准，本课不写死。
