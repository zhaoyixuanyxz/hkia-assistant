# DeepSeek V4 Pro + 按场景思考模式

**日期：** 2026-07-09  
**状态：** 已批准

## 背景

DeepSeek 将于 2026/07/24 弃用 `deepseek-chat` / `deepseek-reasoner`。官方推荐改用 `deepseek-v4-pro` 或 `deepseek-v4-flash`。V4 默认开启思考模式；若不显式关闭，对话链路会变慢、变贵。

## 目标

- 所有生成式 LLM 调用统一为 `deepseek-v4-pro`，沿用现有 `DEEPSEEK_API_KEY`
- 对话链路显式关闭思考
- 报告链路（双线画像融合 + Report Architect）显式开启思考

## 非目标

- 不更换 API Key / base URL 协议
- 不改 Embedding
- 不改 Prompt 文案与前端
- 不做对话/报告双模型拆分（Flash vs Pro）

## 调用矩阵

| 调用 | 方法 | thinking | reasoning_effort |
|------|------|----------|------------------|
| Insurance Expert | `chat` | disabled | — |
| 正文改写 | `rewrite_chat_body_to_length` | disabled | — |
| Profile Architect（对话内） | `complete_json_text` | disabled | — |
| Rolling summary | `chat` | disabled | — |
| 双线画像融合 | `complete_json_text` | enabled | high（可配置） |
| Report Architect | `complete_json_text` | enabled | high（可配置） |

## 设计

### 配置

- 默认 `deepseek_chat_model = "deepseek-v4-pro"`（仍兼容 `DEEPSEEK_CHAT_MODEL` / `DEEPSEEK_MODEL`）
- `deepseek_report_thinking: bool = True`（`DEEPSEEK_REPORT_THINKING`）
- `deepseek_report_reasoning_effort: str = "high"`（`DEEPSEEK_REPORT_REASONING_EFFORT`，允许 `high` / `max`）

### LLM 层

- `DeepSeekLLM` 内部统一 `_create_completion(..., *, thinking_enabled: bool)`
- 思考开启：`extra_body={"thinking": {"type": "enabled"}}` + `reasoning_effort`；不传 temperature
- 思考关闭：`extra_body={"thinking": {"type": "disabled"}}`；保留现有 temperature
- `complete_json_text(..., *, thinking: bool | None = None)`：默认非思考；报告侧传 `thinking=True`（受配置开关约束）
- 最终答案仍取 `content`；现有 `_chat_completion_assistant_text` 兜底保留；不把 `reasoning_content` 写入多轮历史

### 调用方

- `report_integrated_profile.fuse_profile_summary_dual_source` → `thinking=True`
- `report_graph.report_architect` → `thinking=True`
- 对话侧保持默认

### 验证

- 单元测试：默认模型、对话请求带 disabled、报告请求带 enabled
- 现有 pytest 套件通过（MockLLM）
- 若本地配置了真实 `DEEPSEEK_API_KEY`：手跑或脚本验证对话 + 报告闭环
