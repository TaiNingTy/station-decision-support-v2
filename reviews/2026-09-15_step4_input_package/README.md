# 第 4 步 · 站点输入包（2026-09-15）

依据字段契约 §2、§8、§10、§11 与规则文档总原则实现。阶段 `input_package`，脚本 `scripts/build_miami_input_package.py`，包目录 `input_package/pkg-<id>/`，指针 `input_package_current.json`。

## 内容

- 每站一份输入包（`stations/<station_id>.json`，21 份）加一份全站文件与索引。每站包含：站点主表的身份、几何、映射状态与外部连接；三个环带与累计盘上并列的**法定分区画像、ACS 人口画像、LODES 岗位画像**；参考点分区匹配；OD 联系潜力（非排他）；Miami 特定输入占位；角色分类占位（`NOT_CLASSIFIED`）；配置占位（`NOT_CALCULATED`）。
- **只复制不重算**：数值块是产出层信封的原文，另加 `evidence_source`（产出层包、证据文件、证据 ID 模式）。结构检查要求每个 `value` 都带 `value_status`；这项检查在首次运行时抓到人口层与就业层三处密度、比率字段缺状态，已在源头补齐后重建两层。
- **版本锁定**：`component_versions` 记录站点主表哈希与空间连接、人口、就业三层的包 ID 与 manifest 哈希；校验要求锁定值等于构建时的当前指针。
- **AI 使用规则**随包携带：场地事实引证据 ID，规范判断引规则 ID 与知识库版本，方案比较引计算结果 ID；禁止把密度当人/小时、把覆盖份额当分配权重、平均中位数、把 LODES 当出行量、由收入推断支付意愿、整类剔除分区。
- **配置输入摘要**写入 manifest 的 `config_inputs`：站台可建设空间、车辆参数、服务基线均未取得。

## 就绪状态的变化

输入包发布后聚合器首次给出 `ready_for_ai_interpretation: true`（站点主表、空间连接、人口、就业、输入包五个必需阶段均 DONE），可选缺失为 POI 与步行模型；`config_inputs_complete: false`，缺站台可建设空间、车辆参数、服务基线与情景结果；`config_inputs_all_observed: false`。这是当前状态的如实表达：可以供 AI 解读，还不能计算泊位与尺寸。

## 验证

[regression_results.json](regression_results.json)：20 个场景、190 项检查全部通过，全部在临时副本中运行，本目录只读。本步新增 `input_package_build`（10 项）：阶段 DONE、校验 PASS、锁定值等于当前指针、覆盖三层、21 份站点文件全部列入 manifest、AI 标志为 true、配置摘要含三项、缺失清单为四项、每个值带状态、包与本目录已发布的包逐字节一致。既有场景随编排器一起覆盖输入包：无变化重跑逐字节一致；空间连接重发包后输入包 STALE；原始文件改动后经人口层传递到输入包，AI 标志回到 false。

`data_nature` 枚举本步增加 `administrative_record`（分区图层、GTFS 时刻表这类非建模的行政记录），契约与规则文档同步。

## 未做

服务基线尚未从 GTFS 推算；情景阶段、POI 层、步行模型层未实现；角色分类与配置计算属于分析层与规则层，不在输入包内决定。
