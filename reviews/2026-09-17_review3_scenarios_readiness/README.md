# 对第三轮评测的响应（2026-09-17）

评测提出的四项都成立，均已在临时副本中复现后修正；POI 与步行路网在任何目录都未建过，readiness 中的 NOT_RUN 就是真实状态。

| 项 | 复现 | 修改 | 回归场景 |
|---|---|---|---|
| 1 情景基数的覆盖口径 | 4,299 条 both_in 联系（JT01 共 9,706 人）中 852 条、1,511 人涉及只被部分覆盖的街区；按两端街区陆地落在全网并集内的份额加权后为 8,814.6 人（90.8%） | 就业层为每个街区输出 `share_in_network_union`，OD 汇总新增 `both_in_coverage_weighted_S000` 与口径说明；情景层的 P01 改为覆盖加权值，整块纳入的 9,706 另报为上限，每条联系按 cov_h × cov_w 计入后再按候选站点份额分配；`excludes` 加上"部分覆盖街区的未覆盖份额"。三档早高峰出行量由 160 / 638 / 1,596 变为 145 / 580 / 1,449 | `service_baseline_and_scenarios`（新增"基数为覆盖加权"检查）；守恒、单调、低档上限照旧 |
| 2 可选层后补时旧输入包不提示 | 代码核对：过期判定只看已登记的依赖，没有"此前缺失、现在出现"的追踪 | 输入包 manifest 记 `optional_layers_absent_at_build`；聚合器发现其中任一层 DONE 即把输入包标 STALE，`freshness` 写明 `optional_layer_now_available`，重建后自动纳入并锁定 | `optional_layer_added_marks_input_package_stale`：POI 夹具出现后输入包 STALE 并点名 poi、情景层随之 STALE、AI 标志为 false；重建输入包后 DONE、poi 已锁定、缺席清单只剩 walk_model |
| 3 就绪文件自相矛盾 | 顶层 `demography.status` 等仍为 NOT_DOWNLOADED，而 `stages` 为 DONE | readiness 升到 2.2：顶层不再平铺上游清单；新增 `layers` 段，每个数据层的现状只从阶段登记表派生（含 `demand` 的"实测未取得 / 情景模型 DONE"两个字段与 `engineering` 的两项获取状态）；上游清单整体移入 `upstream_inventory` 并注明"日期快照，不含现状"。数据 README 的接入状态表同步改为现状 | `readiness_flags_baseline`（新增：顶层无旧状态键、`layers` 与 `stages` 一致、快照已嵌套且经校验） |
| 4 损坏的指针或 manifest 未按层隔离 | 可选层 manifest 写入非 JSON 后聚合器抛 JSONDecodeError、退出 1 | 新增 `safe_load`：指针、manifest、上游 build_manifest 与清单任一损坏，只把该阶段标 CORRUPT_PACKAGE 并写明"不是合法 JSON"，指针错误另记在 `lineage.pointer_errors`；聚合器继续完成其余阶段并正常退出 | `corrupt_optional_layer_isolated`：manifest 损坏与指针损坏两种情况，poi 为 CORRUPT_PACKAGE，其余阶段状态不变，AI 标志仍为 true |

## 验证

[regression_results.json](regression_results.json)：23 个场景、232 项检查全部通过，全部在临时副本中运行，本目录只读。修改聚合器与就业、情景脚本后用编排器重发了全部受影响的包（人口层与服务基线因代码登记的哈希变化也重发，产物不变）。

## 未做

POI 层与步行模型层仍未实现；站台可建设空间与车辆参数等待真实参数；情景仍未与实测客流校准。
