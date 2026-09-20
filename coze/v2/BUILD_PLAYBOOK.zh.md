# 搭建手册 · 在扣子上新建 V2 工作流 `station_decision_v2`

原则：**V1 的 Bot 和 V1.1 的工作流 `station_gate_v1` 一个都不动**。V2 是新建的第三个产物，用自己的知识库。设计说明见 [DESIGN.md](DESIGN.md)。

一句话逻辑：**AI 读取与判读，代码核验，人决定。** G1、G2 两个读取智能体直接读 GIS 要素（道路、铁路与导轨、zoning、现状用地、地块、热度代理栅格与图片、街区组）；后面三个智能体沿用 V1 的骨架；四个代码节点把关。热力图是用公开数据推算的活动强度**代理**，与 zoning 结合着读，只作**辅助证据**。

```
开始(station_id) → HTTP×3 → 代码 gis-gate → 分支
   ├─ 通过 → 知识库 → LLM G1 GIS读取 → LLM G2 热度与人口读取 → 代码 gis-verify
   └─ 不通过 → 跳过（空间证据不可用，不阻断）
→ 代码 brief-gate → 分支
   ├─ 通过 → LLM1 站点解读 → 知识库 → LLM2 依据与规则复核 → LLM3 配置解释 → 代码 assemble-and-validate → 分支 → 结束
   └─ 不通过 → 结束(BLOCKED / NEEDS_REVIEW)      ← LLM1–3 不运行，0 token
```

## S0 前提：输入文件要能被公网访问

工作流用 HTTP 节点按站点编号去拉文件，地址是 `https://tainingty.github.io/station-decision-support-v2/gis/<站点>/`，下面有 `g1_input.json`、`g2_input.json`、`brief.coze.json`、`heat.png`。这些文件由 `python3 scripts/export_miami_gis_agent_inputs.py` 生成并镜像到 `docs/gis/`，**push 之后**才在线上可取。自检：浏览器打开 `…/gis/MIA-MM-12/heat.png` 能看到图。

如果暂时不想用 HTTP 节点，也可以把开始节点改成四个 String 输入，手动粘贴三个 JSON 的全文和图片地址，其余节点不变。

## S1 新建知识库（15 分钟）

1. 资源库 → 知识库 → 新建 `Station-KB-V2`，类型"文本"。
2. 上传 `kb/v2/` 下**六个** `KB_V2_*.md`（01 数据语义、02 情景与 PRT 配置方法、03 解读指引、04 未决事项、05 GIS 读取指引、06 图层图例）。不要上传 `AGENT_PROMPT_v2.md` 和 `manifest.json`。
3. 自动分段，处理到状态变绿。自检两问："are observed boardings a calibration target" 应命中 KB_V2_01 的 DS-07；"is the existing guideway an obstacle" 应命中 KB_V2_05 的 GR-04。

## S2 新建工作流（约 2.5 小时）

资源库 → 工作流 → 新建 `station_decision_v2`。知识库检索设置统一为：**自动调用、混合检索、最小匹配度 0.15、结果重排开、最大召回 20**。

**① 开始**：输入变量 `station_id`（String）。

**② 三个 HTTP 请求节点**（GET）：URL 分别为 `https://tainingty.github.io/station-decision-support-v2/gis/{{station_id}}/g1_input.json`、`…/g2_input.json`、`…/brief.coze.json`；输出取响应正文，变量名 `g1_input`、`g2_input`、`station_brief`（String）。

**③ 代码节点 `gis-gate`**：输入 `g1_input`、`g2_input`；代码粘贴 [`nodes/gis_gate.js`](nodes/gis_gate.js) 全文；输出变量：`gis_status` String、`allow_reading` Boolean、`gis_problems` Array<String>、`station_name` String、`heat_image_url` String，以及十一张表（全部 String）：`g1_roads_table`、`g1_rail_table`、`g1_zoning_table`、`g1_landuse_table`、`g1_parcels_table`、`g1_parcel_groups`、`g1_facts_table`、`g2_cells_table`、`g2_blockgroups_table`、`g2_zoning_table`、`g2_facts_table`，另有 `kb_query_gis` String。

**④ 条件分支**：`allow_reading` 等于 true 走"读取"支路，否则直接连到 ⑧（空间证据是辅助的，不通过也不阻断）。

**⑤ 知识库节点**（读取支路）：query 引用 `kb_query_gis`，输出 `kb_chunks_gis`。

**⑥ LLM G1 · GIS 读取**：模型豆包 2.0 Pro；系统提示词用 [`agents/G1-gis-reader.md`](agents/G1-gis-reader.md)；用户提示词：
`站点：{{station_name}}\n\n道路分组：\n{{g1_roads_table}}\n\n铁路与导轨：\n{{g1_rail_table}}\n\nzoning 多边形：\n{{g1_zoning_table}}\n\n现状用地类别：\n{{g1_landuse_table}}\n\n地块：\n{{g1_parcels_table}}\n\n地块分组汇总：\n{{g1_parcel_groups}}\n\n汇总数字：\n{{g1_facts_table}}\n\n知识库内容：\n{{kb_chunks_gis}}`
输出变量 `g1_json`（String）。

**⑦ LLM G2 · 热度与人口读取**：选豆包的**视觉理解模型**，图片输入引用 `heat_image_url`；系统提示词用 [`agents/G2-heat-residents-reader.md`](agents/G2-heat-residents-reader.md)；用户提示词：
`站点：{{station_name}}\n\n热度栅格格值表：\n{{g2_cells_table}}\n\n街区组人口估计：\n{{g2_blockgroups_table}}\n\nzoning 多边形：\n{{g2_zoning_table}}\n\n汇总数字：\n{{g2_facts_table}}\n\n知识库内容：\n{{kb_chunks_gis}}`
输出变量 `g2_json`（String）。如果视觉模型装不下长表，就拆成两个节点：视觉模型只看图、输出纯文字观察，文字模型读表并把那段观察放进 `visual_observations_unverified`。

**⑧ 代码节点 `gis-verify`**（读取支路末尾）：输入 `g1_input`、`g2_input`、`g1_json`、`g2_json`；代码 [`nodes/gis_verify.js`](nodes/gis_verify.js)；输出 `evidence_status` String、`allow_evidence` Boolean、`evidence_problems` Array<String>、`evidence_soft_warnings` Array<String>、`spatial_evidence_json` String、`evidence_digest` String、`evidence_object_ids` Array<String>。跳过读取支路时，给下游一个固定的 `evidence_digest`：`SPATIAL EVIDENCE NOT AVAILABLE: gis-gate did not pass.`（可用一个"文本处理"节点或变量聚合节点实现）。

**⑨ 代码节点 `brief-gate`**：输入 `station_brief`；代码 [`nodes/brief_gate.js`](nodes/brief_gate.js)；输出 `workflow_status`、`allow_interpretation`、`blocked_reasons`、`station_id`、`station_name`、`facts_table`、`rules_table`、`caveats`、`kb_query`。

**⑩ 条件分支**：`allow_interpretation` 等于 true 才往下；否则 → 结束节点输出 `workflow_status` 与 `blocked_reasons`。**这条支路上不放任何 LLM 节点**。

**⑪ LLM1 站点解读**：系统提示词 [`agents/01-site-reading.md`](agents/01-site-reading.md)；用户提示词 `站点：{{station_name}}\n\n事实表：\n{{facts_table}}\n\n规则结果表：\n{{rules_table}}\n\n注意事项：\n{{caveats}}\n\n空间证据（辅助）：\n{{evidence_digest}}`；输出 `site_json`。

**⑫ 知识库节点**：query 引用 `kb_query`，输出 `kb_chunks`。

**⑬ LLM2 依据与规则复核**：[`agents/02-grounded-review.md`](agents/02-grounded-review.md)；用户提示词含 `facts_table`、`rules_table`、`site_json`、`evidence_digest`、`kb_chunks`；输出 `review_json`。

**⑭ LLM3 配置解释**：[`agents/03-configuration-brief.md`](agents/03-configuration-brief.md)；用户提示词含 `facts_table`、`rules_table`、`site_json`、`review_json`、`evidence_digest`、`kb_chunks`；输出 `config_json`。

**⑮ 代码节点 `assemble-and-validate`**：输入 `station_brief`、`site_json`、`review_json`、`config_json`、`spatial_evidence_json`、`evidence_object_ids`、`gis_status`；代码 [`nodes/assemble_and_validate.js`](nodes/assemble_and_validate.js)；输出 `output_status`、`allow_output`、`problems`、`soft_warnings`、`final_json`。

**⑯ 条件分支 + 两个结束节点**：`allow_output` 为 true → 输出 `final_json`；否则输出固定文字 `REJECTED BY OUTPUT GATE` 与 `problems`。

五个 LLM 节点的提示词末尾都保留"严格只输出一个 JSON 对象"。

## S3 留证据的试运行

| 试运行 | 怎么做 | 期望 | 要截图 / 记录 |
|---|---|---|---|
| A 正常站 | `station_id = MIA-MM-12` | gis-gate PASS → G1、G2 → gis-verify VALID → brief-gate PASS → LLM1–3 → 输出闸门 VALID | 画布全绿、各节点 token 数、`final_json` |
| B 注入 critical | 把 ② 里 `station_brief` 临时改成粘贴 `coze/v2/evals/fixtures/MIA-MM-12.injected_critical.coze.json` 全文（文件内注明 TEST FIXTURE） | brief-gate = BLOCKED，**LLM1–3 未运行，0 token** | LLM 节点为灰、token 为 0、`blocked_reasons` 为 `NET\|high\|RC-05` |
| C 缺规则结果 | 同上，粘贴 `MIA-MM-12.missing_rule.coze.json` | brief-gate = NEEDS_REVIEW | `blocked_reasons` 列出 `MIA-MM-12\|-\|RC-07` |
| D 导轨被读成障碍 | 单独试运行节点 ⑧：`g1_json` 用 `fixtures/tampered_g1_json.guideway_as_obstacle.json`，`g2_json` 用 `wellformed_gis_readings.json` 里的 `g2_json`，两个 input 用线上文件内容 | `evidence_status = INVALID`，问题里写明导轨是待转换设施 | 节点输出 |
| E 编造引用 | 单独试运行节点 ⑮：`site_json` 用 `fixtures/tampered_site_json.invented_fact_id.json` | `output_status = INVALID`，点名 `MIA-MM-12.F999` | 节点输出 |

## S4 保存真实输出并校验

1. 把试运行 A 的 `final_json` 原样存为 `ai/miami/runs/MIA-MM-12/<YYYYMMDD-HHMM>.json`，填 `run_record`：`execution_mode` 填 `coze_ui_manual`，`workflow_or_bot` 写工作流名与版本，`model` 写实际模型（G2 用了视觉模型就两个都写），`run_at_utc`、`operator` 照实，`run_id` 平台没返回就保持 `null`，`retrieval_hits` 照知识库节点显示的命中填。
2. 本地校验：

```sh
python3 scripts/check_miami_ai_output.py ai/miami/runs/MIA-MM-12/<文件名>.json
```

校验器除了查 id、版本和措辞，还会把 G1 的角色判读与数据包里的规则提示逐一对比，给出一致率并列出分歧项，供你人工审看。一致率只是信号，不是目标。
3. 人工审校后把 `review.status` 改成 `reviewed_ok` 或 `reviewed_with_edits`。之后再跑 MIA-MM-09、MIA-MM-21、MIA-MM-01、MIA-MM-02。

## 常见坑

- **HTTP 节点取到的是 404**：还没 push，或 GitHub Pages 还没重新部署；先在浏览器里打开地址确认。
- **G1 输入太长**：地块表最多 150 行，整份输入约 8 千 token；如果模型上下文不够，换更长上下文的模型，不要删表。
- **LLM 输出前后带解释文字**：闸门会判 INVALID，回到提示词末尾强调"只输出 JSON"。
- **想改规则阈值或地块分组**：不要在 Coze 里改。改仓库里的 `config/rules_v2.json` 或 `config/gis_objects_v1.json`，重跑 `build_all_miami.py`、`build_miami_ai_kit.py`、`export_miami_gis_agent_inputs.py`，再 push。
- **数据包重建之后**：输入文件会变；旧输出的版本号或 id 对不上，会被校验器拦下，这是设计如此。
