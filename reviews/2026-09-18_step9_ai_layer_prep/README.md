# 第 9 步 · 规则层与 AI 解读层准备（2026-09-18）

目标：让 V2 的 AI 层有可引用的东西再开跑。架构底稿的要求是"规则引擎执行版本化、已确认适用的规则；AI 依据已计算方案解释差异、形成风险和建议，引用 rule_id + KB 版本"。此前包里只有数值，没有带 id 的规则结果，也没有 V2 的知识库。

## 9a 规则层（阶段 `rules`）

- 规则包 `config/rules_v2.json`（rules-v2.0）：13 条，四类基础（算术恒等式 / 项目约定 / 数据质量 / 范围限制），四级状态（pass / info / warning / critical），并写明"critical 表示按当前计算不可用，AI 不得写成可用"。
- `scripts/build_miami_rules.py` 消费输入包、情景包、配置包，发布 `rules/pkg-<id>/`：`rule_results.json`（每站 15 条 + 全网 10 条，共 325 条）、`rule_pack.json`、`rules_validation.json`。登记表、编排器、就绪视图（`layers.rules`）与回归（新增 `rules_stage` 14 项）已接入。
- 当前结果：无 critical；全网高情景轨道比值 0.929 触发 RC-05 warning；21 站都带 RC-07（可建设空间假设）warning；改名三站 RC-09 warning；Government Center RC-11 / RC-12 info（观测份额 20% 对情景 3%，Metrorail / Tri-Rail 换乘流入被排除）；泊位公式逐站逐情景复算一致（RC-03）。
- 网页第 6 步新增"Deterministic rule checks"表，台账新增"Rule layer"行。

## 9b AI 解读准备（ai-kit-v2.0）

- 知识库 `kb/v2/` 四份（英文）：KB_V2_01 数据语义（12 节）、KB_V2_02 情景链与 PRT 配置方法（9 节）、KB_V2_03 解读指引（10 节，含角色假设的判读方式与禁止事项）、KB_V2_04 未决事项与责任归属（10 节）。`manifest.json` 记录版本 kb-v2.0 与各文件哈希。
- 智能体提示词 `kb/v2/AGENT_PROMPT_v2.md`（prompt-v2.0）：只用摘要与知识库、逐句引用 id、不写摘要外数字、区分来源类别、critical 不可写成可用、角色只是假设、只输出 JSON。
- 每站摘要 `ai/miami/briefs/<站>.md|json`：83 条事实（身份、半英里盘的分区 / 人口 / 就业 / 设施、内环带、时刻表、实测上车量、岗位联系潜力、全网、三档情景与配置、运营假设），每条带 fact_id、来源类别、可靠性 / 误差与来源包指向；附全部规则结果、未取得项与禁止事项。约 16 KB，可直接粘贴。
- 输出规范 `config/ai_output_schema_v2.json` 与校验脚本 `scripts/check_miami_ai_output.py`：硬检查（格式、版本一致、每个引用 id 存在、每档配置解读必引该档 RC-03 与 RC-07、角色必须待人确认、运行记录字段合法、critical 结果必须被承认），软提示（摘要外数字、"forecast / calibrated / willingness to pay / 外部标准"等措辞）。手写的格式示例 `ai/miami/examples/EXAMPLE_format_only_not_a_model_output.json` 通过校验且被标为"不可发布"。
- 操作说明 `ai/README.md`（中文）：在 Coze 新建 Bot（不动 V1.1），上传四份知识库，粘提示词，逐站粘摘要，输出存 `ai/miami/runs/`，填运行记录（手动执行如实标 `coze_ui_manual`，run_id 不伪造），跑校验，人审后才能进网页。

## 验证

[regression_results.json](regression_results.json)：见文件（新增 `rules_stage`）。生产树用编排器全量重建通过；就绪视图各阶段 DONE（walk_model 除外）；网页数据重新导出。

## 未做

模型尚未运行（需业主在 Coze 上操作）；输出接入网页的导出逻辑等有真实输出后再写；步行模型仍暂停。
