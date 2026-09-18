# Miami GTFS 首轮数据盘点

数据下载：2026-09-11；盘点与归档：2026-09-14。研究服务日：2026-09-14，时区 America/New_York。

本轮已完成数据归档、字段盘点、按服务名提取 Metromover 记录和初步完整性检查。尚未完成43个stop_id与官方21个实体站的对应，不包含客流预测、站台几何、结构或PRT配置。

后续进展：映射及GIS归档已在独立的[2026-09-14 数据包](../2026-09-14/README.md)完成第一版。本报告及原始未合并GeoJSON保留为首轮盘点记录。

## 原始数据

- [完整县级 GTFS ZIP](../../../raw/miami/2026-09-11/google_transit.zip)
- [归档来源与哈希](../../../raw/miami/2026-09-11/source_manifest.json)
- 同目录保存 Miami 21 服务元信息和两个地块的查询样本，不代表整个研究范围的 zoning 已齐备。
- 官方下载地址：https://www.miamidade.gov/transit/googletransit/current/google_transit.zip

## 文件与规模

| 文件 | 记录数 |
|---|---:|
| agency.txt | 1 |
| calendar.txt | 12 |
| calendar_dates.txt | 4 |
| routes.txt | 123 |
| stops.txt | 6,973 |
| trips.txt | 24,285 |
| stop_times.txt | 969,737 |
| shapes.txt | 100,590 |

以上是全县feed规模，不全部属于Metromover。

## Metromover 子集

按route_long_name包含METROMOVER筛选，经trips与stop_times关联：

- 2条GTFS线路记录：14457 / MMI（Inner Loop）；14456 / MMO（Omni/Brickell Outer Loop）。不能据此说只有两个实体环路。
- 全日历模式4,261条班次记录；按所选服务日的calendar及exceptions筛选后1,588条。
- 43个stop_id、23种站名；所选服务日仍涉及43个stop_id。
- 6条shape，所选服务日也涉及这6条。它们是计划服务路径，不是经过测量的高架结构线位。
- 43个停靠记录的parent_station均为空；location_type也均未填写。不能直接依赖父子站字段建立实体站映射。
- 存在需要核实的名称：COLLEGE BAYSIDE与COLLEGE / BAYSIDE；BISCAYNE BD@E FLAGLER ST等。保留原始ID与名称，不预先删除或强制合并。

班次记录、停靠事件和服务路径都是供给信息，不能当作上车人数。日历有效也不证明实际当天按计划运营。

## 已做检查

- ZIP CRC通过。
- stops/trips主键未发现重复行。
- stop_times引用的stop_id、trip_id均能在本feed找到。
- Metromover引用的shape_id都存在。
- 选出的站点坐标在WGS84合法范围内；路径至少包含两点且坐标范围有效。
- Metromover非空到发时刻未发现格式错误；未出现24时及以上的时间字段。这不是对全县所有时刻字段的检查结论。

这些检查不代替完整GTFS标准验证、实际运行核对、拓扑检查或工程调查。

## 产物

- [机器可读盘点](inventory.json)
- [43条原始停靠记录 GeoJSON](metromover_stop_records.geojson)：physical_station_id全部保留null，mapping_status=UNREVIEWED。
- [6条服务路径 GeoJSON](metromover_service_shapes.geojson)
- [按原始站名分组](metromover_name_groups.json)：只分组展示，不是实体站主表。

可复算脚本：[inventory_miami_gtfs.py](../../../scripts/inventory_miami_gtfs.py)。从数据基础目录运行：

```bash
python3 scripts/inventory_miami_gtfs.py raw/miami/2026-09-11/google_transit.zip data/miami/2026-09-11 --service-date 2026-09-14
```

## 下一步

建立官方21站的独立主表，结合名称、坐标、路径及停靠记录核对关系；把同站多个停靠点、名字变体与可能的替代停靠记录分别解释。继而定义研究边界、数据版本与演示场景。AI管线尚未在这些输入上运行。
