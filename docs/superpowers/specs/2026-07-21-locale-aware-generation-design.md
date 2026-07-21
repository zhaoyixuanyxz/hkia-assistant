# 跟 UI Locale 的生成内容（对话 / 报告 / 兜底）

**日期：** 2026-07-21  
**状态：** 已批准

## 背景

前端已通过 next-intl 支持 `zh-CN` / `en` / `zh-TW`（路由、`messages/*.json`、右上角切换）。  
后端顾问对话、画像摘要、报告 JSON、免责声明与失败/空正文兜底仍写死「中文输出」，且请求未携带 `locale`。  
结果：用户切到 English UI 后，界面是英文，助手回复与报告仍是中文（需求文档已要求支持英文）。

## 目标

- **跟 UI 语言走**：当前界面 locale 为 `en` / `zh-TW` / `zh-CN` 时，**本轮新生成**的对话正文、侧栏相关摘要字段、报告正文、标准免责声明、空回复/管道失败兜底、报告解析失败占位，均使用对应语言。
- **中途切换只影响新内容**：历史聊天气泡不改写；重新生成报告时用**当前** UI locale。
- **一次覆盖三语**：`zh-CN`、`en`、`zh-TW` 与现有语言切换对齐。
- **兼容旧客户端**：未传 `locale` 时默认 `zh-CN`。

## 非目标

- 不按用户消息自动检测语言（不做「用户英文问、UI 中文仍用英文回」）。
- 不翻译或重写历史消息。
- 不在 `conversations` 表持久化 `locale`。
- 不为整份主 system prompt 维护三份完整翻译包。
- 不擅自翻译产品正式名称 / 计划代码 / 条款专名（可保留原文，必要时括号附短释义）。
- 本迭代不强制把所有 HTTP `detail` 错误文案三语化（表单校验等可仍走前端 i18n 或既有中文 detail）。

## 方案选择

采用 **请求级 locale（方案 1）**：

- 前端每次发消息、编辑消息重跑、生成报告时，在 JSON body 中带上当前 `useLocale()`。
- 后端 `normalize_locale()` 校验后注入 prompt / 文案表。
- 不采用会话绑定 locale；不采用整包 prompt 三语资源文件。

## 架构

```text
[UI locale] → POST body.locale → FastAPI
                                → normalize_locale()
                                → prompts + disclaimer/fallback tables
                                → LLM（仅约束本轮输出语言）
```

语言不入库；同一会话可因用户切换 UI 而出现历史中文 + 新英文混排（已接受）。

## API 契约

### 支持的 locale

`zh-CN` | `en` | `zh-TW`  
非法或缺失 → `zh-CN`。

### 对话

- `MessageCreate` 增加可选字段：`locale: str | None = None`
- 作用于：
  - `POST /conversations/{id}/messages`
  - `PATCH /conversations/{id}/messages/{message_id}`（编辑后重跑同一路径）

### 报告

- `POST /conversations/{id}/reports/generate` 接受可选 JSON body：`{ "locale": "…" }`
- 无 body 或无字段时默认 `zh-CN`

### 前端

- `chat` 发送、编辑保存、报告生成处读取 `useLocale()` 写入 body。
- `apiFetch` 无需全局强制加 header；以 body 为准即可。

## Prompt 与输出语言

### 策略

- 品牌边界、合规、篇幅等**规则类** system 文案继续以中文维护（模型可理解）。
- 去掉写死的「必须用中文」；改为按 locale 注入 **输出语言块**。
- JSON 字段**键名**保持英文；**值**（title、insights、summary_text 等）使用目标语言。

### 语言块要求（摘要）

| locale | 输出 |
|--------|------|
| `zh-CN` | 简体中文 |
| `zh-TW` | 繁体中文（不另建简繁转换词典，依赖模型自然繁体） |
| `en` | 专业、审慎的顾问英语；产品正式名/计划代码保持知识库原文，必要时括号短释义 |

### 改动触及

- `build_insurance_expert_system(..., locale)`
- `chat_body_rewrite_system(..., locale)`
- 画像结构化 / 滚动摘要 / 双线融合 / `REPORT_JSON_SYSTEM` 等凡写「中文字符串」处改为「目标语言」
- `conversation_runner`、`report_graph`、长度改写路径将 `locale` 传到全部相关 LLM 调用

### 长度

- 继续使用现有字符数 `min_len` / `max_len` 区间（中英共用）；本迭代不单独为英文开字数表。

## 免责声明、失败/空回复、报告兜底

后端用按 locale 索引的文案表（缺省 `zh-CN`），至少覆盖：

| 键 / 函数 | 用途 |
|-----------|------|
| `STANDARD_DISCLAIMER` / `SHORT_DISCLAIMER` | 对话尾注、报告 disclaimer、剥离识别 |
| `CHAT_ASSISTANT_EMPTY_BODY_FALLBACK` 等 | 空正文兜底 |
| `assistant_pipeline_failure_reply` | 「助手暂时不可用…」 |
| `report_fallback(locale=…)` | 报告解析失败占位各字段 |
| 长度补齐后缀（可选） | 过短正文 pad，按语言各备一小套 |

API 形态示例：`disclaimer_for(locale)`、`failure_reply_for(locale)`、`ensure_disclaimer_text(..., locale)`、`report_fallback(locale=…)`。  
追加免责声明时只追加**当前语言**标准声明。

### 前后端剥离同步

- 后端 `_DISCLAIMER_SUFFIXES_STRIP` 与前端 `frontend/lib/chat-disclaimer.ts` 的 `DISCLAIMER_SUFFIXES` **同时收录三语**标准/短声明，保证历史中文消息与新英文消息都能正确拆 footer。

## 测试与验收

### 自动化（可 mock LLM）

1. `normalize_locale`：合法三语；非法 → `zh-CN`
2. 三语 disclaimer / failure / report_fallback 非空且互不相同
3. Prompt 组装：`en` / `zh-TW` 含对应输出约束，且无写死「必须中文」
4. Message / report API 接受 `locale`；缺省兼容
5. 中英繁 disclaimer 后缀均可从正文剥离

### 前端

1. 发送 / 编辑 / 生成报告请求 body 含当前 locale
2. `splitAssistantMessage` 对英文 disclaimer 可拆 footer

### 手工

1. English UI → 新回复与免责声明为英文；历史中文不变
2. 同会话切回简体 → 新回复变简体
3. English 下生成报告 → 叙述英文化；产品正式名可保留原文
4. 繁体 UI 抽查一轮
5. 触发失败/空正文时，兜底语言与 UI 一致

## 风险与备注

- 英文下字符长度区间可能导致改写更频繁；若线上体验差，再单独调英文区间（非本迭代必做）。
- 繁体质量依赖模型；不做额外 OpenCC 管线。
- 合规英文 disclaimer 需与法务/产品口径一致；实现时提供清晰英文稿，后续可替换文案表而不改逻辑。

## 实现顺序（供计划引用）

1. `normalize_locale` + 文案表 + disclaimer 剥离三语
2. Prompt / runner / report_graph 传 locale
3. API schema + 路由接线
4. 前端 body 传 locale + `chat-disclaimer` 同步
5. 测试与手工验收
