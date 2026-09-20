# 搭建手册 · 在扣子上新建 V2 工作流 `station_decision_v2`

原则：**V1 的 Bot 和 V1.1 的工作流 `station_gate_v1` 一个都不动**。V2 是新建的第三个产物，用自己的知识库。设计说明见 [DESIGN.md](DESIGN.md)。

结构（与 V1.1 同一副骨架：代码闸门 + 条件分支 + 三个智能体 + 知识库，另加一个输出闸门）：

```
开始 → 代码 brief-gate → 条件分支
   ├─ 通过 → LLM1 站点解读 → 知识库 → LLM2 依据与规则复核 → LLM3 配置解释 → 代码 assemble-and-validate → 条件分支
   │                                                                          ├─ 有效 → 结束(final_json)
   │                                                                          └─ 无效 → 结束(被输出闸门拒绝 + problems)
   └─ 不通过 → 结束(BLOCKED / NEEDS_REVIEW + blocked_reasons)   ← 不经过任何 LLM，0 token
```

## S1 新建知识库（15 分钟）

1. 资源库 → 知识库 → 新建，命名 `Station-KB-V2`，类型"文本"。
2. 上传仓库 `kb/v2/` 下四个文件：`KB_V2_01_data_semantics.md`、`KB_V2_02_prt_configuration_method.md`、`KB_V2_03_interpretation_guidance.md`、`KB_V2_04_open_items_and_ownership.md`。不要上传 `AGENT_PROMPT_v2.md` 和 `manifest.json`。
3. 分段：自动分段（文档每节以 `## DS-01` 这类标题开头，便于命中章节号）。处理到状态变绿。
4. 自检：在知识库测试框里问 "are observed boardings a calibration target"，应命中 KB_V2_01 的 DS-07。

## S2 新建工作流（约 1.5 小时）

资源库 → 工作流 → 新建 `station_decision_v2`。

**① 开始**：新增输入变量 `station_brief`（String）。

**② 代码节点 `brief-gate`**（JavaScript）
- 输入：`station_brief` ← 引用开始节点的 `station_brief`。
- 代码：粘贴 [`nodes/brief_gate.js`](nodes/brief_gate.js) 全文。
- 输出变量（名称与类型照填）：`workflow_status` String、`allow_interpretation` Boolean、`blocked_reasons` Array<Object>、`station_id` String、`station_name` String、`facts_table` String、`rules_table` String、`caveats` String、`kb_query` String。（`allowed_fact_ids` 等其余字段工作流里用不到，可不声明。）

**③ 条件分支**：条件 `allow_interpretation` 等于 true → 走"通过"分支；否则走"不通过"分支。

**④ 不通过分支 → 结束节点**：输出 `workflow_status` 与 `blocked_reasons`。这个分支上**不放任何 LLM 节点**，这就是闸门。

**⑤ LLM1 站点解读**（通过分支）
- 模型：豆包 2.0 Pro（与 V1 一致）。输入：`station_name`、`facts_table`、`rules_table`、`caveats`。
- 系统提示词：[`agents/01-site-reading.md`](agents/01-site-reading.md) 的 System prompt 全文。
- 用户提示词：`站点：{{station_name}}\n\n事实表：\n{{facts_table}}\n\n规则结果表：\n{{rules_table}}\n\n注意事项：\n{{caveats}}`
- 输出变量：`site_json`（String）。

**⑥ 知识库节点**：选择 `Station-KB-V2`；query 引用 `kb_query`；检索设置同 V1.1 修复后的配置——**自动调用、混合检索、最小匹配度 0.15、结果重排开**；最大召回建议 **20**（V2 的章节很短，10 条容易漏）。输出 `kb_chunks`。

**⑦ LLM2 依据与规则复核**
- 输入：`facts_table`、`rules_table`、`caveats`、`site_json`、`kb_chunks`。
- 系统提示词：[`agents/02-grounded-review.md`](agents/02-grounded-review.md)。
- 用户提示词：`事实表：\n{{facts_table}}\n\n规则结果表：\n{{rules_table}}\n\n上游站点解读：\n{{site_json}}\n\n检索到的知识库内容：\n{{kb_chunks}}`
- 输出变量：`review_json`（String）。

**⑧ LLM3 配置解释与决策要点**
- 输入：`facts_table`、`rules_table`、`caveats`、`site_json`、`review_json`、`kb_chunks`。
- 系统提示词：[`agents/03-configuration-brief.md`](agents/03-configuration-brief.md)。
- 用户提示词：`事实表：\n{{facts_table}}\n\n规则结果表：\n{{rules_table}}\n\n站点解读：\n{{site_json}}\n\n依据与规则复核：\n{{review_json}}\n\n知识库内容：\n{{kb_chunks}}`
- 输出变量：`config_json`（String）。

**⑨ 代码节点 `assemble-and-validate`**（JavaScript）
- 输入：`station_brief`（引用开始节点）、`site_json`、`review_json`、`config_json`。
- 代码：粘贴 [`nodes/assemble_and_validate.js`](nodes/assemble_and_validate.js) 全文。
- 输出变量：`output_status` String、`allow_output` Boolean、`problems` Array<String>、`soft_warnings` Array<String>、`final_json` String。

**⑩ 条件分支**：`allow_output` 等于 true → 结束节点输出 `final_json`；否则 → 结束节点输出固定文字 `REJECTED BY OUTPUT GATE` 与 `problems`。

三个 LLM 节点都要在提示词末尾保留"严格只输出一个 JSON 对象"；输出闸门能容忍 ```json 代码块，但不能容忍解释文字把 JSON 截断。

## S3 三次试运行（这是要留证据的部分）

| 试运行 | `station_brief` 粘贴什么 | 期望 | 要截图 / 记录 |
|---|---|---|---|
| A 正常站 | `ai/miami/briefs/MIA-MM-12.coze.json` 全文 | `brief-gate` = PASS → 三个 LLM 运行 → `assemble-and-validate` = VALID → 输出 final_json | 画布全绿 + 各节点 token 数 + final_json |
| B 注入 critical | `coze/v2/evals/fixtures/MIA-MM-12.injected_critical.coze.json`（文件内已注明 TEST FIXTURE） | `brief-gate` = BLOCKED → 走不通过分支 → **三个 LLM 节点未运行（0 token）** | 画布上 LLM 节点为灰 + token 为 0 + blocked_reasons 里是 `NET\|high\|RC-05` |
| C 缺规则结果 | `coze/v2/evals/fixtures/MIA-MM-12.missing_rule.coze.json` | `brief-gate` = NEEDS_REVIEW（缺的不算通过） | blocked_reasons 列出 `MIA-MM-12\|-\|RC-07` |

输出闸门的反例可单独试运行节点 ⑨：`station_brief` 用正常简报，`site_json` 用 `coze/v2/evals/fixtures/tampered_site_json.invented_fact_id.json` 的内容，另两项用 `wellformed_parts.json` 里的 `review_json`、`config_json` → 期望 `output_status = INVALID`，`problems` 点名 `MIA-MM-12.F999`。

## S4 保存真实输出并校验

1. 把试运行 A 的 `final_json` 原样存为 `ai/miami/runs/MIA-MM-12/<YYYYMMDD-HHMM>.json`。
2. 填 `run_record`：`execution_mode` 填 `coze_ui_manual`（在界面里手动试运行）；`workflow_or_bot` 保持 `station_decision_v2` 并写上你的工作流版本；`model` 写实际模型名；`run_at_utc`、`operator` 照实；`run_id` 只有平台返回了才填，否则保持 `null`；`retrieval_hits` 照知识库节点显示的命中填（文档名 + 章节）。
3. 本地再校验一次（Python 校验器比工作流里的输出闸门多查版本一致性与措辞）：

```sh
python3 scripts/check_miami_ai_output.py ai/miami/runs/MIA-MM-12/<文件名>.json
```

4. 人工审校后把 `review.status` 改成 `reviewed_ok` 或 `reviewed_with_edits`。之后再跑其余四个代表站：MIA-MM-09、MIA-MM-21、MIA-MM-01、MIA-MM-02。

## 常见坑

- **粘贴的是 `.coze.json` 不是 `.md`**：代码节点要解析 JSON；`.md` 只给单智能体备用方案用。
- **LLM 输出前后带解释文字**：输出闸门会判 INVALID，回到提示词末尾强调"只输出 JSON"。
- **知识库没命中章节号**：把最大召回调到 20；确认四份文档都已处理完成。
- **想改规则阈值**：不要在 Coze 里改。阈值在仓库 `config/rules_v2.json`，改完重跑 `build_all_miami.py` 与 `build_miami_ai_kit.py`，简报会带上新结果。
- **数据包重建之后**：简报要重新生成；旧输出的版本号或 id 对不上，会被校验器拦下，这是设计如此。
