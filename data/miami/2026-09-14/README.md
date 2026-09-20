# Miami：21 站实体主表与 GIS 接入准备

更新：2026-09-14。已完成第一版可复算数据整理，适用于 2026-09-11 下载的 GTFS 快照。本轮没有运行 Coze、计算 PRT 泊位、判断结构可复用性或修改线上产品。

## 结论与证据

**43 个 GTFS 停靠记录 → 21 个站点实体。** 43 条记录在该快照中恰好落在 21 组不同坐标上；23 种原始站名中的 College Bayside 写法差异和 Bayfront Park 异常名称，需要单独处理。实体站名单依据 [Miami-Dade 官方站图](https://www.miamidade.gov/resources/transportation_publicworks/documents/metromover-map.pdf)逐一抄录并视觉核对，与[官方系统介绍的 21 站基线](https://www.miamidade.gov/global/transportation/metromover.page)一致。

这是一份由项目整理的、受到官方地图与 GTFS 支持的实体映射，尚未获得运营方逐条确认。`MIA-MM-*` 是项目自建稳定 ID；原始 GTFS ID 和名称全部保留。参考点来自 GTFS，不能当作站台中心、街道入口、精确地籍位置或测绘成果。

| 项目实体 ID | 官方图示站名 | 原始 stop_id |
|---|---|---|
| MIA-MM-01 | School Board | 795, 831 |
| MIA-MM-02 | Adrienne Arsht Center | 796 |
| MIA-MM-03 | Museum Park | 797, 829 |
| MIA-MM-04 | Eleventh Street | 798, 828 |
| MIA-MM-05 | Miami Worldcenter | 799, 827 |
| MIA-MM-06 | Freedom Tower | 800, 826 |
| MIA-MM-07 | College North | 811, 838 |
| MIA-MM-08 | Wilkie D. Ferguson, Jr. | 812, 837 |
| MIA-MM-09 | Government Center | 813 |
| MIA-MM-10 | College Bayside | 810, 825, 839 |
| MIA-MM-11 | First Street | 809, 824, 840 |
| MIA-MM-12 | Bayfront Park | 808, 823, **832**, 841 |
| MIA-MM-13 | Knight Center | 807, 822, 833 |
| MIA-MM-14 | Miami Avenue | 834 |
| MIA-MM-15 | Third Street | 815 |
| MIA-MM-16 | Riverwalk | 806, 816 |
| MIA-MM-17 | Fifth Street | 805, 817 |
| MIA-MM-18 | Brickell City Centre | 804, 818 |
| MIA-MM-19 | Tenth Street Promenade | 803, 819 |
| MIA-MM-20 | Brickell | 802, 820 |
| MIA-MM-21 | Financial District | 801, 821 |

### 两处合并证据与两处显示名规范化

- **College Bayside**：825 的名称多了 `/`，但与 810、839 的坐标完全一致；官方图中只有一个 College Bayside。保留原名，关联同一实体。
- **Bayfront Park / 832**：832 的名称是 `BISCAYNE BD@E FLAGLER ST`，但与 808、823、841 同坐标。它出现在 shape `123750` 的 `832 → 833 → 834 → 813` 序列，对应官方 Inner Loop 的 `Bayfront Park → Knight Center → Miami Avenue → Government Center`；另一段 shape `123751` 从 Government Center 经 Wilkie、College North、College Bayside、First Street 到同坐标的 841。因而将 832 映射到 Bayfront Park，同时保留 `SUPPORTED_WITH_SOURCE_NAME_ANOMALY`。这不证明该名称产生的原因，不能擅自称为已确认的旧站名、公交替代站或数据错误。
- **Tenth Street Promenade**：原始字段拼作 `PROMANADE`；显示名依官方图改为 `Promenade`，原始名称不改写。
- **Wilkie D. Ferguson, Jr.**：官方图提供标点和 Jr.，补入显示名；原始名称仍可追溯。

43 条记录均有唯一实体归属，未删除记录、未把缺失的 `parent_station` 伪造成官方字段。站点名称异常与实体映射状态分开记录。**一个实体对应多个 stop_id，不意味着它有同样数量的站台或 PRT 泊位。**

## 已取得的 GIS 与实际字段

本轮取得 [City of Miami 的 Miami 21 Zoning 图层](https://www.arcgis.com/home/item.html?id=064c93f16768497d8662b6d58a240703)在研究窗口内的 **235 个分区多边形**。发布者为 `CityMiamiFL`，项目元数据注明 CC BY 4.0，署名 City of Miami, Department of Planning and Zoning; Department of Innovation and Technology, GIS Team。原始响应、元数据与哈希均已归档。

研究窗口为 WGS84 bbox `[-80.209, 25.749, -80.175, 25.801]`，是为了下载站点周边数据而选定的矩形，**不是 15 分钟步行范围，也不是已批准项目边界**。返回的是与窗口相交的完整多边形，未裁切成窗口内碎片。独立 ID 查询、Esri JSON 和 GeoJSON 的 235 个 FID 集合一致，没有发现结果截断。

| 原始字段 | 本次真实例子 | V2 接入处理 |
|---|---|---|
| `FID` | 整数要素 ID | 与快照版本共同标识来源，不能当成永久地籍编号 |
| `M21_ZONE` | T6-80-O、T5-L、CS、CI、D1、D2、D3 | 保留完整代码，再建立审核过的用途映射 |
| `Transect` / `Transect_D` | T6 / Urban Core Zone；D1 / Work Place District Zone | 区分城市形态分区与实际用地、就业、需求 |
| `Map_Code` / `Intensity` | T6-80 / O | 保留地方分类语义，不能直接用通用 residential/commercial 标签替代 |
| `Bldg_Heigh` | 字符串 "80" | 需核对 zoning code 的定义；不能当成 80 米建筑实测高度 |
| `FLR` | 部分为空白字符串 | 标准化为缺失，不能改成 0 或自动通过 |
| `Enact` | "13114" | 保留法规追溯字段；尚未逐地块核查其全部修订与适用性 |
| `Shape_STAr` / `Shape__Area` | 多个不同面积值 | 不混用；后续根据确认的 CRS 与面积定义重算，不当成可建设面积 |

原图层 CRS 为 Web Mercator（EPSG:3857），请求输出为 WGS84（EPSG:4326）。GeoJSON 可以供地图显示；长度、面积、缓冲区分析需要选择当地适用的投影和单位。产品内部长度拟统一为米，美国显示可换算为英尺；**该显示约定不构成原始字段单位已核实的证明**。

这批数据中 D1 为 12 个、D2 为 4 个、D3 为 3 个分区多边形。保留其原始分类与几何，不按“工业”名称把其中职工、换乘、通行或改造价值一并清零。道路或高架是否应作为障碍、需求来源或可转换资产，应另立角色字段。

## 接入状态：已取得与仍缺少的内容

| 数据层 | 当前状态 | 下一步转换与限制 |
|---|---|---|
| 站点实体 | 21 站完成第一版映射 | 对新 feed 重新核对，保留 832 名称异常 |
| 计划服务路径 | 6 条路径及其有序站点序列已归档 | 供网络关系分析；不能充当实测高架资产 |
| Zoning | 235 个多边形及原始代码已取得；**站点空间连接已完成**（见下节"法定分区画像"） | 用途映射尚未做；画像只表示法定分区，不表示实际用途、人口或岗位 |
| 人口、收入 | **已接入**（2026-09-15，见"人口与就业层"）：ACS 2020–2024 block group 估计按陆地份额分摊到环带，带统计期与 MOE | 期间估计，不是当前人口；残障指标为 tract 级 |
| 就业与职住关系 | **已接入**（2026-09-15）：LODES 8（2023）WAC / RAC 与街区级 OD 联系，附候选站点 | 岗位数不是出行量；站对站分配属于情景层 |
| 服务基线 | **已由 GTFS 推算**（2026-09-15，见"服务基线与情景"） | 排定不等于运营，不是容量与客流 |
| POI | **已接入**（2026-09-17，见"POI 层"）：县、市与 USDA 的设施图层按固定规则分四类，逐站逐环带计数并给直线最近距离 | school / clinic / grocery / park 为产品分析类别，不是已核实的当地强制标准；距离是直线距离，不是步行距离；缺失指来源中未找到 |
| 步行路网 | 尚未接入（`layers.walk_network` 为 NOT_RUN，AI 解读的可选层） | 需真实入口、过街、障碍和垂直交通；建成后也只是 `network_walk_model` |
| 道路等级、货运、轨道资产 | 尚未取得（输入包中 `road_guideway_roles` 为 `not_acquired`） | 道路功能、标高、货运限制、实测货车使用与资产角色分开，不从 zoning 推断实际货运量 |
| 需求热力图、站级上车量、OD | **分站日均上车量已取得**（2026-09-17，DTPW 月度报表，10 个月，见"实测客流参照"）；OD 与分时流量仍未取得；**情景层已给出低／中／高未校准模型输出** | 上车量只作参照不作校准；GTFS 班次和停靠次数不能代替乘客数；情景假设与观测分开标注 |
| `served_hubs` | 官方图标注了部分铁路连接候选 | Government Center、Brickell、Wilkie D. Ferguson, Jr. 的连接仍需核对步行接口；不能据图推算换乘人数；枢纽流入在 Miami 案例中不建模 |
| 站台模块、可建设空间、车辆参数 | 站台模块图纸**已取得**（2026-09-17，M1 双侧 6 泊位、M2 单侧 7 泊位）；每站可建设空间**假定**可建（C06）；车辆能停入泊位为业主陈述，运营参数为通用 PRT **假设** | 21 个点不提供现状尺寸、承载能力、有效宽度或工程可复用性；配置结果是假设支撑的模型输出，不是设计 |

**当前状态以 `gis_data_readiness.json` 的 `stages` 与 `layers` 两段为准**；该文件里的 `upstream_inventory` 是站点主表阶段写下的日期快照，其中的 NOT_DOWNLOADED 只描述当时，不是现状。所有站点的泊位数、站台尺寸、布局目前均为 `null` / `NOT_CALCULATED`，工程状态为 `NEEDS_REVIEW`，AI 状态为 `NOT_RUN`。前端将来应显示"待取得／待分析"，不能用 0 或绿色通过替代。

## 空间连接：站点周边法定分区画像（2026-09-14 追加）

在同一输入快照上，把 235 个 zoning 多边形连接到 21 站，生成 **21 站 × 3 个距离带 = 63 份法定分区画像**，另附 0–½ mile 累计盘。这是**法定分区**（规划允许/约束的用途）的几何聚合，**不是**实际用途、人口、岗位或需求。

### 方法与参数（全部记录在本阶段包内的 `spatial_join/pkg-<id>/spatial_join_manifest.json`；上游 `build_manifest.json` 只登记上游产物）

- **距离带按英制定义**：0–⅛ / ⅛–¼ / ¼–½ mile = 0–660 / 660–1,320 / 1,320–2,640 ft，三个互不重叠的环带（面积比 1:3:12）。转换为米制用**国际英尺 0.3048 m（精确，NIST 2023 修订）**：201.168 / 402.336 / 804.672 m。这些是**距 GTFS 参考点的欧氏距离带**，不是步行范围，不含通行时间含义。
- **计算 CRS**：EPSG:26917（NAD83 / UTM 17N，米），`always_xy=True`。pyproj 实际选用的基准面步骤为 **"NAD83 to WGS 84 (1)"（EPSG:1188，空转换，报告精度 4 m，未用网格）**；**4 m（≈13.12 ft）是 PROJ 对该操作报告的精度，不是 GTFS 参考点、分区边界或整个模型的总精度，也不是"无影响"的证明**；`grid_used` 由实际 pipeline 推断而非写死，换环境、投影或网格可用性后须重新核对。
- **几何**：缓冲圆 `quad_segs=64`（面积为真圆的 0.9999）；先校验有效性再修复：**2 个多边形（FID 182、983）因环自相交经 `make_valid` 修复，Polygon→Polygon，无部件丢失**；`geometry_quality_report.json` 逐条记录修复方法、投影面积前后差、修复后与投影后的有效性，并确认 **235 个投影后几何全部有效**（不以"非空"代替"有效"）。
- **统计规则**：所有面积来自**裁切到环带内的几何**；覆盖率 = **并集面积 ÷ 环带面积**（源多边形可能重叠，直接求和会重复计入）；同时报告 `zoning_overlap_excess_area_m2`（求和 − 并集）、异码**重复计入量** `code_overlap_excess_area_m2` 与**真实多码重叠范围** `code_conflict_union_area_m2`（异码并集两两相交再求并集），**不强行归一化**。微小裁切碎片（最小约 9 sq ft）保留供审计，**不得据此解读为该站具有某类用途或需求**；展示值按 ft 0.1 / sq ft 1 / acres 0.01 舍入，六位小数只是数值精度、不是测量精度。按原始 `M21_ZONE` 与 `Transect_D` 聚合，同码内先并集；`polygon_count` 计有正面积交集的唯一 `FID`。**零用途映射、零剔除，D1/D2/D3 全部参与。**
- **重叠与"非排他覆盖比例"（不是分配权重）**：记录 21 站 ½ mile 盘两两**实际相交面积**（160 对相交）。每个多边形给出 `coverage_ratio_by_station_nonexclusive`（该站 ½ mile 盘内裁切面积 ÷ 多边形面积）；因盘重叠，**94 个多边形的各站比例合计 >1**（如 FID 98 合计 12.17），字段显式标 `is_allocation_weight:false`。全网 ½ mile **并集面积 3.57 sq mi**，而 21 盘面积**相加 16.49 sq mi（4.62×）**——这是面积重复，不等于人口或需求恰好高估 4.62 倍；并集由几何直接求得，**不能**用"面积和减两两交集"推出（存在三站及以上共同覆盖，会得负值）。下游需求分配须另建规则（未分配比例、换乘角色、竞争关系），不得把覆盖比例直接当权重或机械归一化成选择概率。
- **单位**：计算文件保留 m / m²；Miami 展示用 ft / mile、sq ft / acres（1 acre = 43,560 sq ft = 4,046.856 m²），换算因子记入 config。

### 结果与校验（`spatial_join_validation.json`）

**状态拆为三个字段**：`build_status: COMPLETED` / `geometry_validation_status: PASS` / `ready_for_downstream: true`。**这里的 PASS 只表示脚本列出的几何与输入完整性检查通过**，不代表整个 V2 输入包验收完成，不是运营方确认、步行可达结果或工程验证。

- 输入哈希与上游 manifest 一致；依赖锁匹配；同站三环带无正面积重叠、三带面积和 = ½ mile 盘（容差 1e-6 m²）；裁切面积不超环带；每站 ½ mile 内均有多边形；235 个投影后几何全部有效。
- **235 个多边形对账：146 个至少被一站命中，89 个位于窗口内但在所有 ½ mile 盘之外**（属正常，非缺失）；112 个落在 ≥2 站。
- **窗口余量对 21 站实算**：最小 **1,414.17 ft（431.04 m，MIA-MM-12 Bayfront Park）**，所有环带均在窗口内。
- **逐环带证据**：1,553 条（站 × 环带 × 源 FID），每条带 `evidence_id`，供网页高亮与 AI 按证据 ID 引用。**这 1,553 条不是互不重叠的覆盖记录**：其中 892 条是三个独立环带的记录（b1 89 / b2 186 / b3 617），另 661 条是 0–½ mile 累计盘的记录（`cum`），累计盘记录与环带记录覆盖同一批地块，两类**不能相加**解读。
- **复算一致性已验证**：无变化重跑得到同一个内容寻址包 ID（当前 ID 见 `spatial_join_current.json`），8 个产物 + manifest 字节级一致；在独立临时副本中从头重建也得到同一包 ID（同一解释器与锁定依赖下）。依赖锁文件变化（2026-09-15 加入 pyshp）会因 manifest 里的环境记录不同而产生新的包 ID，分析产物本身逐字节不变；旧包目录保留。

> **所有分析环带均位于已查询的空间窗口内，查询结果未发现截断。** 这不等于环带内所有实际分区都已完整、准确收录；"未覆盖"面积可能是水域、道路用地、图层空洞或未收录地块，**取得独立水域/道路图层前不拆分原因**。

### 审查后修正与发布规则（v1.2，依据 `reviews/2026-09-14_miami_spatial_join/` 与 `reviews/2026-09-14_miami_spatial_join_recheck/`）

两轮独立审查共提出 F1–F3、U1–U4、R1–R3 及若干次要项。下表是**逐项状态**；每项的验收证据都来自可重复运行的故障注入回归 `scripts/test_miami_pipeline_regression.py`（11 个场景、102 项检查，全部在临时副本中执行，本目录只读；结果存于 `reviews/2026-09-14_miami_spatial_join_recheck/fix_regression_results.json`）。表中"通过"仅指该场景的检查通过，**不是整个 V2 输入包验收**；被强杀进程、磁盘损坏等极端情形由读取时整包校验兜底，不在"通过"含义之内。

| 项 | 状态 | 规则 | 回归场景 |
|---|---|---|---|
| F1 · 校验失败保护 | 通过 | 先在 `spatial_join/.staging` 构建并完成全部校验；失败即写 `failed/spatial_join_failed_<时间>.json`，**当前包与指针不动** | `validation_failure` |
| R3 · 发布中断保护 | 通过（v1.2 新增） | 产物**整包**写入按内容寻址的不可变目录 `spatial_join/pkg-<id>/`（8 个产物 + manifest，id = manifest 的 sha256 前 12 位），整包自校验后用**一次原子 `os.replace`** 切换唯一可变文件 `spatial_join_current.json`；读取方先解析指针再校验整包。目录改名失败 → 什么都没发布；指针切换失败 → 新包完整但不生效、旧指针仍有效，直接重跑即恢复。不再逐文件替换 | `publish_failure_rename`、`publish_failure_pointer` |
| F2 · 版本记录准确（更新构建 + 归档） | 通过 | 每个包记录**实际**脚本 sha256 与参数 sha256；旧包目录原样保留即为归档（取代 `prev-<sha8>` 副本，v1.1 的两份平铺 manifest 已移入 `spatial_join/manifest_history/`）；无变化重跑得到同一包 ID、逐字节一致 | `unchanged_rerun` |
| F3 / R1 · 上游变化标过期 | 通过（R1 为 v1.2 修正） | 本阶段 manifest 记录所消费的**全部三份输入**（站点主表、研究窗口、原始 zoning）的 sha256；`scripts/miami_readiness.py` 逐一与当前文件比对，**任一不同即 `STALE`、`ready_for_downstream:false` 并列出变化项**；上游 manifest 哈希只作参考、不作判定。此前只比对站点主表，窗口或 zoning 变化会漏检 | `station_change`、`window_change`、`zoning_change` |
| R2 · readiness 单一写入者 | 通过（v1.2 修正） | 上游改为输出不可变的 `gis_inventory.json`；`gis_data_readiness.json` 只由 `scripts/miami_readiness.py` 从两份阶段 manifest **派生**（自带 lineage 哈希，每个阶段脚本结束时调用它），不再出现在任何阶段的产物清单里，因此上游 manifest 的哈希校验全部通过。此前上下游共写同一文件，导致上游清单中的哈希失配 | `readiness_single_writer`、`baseline_full_rebuild` |
| 包损坏可检出 | 通过（v1.2 新增） | 当前包任一文件与 manifest 不符 → `CORRUPT_PACKAGE`、`--check` 退出 1；重跑会把损坏目录隔离为 `pkg-<id>.corrupt-<时间>` 再重新发布 | `corrupt_package_detected` |
| U3 · 依赖锁 | 通过 | `requirements-gis.lock.txt` 是脚本解析的**运行时版本门禁**（GEOS / PROJ 条目是库版本），不是 pip 文件；可安装版本见 `requirements-gis.txt`；manifest 记录实际解释器路径与版本；`grid_used` 由实际 pipeline 推断；4 m 精度措辞收窄 | `lock_mismatch` |

语义修正（v1.1，保留）：

- **U1** 覆盖比例改为"非排他"并标 `is_allocation_weight:false`，新增全网 ½ mile 并集几何与面积（见上）。
- **U2** 新增逐环带、逐 FID 证据表 `station_zoning_evidence.json`（环带记录与累计盘记录不可相加，见上）。
- **U4** 修复诊断补投影面积与有效性——其中"修复前投影面积"在 v1.2 改名为 **buffer(0) 基线**（`projected_area_buffer0_baseline_m2`，附 `baseline_method`）：它是用另一种修复方法算出的对照值，**不是无效多边形的原始真值面积**（无效多边形没有定义良好的面积）；`code_conflict` 拆为重复计入量与真实重叠范围；每个 band 对象自带 `catchment_type / is_validated_walk_catchment:false / demand_origin_or_destination:TO_BE_EVALUATED / is_population_allocation_weight:false`；单独输出**站点参考点与分区匹配**（`station_point_zoning_match.json`：**Freedom Tower、Brickell 的参考点不在任何源分区多边形内**，其余 19 站有匹配——这不使环带画像失效，也不能据此断言站点不合法或无需求，**不做最近邻补值**）；readiness 中 `walk_network.distance_proxy_m=1200` 已注明是未执行的步行分析设想，不是本轮英制环带参数。

### 明确未做
步行可达结论、用途映射、需求分配、泊位与站台尺寸、运营方确认。距离权重不由环带面积隐含，须作为单独可校准参数。后续接入的人口密度、岗位密度和 POI 可达性可以形成地图，但不能直接作为"人／小时"的客流热力图；转成站点峰值上下客量还需要时段分布、出行目的、方式选择、PRT 采用率及站点分配假设，按低／中／高情景给出并标明每个参数是观测依据还是演示假设。数据层编码规则见 [V2 数据语义与客流转换规则](../../../V2_数据语义与客流转换规则.md)（第三版，已并入两轮独立评测的修订），字段级定义见 [V2 站点输入包字段契约](../../../V2_站点输入包字段契约.md)。

### 可用于面试的表述
"I joined the city's statutory zoning layer to the 21 stations as imperial-defined distance bands, computed in a local projected CRS with the actual datum transformation recorded, clipped geometry, union-based coverage, and per-code aggregation with no use mapping and no exclusion — so downstream demand work starts from a traceable, honest spatial profile."

## 人口与就业层（V2 第 3 步，2026-09-15 追加）

两层都按 [字段契约](../../../V2_站点输入包字段契约.md) 编码，整包发布到 `demography/pkg-<id>/` 与 `jobs/pkg-<id>/`，指针分别是 `demography_current.json` 与 `jobs_current.json`。**这些是居住地口径的调查估计与年度岗位计数，不是客流、不是出行量、不是步行范围。**

### 人口层（`scripts/build_miami_demography.py`，ACS 2020–2024 五年期，block group）

- **几何**：用空间连接包的参数重建 21 站的三个英制环带与累计盘，并与该包发布的面积逐站核对到 1e-4 m² 以内；陆地几何 = TIGER 2020 P.L. 街区多边形擦除 TIGER 2024 水域面要素，范围取与全网 ½ mile 并集相交的 39 个 tract 的全部 844 个街区（tract 完整，分母不裁切），其中 44 个街区被擦去水域。
- **份额**：block group 在某环带内的份额 = Σ(街区陆地 ∩ 环带) ÷ Σ(街区陆地)，分子分母同一套陆地几何；每站三环带份额之和与累计盘份额精确相等。
- **数值**：计数按 Σ(份额 × 估计) 汇总，MOE 按 √Σ(份额 × MOE)² 合并，字段标明**只含抽样误差、不含空间分摊的不确定性**；比例先合分子分母再算，MOE 用 Census 比例近似公式；每个值带 cv 与 `reliability_flag`（0.12 / 0.40 分档，项目惯例）。
- **中位数**：block group 的收入中位数只逐单元保留，不平均；环带级用 B19001 十六档户数按份额汇总后分组内线性插值，落入最高开放档只报下界，`sensitivity_range` 是所在档的上下界，不是置信区间。
- **残障指标（D13、R06）在 tract 级**：B18101 在 block group 级不发布，API 对全部 1,843 个 block group 返回 null，故改拉 tract 级并按 tract 陆地份额分摊，粒度比其他指标粗，字段标 `geography_unit: tract`。
- **重叠**：每站画像非排他；全网合计在并集几何上算一次去重。当前值：全网 ½ mile 陆地内去重人口 76,357，21 站累计盘相加 420,877（重复比 5.5），其中 67,711 人住在被两站以上覆盖的区域。这些是"重复计入"的说明，不是需求倍数。
- **产物**：`station_demography_profile.json`（63 份环带画像 + 累计盘 + 全网去重）、`demography_evidence.json`（2,151 条 站 × 环带 × 来源单元 记录）、`block_group_values.json`（83 个 block group 与 39 个 tract 的原始值与状态）、`block_land_geometry.json` 与 `analysis_targets_26917.json`（投影坐标的陆地几何与分析目标，供就业层复用）、`land_geometry_report.json`（擦水域前后与 ALAND20 的偏差，最大 0.16%）、`demography_validation.json`。

### 就业层（`scripts/build_miami_jobs.py`，LODES 8，佛州 2023，2020 街区）

- 直接消费人口层的陆地几何与分析目标，两层几何完全一致；街区份额 = 街区陆地 ∩ 环带 ÷ 街区陆地。
- WAC（工作地岗位）与 RAC（居民持有岗位）各取 JT00 全部岗位与 JT01 主要岗位；`C000` 按发布方定义都是"岗位总数"，只有 JT01 可近似人数。文件中没有的街区记为 `zero_absent_from_file`。无 MOE（行政数据建模）。
- 职住比主口径 J09 = WAC JT01 ÷ RAC JT01（同年同类型）；副口径 J10 = WAC JT01 ÷ ACS 住房单元，标 `mixed_period`。
- **OD 只到街区级，不做站对站矩阵**：保留至少一端落在候选街区（陆地触及任一站 ½ mile 盘的 510 个街区）的 156,291 条居住地到工作地联系，两端各附候选站点与份额，分四类；每站的"份额加权联系潜力"是非排他汇总，不是分配。恒等式 WAC = OD(main) + OD(aux) 在候选街区上对 JT00 与 JT01 均精确成立；居民在州外工作的岗位不在佛州文件里，已作为缺口计数（候选街区 423 份）。
- 当前值：全网 ½ mile 去重岗位 180,847（JT00），21 站相加 1,344,824（重复比 7.4）；去重后居民主要岗位 32,804，全网 J09 = 5.2。
- **产物**：`station_jobs_profile.json`、`jobs_evidence.json`（6,457 条 站 × 环带 × 街区 记录）、`block_values.json`（含每个街区的候选站点与份额）、`od_links_subset.csv.gz`（gzip 时间戳置零以保证逐字节可复现）、`od_summary.json`（类别合计、恒等式对账、每站非排他潜力）、`jobs_validation.json`。

### 两层共用的规则与验收

- 共用模块 `scripts/miami_v2_common.py`：依赖锁门禁（含 vendored pyshp）、投影记录、TIGER 读取、擦水域、份额、ACS 特殊值、MOE 公式、英制展示、通用整包发布。
- 每个包的 manifest 登记 `consumed_inputs`（原始文件路径与哈希）、`consumed_packages`、`code`、`config`、`environment`；聚合器据此判定过期。原始文件哈希与 `raw/miami/2026-09-15/source_manifest.json` 不符时脚本直接停止。
- 回归见 `reviews/2026-09-15_step3_demography_jobs/`。

## 站点输入包（V2 第 4 步，2026-09-15 追加）

`scripts/build_miami_input_package.py` 把站点主表、空间连接、人口、就业四层按**当前指针的包 ID** 汇总成每站一份输入包，发布到 `input_package/pkg-<id>/`，指针 `input_package_current.json`。它是 AI 批处理推理与确定性配置规则共同读取的那一份包。

- **只复制不重算**：每个数值块是产出层的信封原文（值、状态、误差字段、三组标记），另加 `evidence_source`（产出层、证据文件、证据 ID 模式）以便逐条追溯；结构检查保证每个 `value` 都带 `value_status`。
- **版本锁定**：`component_versions` 记录站点主表哈希与各层的包 ID、manifest 哈希；任一层重发包，聚合器把输入包标 STALE。manifest 另记 `optional_layers_absent_at_build`：构建时缺席的可选层（POI、步行模型）一旦建成，聚合器同样把输入包标 STALE 并点名该层，重建后自动纳入。
- **只放事实**：角色分类（起点／终点／待改造设施／障碍／候选场地）留为 `NOT_CLASSIFIED`，配置字段保持 `NOT_CALCULATED`；`ai_usage_rules` 写明 AI 引用证据 ID、规则 ID 与计算结果 ID 的要求以及禁止事项。
- **Miami 特定输入**：客流基线、服务基线（可由 GTFS 推算，尚未推算）、枢纽流入（保留字段、不建模）、道路与轨道角色、站台可建设空间、车辆参数，目前都未取得，`acquisition_status` 与 `value_status` 分开标注。
- **就绪状态**：输入包发布后 `ready_for_ai_interpretation` 首次为 true，可选缺失为 POI 与步行模型；`config_inputs_complete` 为 false，缺站台空间、车辆参数、服务基线与情景结果。
- **产物**：`station_input_package.json`（21 站 + 全网块，约 8 MB）、`stations/<station_id>.json`（每站一份，供网页按需加载）、`input_package_index.json`（站点清单、坐标、文件路径、配置输入状态）、`input_package_validation.json`。

## 服务基线与情景（V2 第 5 步，2026-09-15 追加）

### 服务基线（`scripts/build_miami_service_baseline.py`，阶段 `service_baseline`）

从 GTFS 快照的工作日服务（日历 service 11，周一至周五，无例外日期）按 stop → 站点映射把 Metromover 两条环线（MMI 内环、MMO Omni/Brickell 外环）的 stop_times 汇总到 21 站：逐小时与逐线路的排定出发次数、首末班、五个时段（早、早高峰 7–9、平峰 9–16、晚高峰 16–19、夜间）的每小时出发次数与隐含班距。12,307 条工作日 stop_times 全部对上站点。**排定不等于实际运营，出发次数不是容量也不是客流**；`data_nature: administrative_record`。输入包中 `service_baseline` 的获取状态变为 `derived`。

### 情景（`scripts/build_miami_scenarios.py`，阶段 `scenarios`）

按规则 5 的计算链做低／中／高三档，每一步一个参数、每个参数带三组标记：

| 步 | 参数 | 类别 | 值 |
|---|---|---|---|
| 基数 | 两端都在全网 ½ mile 并集内的 LODES 主要岗位联系，**按覆盖份额计入**：每条联系乘以两端街区陆地落在并集内的份额；只碰到圆的街区不整块纳入 | 推算（行政数据建模 × 陆地份额约定） | 8,815（整块纳入的上限为 9,706；852 条联系、1,511 人涉及部分覆盖的街区） |
| 通勤出行 | ACS 在家办公比例；到岗率 | 推算；假设 | 27.3%；0.85 |
| 全目的出行 | 非通勤出行 ÷ 通勤出行 | 假设，三档 | 0.5 / 1.0 / 1.5 |
| 高峰小时 | 单一峰值份额，B08302 最高 60 分钟窗口 8:00–8:59 | 推算，依赖"离家≈抵站"假设 | 35.5% |
| 采用率 | 占全方式出行份额，低档不超过观测公交分担率 6.1% | 假设，三档 | 0.05 / 0.15 / 0.30 |
| 分站上下客 | 按候选站点陆地份额归一分配，PM 为 AM 镜像 | 假设 | 守恒检查通过 |

结果：早高峰网内 PRT 出行量 低 145 / 中 580 / 高 1,449 人次，分站上下客见 `station_scenario_table.json`，每站附排定出发次数作为观测参照（不是容量比较）。**这是未校准的模型输出、演示计算链用，不是需求预测**：只含网内两端的联系，不含一端在网外的 17.8 万份工作地联系、居民在州外的岗位与枢纽换乘流入。三档只改非通勤倍数与采用率，其余参数共用。产物：`scenario_results.json`（含逐步计算链与守恒检查）、`scenario_parameters.json`、`station_scenario_table.json`、`scenario_validation.json`；manifest 带 `assumption_parameter_ids`，聚合器据此把情景结果标为"假设支撑"。

## 实测客流参照（V2 第 7a 步，2026-09-17 追加）

`scripts/fetch_miami_ridership_reports.py` 取得 Miami-Dade DTPW 2025-10 至 2026-07 十份月度《Ridership Technical Report》（`raw/miami/2026-09-17/dtpw_rtr/`，含 URL、哈希与检索时间），`scripts/build_miami_ridership_reference.py`（阶段 `ridership_reference`）从每份的"Metromover Monthly and Average Daily Boardings by Station"表解析 21 站的平均工作日、周六、周日上车量与月总量，按显式对照表映射到站点主表；三个改名站（Omni = Adrienne Arsht Center，Park West = Miami Worldcenter，Eighth Street = Brickell City Centre）标为待业主确认。每月分站之和与报表 TOTAL 相差不超过 3。

当前值：系统平均工作日上车量 10 个月均值 25,402 人次，Government Center 5,162（20.3%）、Bayfront Park 2,387、Brickell City Centre 1,783、Brickell 1,774。**这是现有 Metromover 的上车量，不是出行量、OD、下车量或分时流量，也不是新系统的需求；只作参照，不作校准。** 输入包的 `ridership_baseline` 因此为 `acquired`，情景包新增 `observed_reference` 块：量级参照（情景日出行量约为观测的 3% / 13% / 32%，因为情景只含网内联系）与分布参照（各站份额秩相关约 0.20；最大差异在 Government Center，观测 20% 对情景 3%，正是排除了 Metrorail 换乘等区域流入的结果）。

## POI 层：学校、诊所、杂货店、公园（V2 第 7b 步，2026-09-17 追加）

`scripts/fetch_miami_poi.py` 从三个官方开放数据服务按研究窗口取得设施记录（`raw/miami/2026-09-17/poi/`，每层记录服务 URL、字段、记录数、sha256 与检索时间）：Miami-Dade 县 GIS 开放数据的公立 / 特许 / 私立学校层与五个公共健康设施层（FQHC、独立诊所、JHS 初级诊疗、心理健康、校内诊所）、City of Miami 公园边界与县公园边界、USDA SNAP 零售商定位数据。原计划用 OSM 取杂货店与诊所，实际改为官方来源，OSM 的超市 / 杂货店（Overpass 镜像，数据有滞后）只作杂货店名单的交叉核对，不并入。`scripts/build_miami_poi.py`（阶段 `poi`，AI 解读的可选层）按固定规则分四类：学校 = 公立学校中在校生数 > 0 的记录 + 特许 + 私立（教育局办公楼、车库、通信中心、成人技术学院与零在校生的项目点共 8 条排除；有在校生的虚拟学校保留，因来源未标注）；公园 = 市公园多边形 + 与之重叠不超过 50% 的县公园多边形；诊所 = 五层合并、50 m 内同名去重；杂货店 = SNAP 店型为 Supermarket / Super Store / Grocery Store（便利店、专卖店、其他店型排除）。每站三个环带与累计盘分别给各类数量（点设施落在环带内、公园多边形与环带相交）和各类直线最近距离（起点为 GTFS 参考点，只在窗口内搜索），逐条证据在 `poi_evidence.json`，被排除的记录连同原因在 `poi_features.json → excluded_records`。

当前值：窗口内学校 37、诊所 8、杂货店 19、公园 38；全网 ½ mile 并集内去重后 22 / 3 / 14 / 24。诊所最少：21 站中 11 站 ½ mile 内没有任何来源中的诊所，Financial District 最近诊所直线约 1.0 mi；每站 ½ mile 内都至少有一所学校、一家杂货店和一处公园。**这些是来源中列出的设施数量与直线距离，不是服务水平评分，不是步行距离；"缺失"指来源中未找到（`not_found_in_source_within_window`），不是确认不存在。** 来源的已知瑕疵如实保留：市公园层含 "UNNAMED - FAA Parcel" 一类的地块名，SNAP 名单含小型市场。输入包每站每环带新增 `poi` 块（数量与设施 ID）和站级 `poi_nearest_by_category`；`optional_layers.poi` 为 `acquired`，readiness 的 `ai_missing_optional` 只剩 `walk_model`。

## 站点配置：PRT 泊位、模块与占地（V2 第 6 步，2026-09-17 追加）

`scripts/build_miami_config.py`，阶段 `config`，按规则 7 把情景层的人次换算成 PRT 的车次、泊位、模块与占地，每一步一个参数、每个参数带类别标记。输入：业主提供的两种站台模块图纸（`config/station_platform_modules_v1.json`，英制为准，公制原值另存，相差不超过 0.6%；车辆能完全停入泊位，几何尺寸不需要）与通用 PRT 运营假设（`config/prt_operations_assumptions_v1.json`：平均同行人数 1.3、泊位周期 45 s、利用率 0.8、小时内峰值系数 1.25、最小行车间隔 3 s、无暂存泊位、假定占地可建）。

链：上车人次 ÷ 同行人数 = 车次 → 每小时泊位周期 = max(到达车次, 出发车次) → × 小时内峰值系数 ÷ (3600 ÷ 泊位周期 × 利用率) 向上取整 = 泊位数 → 泊位数足够的最小模块 → 占地；另算空车平衡与网络级轨道流量比值。PM 为 AM 镜像，泊位数相同。

当前结果（早高峰）：三档全网泊位数 21 / 21 / 36，即低、中档每站 1 个泊位，高档 Brickell、Financial District、Tenth Street 各需 3 个；所有站用 M1 双侧 6 泊位模块即可，无站超过单模块；全网车次 111 / 446 / 1,115 车次/小时，高档接近 3 s 间隔下单线 1,200 车次/小时的网络级上限（比值 0.93）；高档 Brickell 每小时需调入约 30 辆空车。**这些是假设支撑的模型输出，不是设计，也不能证明全线替换容量足够**：需求侧不含区域流入与枢纽换乘，站点可建设空间未取得。产物：`station_config_results.json`、`config_parameters.json`、`station_config_table.json`、`config_validation.json`。

就绪状态因此变为：`ready_for_ai_interpretation: true`；`config_inputs_complete: true`；`config_inputs_all_observed: false`；假设支撑项为站台可建设空间、车辆参数、情景结果。

## 规则层与 AI 解读准备（V2 第 9 步，2026-09-18 追加）

**规则层**（阶段 `rules`，`scripts/build_miami_rules.py`，规则包 [`config/rules_v2.json`](../../../config/rules_v2.json) 版本 rules-v2.0）：13 条规则按站、按情景评估已发布的输入包、情景包与配置包，每条结果带可引用的 `rule_result_id`（如 `MIA-MM-09|-|RC-12`、`NET|high|RC-05`）。规则分四类：算术恒等式（守恒、泊位公式复算）、项目约定（单模块容量、轨道网络比值 0.8 / 1.0、低档采用率不高于观测公交分担率、空车不平衡）、数据质量（人口估计可靠性、改名站对应）、范围限制（可建设空间假设、枢纽流入排除、欧氏环带）。当前 325 条结果：无 critical；全网高情景轨道比值 0.93 为 warning；21 站都带"可建设空间为假设"的 warning；三个改名站、Government Center 的枢纽流入各按规则标出。**规则包是本研究的约定与恒等式，不是法规、行业标准或供应商规格。**

**AI 解读准备**（`scripts/build_miami_ai_kit.py`，套件 ai-kit-v2.1）：知识库 `kb/v2/`（四份英文文档，kb-v2.1：数据语义、情景与 PRT 配置方法、解读指引、未决事项与责任归属）、智能体提示词 `kb/v2/AGENT_PROMPT_v2.md`（prompt-v2.1）、每站摘要 `ai/miami/briefs/`（83 条带 `fact_id` 的事实 + 全部规则结果 + 未取得项与禁止事项）、输出规范 `config/ai_output_schema_v2.json`、校验脚本 `scripts/check_miami_ai_output.py`（引用的每个 fact_id / rule_result_id / KB 章节都核对存在，必引 RC-03 与 RC-07，禁止措辞与摘要外数字给软提示）。操作说明见 [`ai/README.md`](../../../ai/README.md)。**尚无任何模型输出**；就绪视图与网页的 AI 状态仍为 NOT_RUN。

## GIS 要素层与读取智能体的输入（V2 第 11 步，2026-09-20 追加）

业主明确：**让 AI 智能体去读 GIS 数据**是 V2 的核心；热力图用公开数据推算、标明是代理；热力图与 zoning 结合着读，只作辅助证据。原则因此从"代码读取、AI 解释"改为"**AI 读取与判读，代码核验，人决定**"。

**采集**（`scripts/fetch_miami_gis_objects.py` → `raw/miami/2026-09-20/gis_objects/`）：县 GIS 的地块多边形 5,835 个、现状用地多边形 3,410 个、铁路 206 段、Metrorail 线；2020 年普查街区人口 31,622 行（全县合计 2,701,767，与官方总数一致）。按对象 id 分块取数并核对条数。**隐私规则**：含业主姓名与邮寄地址的房产记录层不取；地块层只请求地块编号、用地代码与描述、面积、建成年份等字段，不请求坐落地址与法律描述。道路沿用已归档的 OSM，zoning 沿用 9 月 14 日的采集。

**阶段 `gis_objects`**（`scripts/build_miami_gis_objects.py`，配置 [`config/gis_objects_v1.json`](../../../config/gis_objects_v1.json)）：代码只做裁剪、量测、连接与计数，给每个要素一个可引用的 id：道路分组 `.RDnn`、铁路 `.RLnn`、既有导轨 `.GW01`、zoning 多边形 `.ZN<FID>`、现状用地类别 `.LU<code>`、地块 `.PCnnn`、热度栅格 `.HC<行>_<列>`、街区组 `.BG<geoid>`，以及代码算好的汇总数字 `.Gnnn`。21 站共 8,982 个对象。zoning 裁剪面积与空间连接包逐区对比，偏差为零。

- **热度代理**：500 ft 栅格；每格 = （2020 年普查居民 + 2023 年 LODES 岗位）÷ 格内陆地英亩，按街区陆地份额分摊；全网 453 格，前五分之一为"热格"（74 个）。每格同时记录所在 zoning 类别、现状用地、最高道路等级、是否有铁路，供"热度与 zoning 结合着读"。**不是实测热度，不是客流，不是人/小时**；数值按街区均摊，公园、广场所在的格子会继承街区密度，已写入配置、图片说明和知识库。居民来自 2020 年普查，与人口层的 ACS 2020–2024 估计来源和年份不同，从不相加。
- **一个被编码成检查的语义陷阱**：县"铁路"图层没有任何属性，窗口内 25.75 mi 中约 41% 其实是 Metromover 导轨、27% 是 Metrorail，只有 8.31 mi 是其他铁路。阶段按几何（20 m）把它拆成三部分，顺序是先划出导轨、再划出 Metrorail、余下为其他铁路；约 2.0 mi 的轨道同时靠近两条线，按这个顺序归入导轨（只看与 Metrorail 的距离时是 8.94 mi，拆分后记为 6.92 mi，两个数字口径不同）。读取核验节点规定"既有导轨是待转换设施，读成障碍即拒绝"。
- **地块分组**依据图层自带的用地描述文字，未列入的前缀归入 other 并报告（当前为零）；市中心有 8 个地块的税务分类是"蔬菜耕地"，原样保留，留给读取智能体指出。
- **角色提示**（`object_role_hints.json`，规则 GH-01 至 GH-08）不进入智能体输入，只用于事后统计智能体与简单规则的一致率、把分歧排给人审。

**导出**（`scripts/export_miami_gis_agent_inputs.py`）：每站 `g1_input.json`（道路、铁路与导轨、zoning、现状用地、地块）、`g2_input.json`（热度格值、街区组、zoning）、`heat.png`（热度代理图，图内写明是代理）与 `brief.coze.json`，写入 `ai/miami/gis/<站>/` 并镜像到 `docs/gis/<站>/`，供 Coze 工作流的 HTTP 节点按站点编号拉取。图片重复生成字节一致。

**知识库**升到 kb-v2.1，新增 `KB_V2_05`（GIS 读取指引：角色、道路、铁路与导轨、zoning、用地与地块、热度代理、热度与 zoning 联读、服务相关性筛查、图片的用途）与 `KB_V2_06`（图层图例，由 `scripts/build_miami_kb_legends.py` 从图层自身生成）。图例只写图层带的内容与已核实的定义：Miami 21 官方术语表核实了容积率（FLR）的定义；强度字母 R / L / O、FLR 字母 A / B 和高度数字的单位，图层没有定义、本研究未核实，图例如实写明，智能体只能当标签用。

**Coze 设计**（`coze/v2/`）：新增读取智能体 G1、G2 与两个代码节点 `gis_gate.js`、`gis_verify.js`；评测 `node coze/v2/evals/run.js` 共 32 项全部通过。**尚无任何模型运行。**

## 文件与复算

- [21 站实体 GeoJSON](station_master.geojson)：地图和后续站点输入的稳定主表。
- [43 → 21 映射及逐条证据](stop_to_station_crosswalk.json)：保留原名、异常、版本与来源。
- [6 组有序服务路径](service_patterns.json)：同时保留原始 stop_id 序列和实体站序列。
- [数据提取窗口](study_window.geojson)；[235 个原始 zoning 多边形](../../../raw/miami/2026-09-14/zoning_study_window.geojson)。
- [GIS 数据清单（上游不可变产物）](gis_inventory.json)；[GIS 接入状态（派生视图，唯一写入者 `scripts/miami_readiness.py`；`stages` 段按构建顺序列出八个阶段的 DONE / STALE / CORRUPT_PACKAGE / NOT_RUN，`readiness_flags` 段给出六个就绪字段；2026-09-15 起，未实现的人口、就业、POI、步行模型、输入包、情景阶段如实显示 NOT_RUN）](gis_data_readiness.json)；[校验结果](validation.json)；[上游输入与产物哈希](build_manifest.json)。
- **法定分区画像（空间连接阶段，整包发布）**：指针 [`spatial_join_current.json`](spatial_join_current.json) 指向当前包目录 `spatial_join/pkg-<id>/`（当前 ID 以指针文件为准，不要写死）。包内 9 个文件：`spatial_join_manifest.json`（本阶段 manifest）、`station_zoning_profile.json`（63 份画像 + 累计盘 + 全网并集指标）、`station_catchments.geojson`（环带几何）、`network_half_mile_union.geojson`（全网 ½ mile 并集几何）、`station_overlap.json`（站间重叠与非排他覆盖比例）、`station_zoning_evidence.json`（逐环带逐 FID 证据表）、`station_point_zoning_match.json`（站点参考点分区匹配）、`spatial_join_validation.json`（空间连接校验）、`geometry_quality_report.json`（几何质量报告）。**消费者一律先读指针再取包，并校验整包**（`python3 scripts/miami_readiness.py --check`）；被指针替换的旧包目录不进公开仓库（2026-09-18 起移至仓库外的 `archive/superseded_packages_<日期>/`，附 `MOVED.json` 清单，可移回），v1.1 平铺布局的两份 manifest 在 `spatial_join/manifest_history/`；失败日志在 `failed/`。脚本 [`build_miami_station_zoning_profile.py`](../../../scripts/build_miami_station_zoning_profile.py) —— **与站点主表脚本不同，它依赖 shapely / pyproj（非纯标准库）**，版本由 [`requirements-gis.lock.txt`](../../../requirements-gis.lock.txt) 锁定并强制校验（可安装版本见 [`requirements-gis.txt`](../../../requirements-gis.txt)），实际解释器记入 manifest。
- [人工整理的映射规则](../../../config/miami_station_registry_v1.json)；[可复算脚本](../../../scripts/build_miami_station_master.py)；[原始来源清单](../../../raw/miami/2026-09-14/source_manifest.json)。

从数据基础目录执行 `python3 scripts/build_miami_station_master.py`，使用 Python 标准库即可重新生成站点主表。脚本会在 GTFS 快照哈希变化、重复归属、未覆盖记录、组内坐标冲突、832 的已核对序列改变或 GIS 查询不完整时停止；不会靠模糊名称匹配静默合并新记录。

**复算全流程请用统一入口**：`python3 scripts/build_all_miami.py`（按 站点主表 → 空间连接 → 人口层 → 就业层 → 服务基线 → 实测客流参照 → POI 层 → 输入包 → 情景 → 配置 → readiness 校验 顺序执行，用同一解释器，任一阶段失败即停止；人口与就业层需要 `raw/miami/2026-09-15/` 已按 `scripts/fetch_miami_v2_raw.py` 取得并校验）。**回归测试**：`python3 scripts/test_miami_pipeline_regression.py --out <结果.json>`（只在临时副本中运行，28 个场景 / 302 项检查，本目录只读；最新结果在 `reviews/2026-09-20_step11_gis_reading_agents/`）。空间连接阶段要求解释器已安装 `requirements-gis.lock.txt` 锁定版本的 shapely / pyproj（已发布结果来自 Python 3.13.9 + shapely 2.1.2 / GEOS 3.13.1 / pyproj 3.8.0 / PROJ 9.8.1，解释器路径记录在 `spatial_join_manifest.json → environment`）；系统默认 `python3` 若无这些库或版本不符，脚本会停止并提示，而不是在未锁定环境下静默产出。

本次检查支持数据一致性与可复算性，不是运营方批准、完整 GTFS 合规认证、客流校准、平台尺寸校验或结构安全验证。

## 可用于面试的项目表述

“In this prototype, I reconciled 43 GTFS stop records into 21 station entities using the official network map, coordinates, and service sequences. I preserved an anomalous source label instead of hiding it, and staged the local zoning data with its original codes and provenance. This gives the downstream AI and configuration engine a traceable spatial input.”

这段表述对应本次原型实际完成的工作。GIS 融合、AI 分析、配置优化以及真实项目业务成果，需要分别说明其完成状态与证据。

人口、就业、服务基线、实测客流参照与 POI 已接入，站点输入包、情景与 PRT 配置已生成（见上文各节）。静态网页演示已搭建：`scripts/export_web_demo_data.py` 从各包指针读取并校验整包后导出 `docs/data/demo_data.js`（只复制、不重算，记录包 ID 与 readiness 快照），`docs/index.html` 读取它渲染 STAR 叙事与逐站流程。步行路网模型（V2 第 7c 步）已暂停：`scripts/fetch_miami_osm_walk_network.py` 已取得并校验 OSM 路网（`raw/miami/2026-09-17/osm/`，含查询、时间戳与哈希），`scripts/build_miami_walk_model.py` 已写好但首次运行超过 10 分钟未完成（几千段路网线缓冲合并与复杂多边形求交过慢），未发布任何包，编排器中该阶段已注释；就绪视图如实显示 `walk_model = NOT_RUN`。不得在这些输入缺失时把地图颜色或服务班次换算成已知客流。
