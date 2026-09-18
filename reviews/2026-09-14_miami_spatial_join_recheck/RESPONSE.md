# 对第二轮复查的响应（2026-09-14，v1.2）

对照 [复查报告](README.md) 的三项遗留（R1–R3）与次要说明，逐项记录：修复前的独立复现、所做修改、以及可重复运行的验收证据。

证据来源：`scripts/test_miami_pipeline_regression.py`（故障注入回归，11 个场景、102 项检查；其中一项是在独立副本中从头重建后与本目录已发布包逐字节比对）。它把整个目录复制到临时目录后才运行，本目录树只读；本次运行结果保存在 [fix_regression_results.json](fix_regression_results.json)，其中记录了被测脚本的 sha256、解释器与每个场景的逐项检查值。

## 修复前复现（临时副本，未改生产数据）

| 项 | 复现结果 |
|---|---|
| R1 | 只改研究窗口（bbox 北边 +0.0005°）重建上游：`study_window_sha256` 已变，readiness 仍为 `DONE / FRESH / ready_for_downstream:true`。只改 FID 64 的 `M21_ZONE`（GeoJSON 与 Esri JSON 一致修改）重建上游：`zoning_raw_sha256` 已变，仍 `DONE / FRESH`。代码只比较 `station_master_sha256`。 |
| R2 | 真实文件：`build_manifest.json` 登记的 6 个产物中 5 个哈希匹配，`gis_data_readiness.json` 不匹配；空间阶段 8 个产物全部匹配。原因是上游先记哈希、下游再改写同一文件。 |
| R3 | 改 `QUAD_SEGS` 后在第 2 个 `os.replace` 注入 `OSError`：`station_zoning_profile.json` 已是新版，其余 7 个仍旧版，manifest 对画像的哈希校验失败，readiness 仍写 `DONE`，staging 残留。 |

## 修改与验收

| 项 | 修改 | 回归场景（全部通过） |
|---|---|---|
| **R1 · P1** 过期判断只看站点主表 | 过期判定移入新的 `scripts/miami_readiness.py`：读取当前包 manifest 记录的三份消费输入哈希（`station_master_sha256`、`study_window_sha256`、`zoning_raw_sha256`），逐一与**当前文件**比对；任一不同即 `STALE`、`ready_for_downstream:false`，并在 `consumed_inputs_changed` 列出变化项。上游 manifest 哈希只作参考字段（`upstream_manifest_sha256_matches_current`），不参与判定，因此上游无实质变化的重跑不会误报。上游脚本不再读取下游 manifest。 | `station_change`、`window_change`、`zoning_change`：上游单独重建后分别得到 `STALE` 且 `consumed_inputs_changed` 恰为 `["station_master_sha256"]` / `["study_window_sha256"]` / `["zoning_raw_sha256"]`，`--check` 退出 1；重跑下游后 `DONE`，指针记录前一个包 |
| **R2 · P2** 共享 readiness 导致上游 manifest 校验失败 | 采用复查的首选方案。上游改为输出**不可变**的 `gis_inventory.json`（原 readiness 的清单内容，逐段核对一致），并只把它列入 `build_manifest.json`。`gis_data_readiness.json` 改为**派生视图**（schema `miami-gis-readiness/2.0`），唯一写入者是 `scripts/miami_readiness.py`：从两份阶段 manifest 派生，自带 `lineage`（两份 manifest 与清单的 sha256），不出现在任何阶段的产物清单中；上下游脚本结束时各调用一次它，编排器最后再 `--check` 一次。不存在下游回改上游 manifest 的循环。 | `baseline_full_rebuild`：上游 manifest 6 个产物全部匹配、readiness 不在任何清单中；`readiness_single_writer`：lineage 与当前两份 manifest 一致、聚合器重跑逐字节一致、阶段脚本源码中无 readiness 写入 |
| **R3 · P2** 逐文件替换可能留下混合版本 | 产物整包写入 `spatial_join/.staging`，生成 manifest 后先做整包自校验；包 ID = manifest sha256 前 12 位（内容寻址），整目录 `os.rename` 为 `spatial_join/pkg-<id>/`（同文件系统，原子）；再用**一次** `os.replace` 切换唯一可变文件 `spatial_join_current.json`。读取方先解析指针再整包校验（`miami_readiness.verify_package`）。无变化重跑得到同一包 ID、复用且逐字节一致；旧包目录原样保留即归档，取代 `prev-<sha8>` 副本。 | `publish_failure_rename`（目录改名注错）：退出非 0、指针不变、已发布文件全部不变、无新包、无残留 staging、有失败日志；`publish_failure_pointer`（指针切换注错）：新包完整但不生效、旧指针与旧包仍可校验、readiness 仍为旧包的 `DONE`，直接重跑即切换到新包；`unchanged_rerun`：全部数据文件逐字节一致、无新包 |
| 包损坏检出（R3 的读取侧） | 当前包任一文件与 manifest 不符 → `CORRUPT_PACKAGE`、`ready_for_downstream:false`、`--check` 退出 1；重跑时同 ID 目录若不一致，隔离为 `pkg-<id>.corrupt-<时间>` 后重新发布，不静默覆盖。 | `corrupt_package_detected` |
| 次要 · buffer(0) 基线 | `projected_area_before_m2` 改名 `projected_area_buffer0_baseline_m2`，新增 `baseline_method` 说明它是 `buffer(0)` 修复的对照值而非原始真值；相关字段同步改名（`*_diagnostic_only`、`*_after_make_valid_m2`、`*_delta_vs_buffer0_baseline_m2`）。FID 182、983 的数值未变。 | —— |
| 次要 · 锁文件性质 | `requirements-gis.lock.txt` 加注"运行时版本门禁，非 pip 文件"；新增可安装的 `requirements-gis.txt`（shapely、pyproj 固定版本，GEOS / PROJ 由运行时门禁核对）。 | `lock_mismatch`：改锁后退出 1、数据文件全部不变 |
| 次要 · README 措辞 | 数据 README 删除"已全部修复"，改为逐项状态表；把"校验失败保护"（F1）与"发布中断保护"（R3）分开陈述；注明 1,553 条证据 = 892 条环带记录 + 661 条累计盘记录，不可相加。 | —— |
| 保留 | F1 校验失败不发布；U1–U4 语义修正；英制半径、面积裁切、重叠记录、全网并集、逐 FID 证据、依赖锁。 | `validation_failure`：`SPATIAL_JOIN_FORCE_FAIL=1` 退出 1、数据文件全部不变、无新包、有失败日志 |

## 保护范围的准确表述

- **校验失败保护**（F1）：通过。校验不通过时不发布，当前包与指针不动。
- **发布中断保护**（R3）：通过所列两个注错场景。目录改名和指针替换各是一个原子系统调用，中断只会落在"未发布"或"新包完整但未生效"两种状态，读取方永远看不到混合版本。
- **未覆盖**：文件系统层面的损坏或人为改动不在"发布中断保护"之内，由读取时的整包校验兜底（`CORRUPT_PACKAGE`）。
- "通过"只指对应场景的检查通过，不是整个 V2 输入包验收，不是运营方确认、步行可达结果或工程验证。

## 布局变化（消费者需知）

- 空间连接产物不再平铺在 `data/miami/2026-09-14/` 根目录：读 `spatial_join_current.json` → `package_dir` → 包内 9 个文件；**不要写死包目录名**。本次响应时的包为 `spatial_join/pkg-113ee767a2ca`；之后依赖锁加入 pyshp 后重发过包（分析产物逐字节不变），当前 ID 以指针为准。
- v1.1 的 8 个平铺产物已删除。删除前逐文件核对：与新包的分析内容一致，差异仅为 `upstream.manifest_sha256`（上游 manifest 因 R2 变化）、`environment.lock_sha256`（锁文件加了注释）与改名的修复诊断字段。v1.1 的两份 manifest 移入 `spatial_join/manifest_history/`。
- `gis_data_readiness.json` 的 `zoning.station_spatial_join` 字段变化：`upstream_station_master_sha256` → `consumed_inputs_recorded_sha256`（三项）+ `consumed_inputs_changed`；`profile_file` 现为包内路径；新增 `CORRUPT_PACKAGE` 状态。
- 上游新增 `gis_inventory.json`；`build_manifest.json` 不再含 `downstream_stages_status_at_this_upstream_build`。
- 统一入口 `scripts/build_all_miami.py` 增加最后一步 `miami_readiness.py --check`。

## 未做

未重选英制半径，未改空间算法，未扩展三城调研或可视化（复查验收建议如此）。三城数据、下一层数据（ACS / LODES）与数据目录版本化仍待决定。
