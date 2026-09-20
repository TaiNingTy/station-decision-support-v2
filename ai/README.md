# AI 解读层（V2 · 迈阿密）· 操作说明

状态（2026-09-18）：**准备就绪，尚未运行**。知识库、提示词、每站输入摘要、输出规范与校验脚本都已生成；还没有任何模型输出。网页上的 AI 状态因此仍是 NOT_RUN，直到有经过校验和审校的输出。

## 这一层做什么、不做什么

模型读一份"站点摘要"（brief），里面是该站全部可用事实（每条带 `fact_id`）和确定性规则结果（每条带 `rule_result_id`），然后输出一个固定格式的 JSON：站点解读、数据缺口与可靠性、角色假设（必须由人确认）、三档配置的解释与风险、给业主的问题、知识库未覆盖之处。**它不算数、不定阈值、不做决定**；数字来自数据包，阈值来自规则包，决定归人。

## 文件

| 路径 | 内容 |
|---|---|
| `kb/v2/KB_V2_01…06.md` | 知识库六份（英文）：数据语义、情景与 PRT 配置方法、解读指引、未决事项与责任归属、GIS 读取指引、图层图例（由 `scripts/build_miami_kb_legends.py` 从图层自身生成）。版本 `kb-v2.1`，哈希在 `kb/v2/manifest.json` |
| `ai/miami/gis/<站>/` | 两个读取智能体的输入：`g1_input.json`（道路、铁路与导轨、zoning、现状用地、地块）、`g2_input.json`（热度代理格值、街区组、zoning）、`heat.png`（热度代理图）、`brief.coze.json`；同时镜像到 `docs/gis/` 供 Coze 的 HTTP 节点拉取。由 `scripts/export_miami_gis_agent_inputs.py` 生成 |
| `kb/v2/AGENT_PROMPT_v2.md` | 智能体系统提示词（英文），版本 `prompt-v2.1` |
| `config/rules_v2.json` → 阶段 `rules` | 规则包 `rules-v2.0`：13 条算术恒等式 / 项目约定 / 数据质量 / 范围限制，逐站逐情景给出可引用的 `rule_result_id` |
| `config/ai_output_schema_v2.json` | 模型输出的唯一合法格式 |
| `ai/miami/briefs/<站>.md` / `.json` | 每站输入摘要（约 70 条事实 + 全部规则结果）；`.md` 用于粘贴，`.json` 供校验 |
| `ai/miami/kit_manifest.json` | 套件版本 `ai-kit-v2.1`、所用数据包 ID、各文件哈希 |
| `scripts/check_miami_ai_output.py` | 输出校验：格式、版本、每个引用的 fact_id / rule_result_id / KB 章节是否存在、必引规则、禁止措辞与未出现在摘要中的数字（软提示） |
| `ai/miami/runs/<站>/<日期时间>.json` | 模型输出落地位置（目前为空） |

## 在 Coze 上怎么跑

**主路径：新建 V2 工作流 `station_decision_v2`**（保留 V1 的骨架：三个智能体 + 代码闸门 + 条件分支 + 知识库，另加输出闸门）。设计见 [`coze/v2/DESIGN.md`](../coze/v2/DESIGN.md)，逐步搭建见 [`coze/v2/BUILD_PLAYBOOK.zh.md`](../coze/v2/BUILD_PLAYBOOK.zh.md)，三个智能体的提示词在 `coze/v2/agents/`，两个代码节点在 `coze/v2/nodes/`（本地评测 `node coze/v2/evals/run.js`，15/15）。工作流的输入是 `ai/miami/briefs/<站>.coze.json`。V1 的 Bot 与 V1.1 的工作流不做任何改动。

**备用路径：单智能体手动方式**（下面这一节）。只在想快速试一站、还没搭好工作流时用；它没有代码闸门，只有事后的 Python 校验。

## 备用：单智能体手动方式

1. **新建**一个 Bot 或工作流，不要改动 V1.1 的那个。
2. 新建知识库，上传 `kb/v2/` 下的四份 `KB_V2_*.md`；检索设为每轮自动调用、混合检索、低匹配阈值（同 V1.1 修复后的设置）。
3. 把 `kb/v2/AGENT_PROMPT_v2.md` 全文作为系统提示词。
4. 一次一站：把 `ai/miami/briefs/<站>.md` 全文粘贴为用户消息，要求只输出 JSON。先跑五个代表性站点：MIA-MM-09 Government Center（枢纽）、MIA-MM-12 Bayfront Park、MIA-MM-21 Brickell（流向不平衡）、MIA-MM-01 School Board（端点）、MIA-MM-02 Adrienne Arsht Center（改名站）。
5. 把输出原样存为 `ai/miami/runs/<站>/<YYYYMMDD-HHMM>.json`，并填 `run_record`：平台、`execution_mode` 填 `coze_ui_manual`（界面手动）或 `coze_api`、Bot/工作流名称与版本、模型名、运行时间（UTC）、操作人；`run_id` 只有平台真的返回了才填，否则留 `null`；`retrieval_hits` 照平台显示的检索命中填写，没有就留空数组。
6. 运行校验：

```sh
python3 scripts/check_miami_ai_output.py ai/miami/runs/MIA-MM-12/20260920-1015.json
```

7. 校验 PASS 后由人审校，把 `review.status` 改为 `reviewed_ok` 或 `reviewed_with_edits`（有改动写在 `notes`）。只有这两种状态的输出才会导出到网页，并标注"批跑、已审校、手动执行"。

## 诚实边界

- 不存在的运行不写；手动执行如实标 `coze_ui_manual`；不伪造 run_id。
- 模型引用的每个 id 都会被程序核对；引用不存在的 id 直接 FAIL。
- 规则包不是法规或行业标准；`critical` 结果不允许被写成"可用"。
- 摘要里的数字来自当前数据包；数据包重建后需重新生成摘要（`python3 scripts/build_miami_ai_kit.py`），旧输出因版本不符会被校验拦下。
