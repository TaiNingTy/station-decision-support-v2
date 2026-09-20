# 第 10 步 · Coze V2 重新设计（2026-09-20）

业主要求：Coze 上同样保留 V1 的智能体与节点（不动），V2 重新设计一套新的。第 9 步准备的是"单智能体 + 事后校验"；这一步改为沿用 V1 骨架的完整工作流设计。

## 读了什么（只读，未改动 V1 仓库）

V1.1 仓库的 `agents/01–03`、`skills/rule-check.js`、`docs/v1.1-rule-gate-plan.md`、`docs/build-playbook.md`：三个智能体（需求分析 → 检索+规则校验 → 配置+文档）；工作流里代码节点 `site-gate` + 条件分支，三种状态 PASS / BLOCKED / NEEDS_REVIEW，"缺输入不算通过"，用 token 记账证明阻断（27 m → BLOCKED，生成节点 0 token）；知识库自动检索、只引 KB、"知识库未覆盖"。

## V2 设计（`coze/v2/`）

- `DESIGN.md`：V1→V2 对照表、工作流图、八条决策（D1′–D8′）与"不声称什么"。
- 三个智能体规格与中文提示词（输出英文 JSON）：`01-site-reading`（站点解读 + 角色假设，必须待人确认）、`02-grounded-review`（只解释代码给出的规则结果与数据缺口，只引 kb-v2.0，诚实写未覆盖）、`03-configuration-brief`（只解释已计算的三档配置与驱动因素，列出给业主的问题；不推荐、不修改任何数值）。
- 两个代码节点（JavaScript，可直接粘贴进 Coze，也可本地用 Node 运行）：
  - `brief_gate.js` 输入闸门：任一 critical 规则结果 → BLOCKED；简报不完整或缺少必需的规则结果 → NEEDS_REVIEW；否则 PASS，并产出给提示词用的事实表、规则表、注意事项和检索 query。
  - `assemble_and_validate.js` 输出闸门（V2 新增）：合并三个智能体的输出为 `miami-ai-output/1.0`；任何被引用的 fact_id / rule_result_id / 知识库章节不存在，或某情景没引 RC-03 / RC-07，或角色未标"待人确认"→ INVALID，不输出答案；摘要外的数字给软提示。
- `BUILD_PLAYBOOK.zh.md`：在扣子上逐节点搭建的步骤、变量名与类型、提示词拼接方式、三次留证据的试运行（正常站 / 注入 critical 的测试夹具 / 缺规则结果）、输出闸门反例、输出落地与 Python 校验。
- 套件更新：每站新增紧凑版简报 `ai/miami/briefs/<站>.coze.json`（约 29 KB，去掉逐条来源指向，带知识库章节清单），作为工作流开始节点的输入。

## 验证

- `node coze/v2/evals/run.js`：15/15 通过（输入闸门 6 项、输出闸门 9 项）。
- 两套校验器一致性：用 JS 输出闸门合并出的 final_json 交给 Python 校验器，结果 PASS（未审校，故不可发布）。
- 这些只证明代码节点按规格工作；**没有任何模型运行**，Coze 上尚未搭建。

## 未做

在 Coze 上实际搭建与三次试运行（需业主操作）；真实输出接入网页的导出逻辑；Web 相关工作按业主要求暂停。
