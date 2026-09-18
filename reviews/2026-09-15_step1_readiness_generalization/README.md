# 第 1 步 · 就绪聚合器泛化与六个就绪字段（2026-09-15）

依据字段契约第 10、11 节实现。本步不下载任何数据，不改动任何已发布的包；当前空间连接包仍是 `spatial_join/pkg-113ee767a2ca`。

## 改动

| 文件 | 内容 |
|---|---|
| `scripts/miami_readiness.py` | 阶段登记表（station_master、spatial_join、demography、jobs、poi、walk_model、input_package、scenarios，顺序即构建顺序）；通用过期判定：`consumed_inputs` 文件哈希、`consumed_packages` 是否仍为该阶段当前包、被消费阶段是否 DONE（过期沿构建顺序传递）；站点主表按 `build_manifest.json` 的产物与数据输入判定；空间连接旧格式 manifest 走兼容映射；六个就绪字段写入 `readiness_flags`，阶段状态写入 `stages`；readiness schema 升到 2.1，旧的 `zoning.station_spatial_join` 块保留 |
| `scripts/test_miami_pipeline_regression.py` | 新增 6 个场景，用"夹具包"模拟尚未实现的层（同样的包目录、指针与 manifest 约定）；原 11 个场景不变 |
| `V2_站点输入包字段契约.md` | 第 8 节 `acquisition_status` 增加 `assumed`；第 10 节写明聚合器读取位置；第 11 节写明布局约定、过期传递、代码变化只作提示、旧格式兼容 |
| `data/miami/2026-09-14/README.md` | readiness 描述更新 |

两条判定规则是本步定下的，评测时请一并审：

1. **代码变化不算过期。** 包记录了生成它的脚本哈希；当前脚本不同时 `code_matches_current` 为 false，提示重建，但已发布结果与其记录的输入仍然一致。
2. **过期向下传递。** 被消费的阶段不是 DONE 时，消费它的阶段也标 STALE，理由写在 `consumed_stages_not_done`。

## 验证

[regression_results.json](regression_results.json)：17 个场景、158 项检查全部通过，其中本步新增 56 项。全部在临时副本中运行，本目录只读；独立副本从头重建得到与已发布包逐字节一致的结果。

| 场景 | 验证内容 |
|---|---|
| `readiness_flags_baseline` | 八个阶段按顺序列出；未实现的六个阶段 NOT_RUN；AI 标志 false 并列出 demography、jobs、input_package；可选缺失列出 poi、walk_model；配置完整 false 并列出四项缺失；三个标志都是布尔值；`--check-ai` 退出 1，`--check` 退出 0 |
| `future_layers_fixtures` | 夹具的 demography、jobs、input_package 到位后 AI 标志为 true，尽管 poi、walk_model 缺失；补 poi 夹具后可选缺失只剩 walk_model |
| `assumption_backed_inputs` | 站台空间与车辆参数标为假设、服务基线为推算、情景含假设参数：完整 true、全部观测 false、假设清单三项；全部观测的变体：两者都 true |
| `stale_propagation` | 空间连接重发包后，直接消费它的三个层 STALE 且理由为 spatial_join，情景阶段因输入包不是 DONE 而 STALE，AI 标志回到 false |
| `raw_change_station_master` | 只改站点登记表不重建：站点主表 STALE 并点名该文件，空间连接仍 DONE；重建上游后空间连接 STALE；重建下游后两者 DONE |
| `code_change_informational` | 两个脚本只加注释：状态保持 DONE，`code_matches_current` 为 false；重建后为 true，空间连接得到新包 |

生产目录的 readiness 已按新 schema 重新生成：站点主表与空间连接 DONE，其余六个阶段 NOT_RUN，六个字段如实为 false 并列出缺项。

## 未做

人口、就业、POI、步行模型、输入包、情景六个阶段尚未实现，也未下载任何数据；夹具包只存在于回归的临时副本中。下一步是第 2 步：原始数据获取与哈希清单。
