# 第 7a 步 · 实测客流参照（2026-09-17）

目标是取得一个观测的客流量级作参照，不做校准。找到的来源比预期好：Miami-Dade DTPW 月度《Ridership Technical Report》有 **Metromover 分站** 的月度与日均上车量。

## 获取与解析

- `scripts/fetch_miami_ridership_reports.py`：下载 2025-10 至 2026-07 十份报表到 `raw/miami/2026-09-17/dtpw_rtr/`，记录 URL、字节数、sha256、HTTP Last-Modified 与检索时间，并验证每份都含"Metromover Monthly and Average Daily Boardings by Station"表、21 站加 TOTAL、分站之和与 TOTAL 相差不超过 3、月份标签与文件名一致、站名集合各月一致。2025-08 与 2025-09 为旧版式、站名截断，未采用。
- `scripts/build_miami_ridership_reference.py`（阶段 `ridership_reference`）：解析十份表，按显式对照表映射到 21 站；三个改名站（Omni → Adrienne Arsht Center，Park West → Miami Worldcenter，Eighth Street → Brickell City Centre）标 `renamed_station_same_location`、`mapping_confirmed_by_owner: false`。输出每站十个月的序列、十月均值、最新月、系统份额，以及系统合计。

## 数值与语义

系统平均工作日上车量十月均值 25,402 人次（月度 22,683 到 29,881）。Government Center 5,162（20.3%）居首，其次 Bayfront Park、Brickell City Centre、Brickell。字段标 `observed / measured`，并明确：**是现有 Metromover 的上车量，不是出行量、OD、下车量、分时流量，也不是新系统的需求**。

## 接入方式

- 输入包 `ridership_baseline` 变为 `acquired`，值为分站十月均值、最新月、系统份额与窗口，附证据指向。
- 情景包新增 `observed_reference`：量级参照（低／中／高的日出行量约为观测的 3% / 13% / 32%，因为情景只含网内联系）与分布参照（各站份额的秩相关约 0.20，最大差异在 Government Center：观测 20% 对情景 3%，即被排除的 Metrorail 换乘流入）。规则文档新增规则 6b：参照不是校准。
- 登记表与编排器加入 `ridership_reference`；`layers.demand.observed_ridership_status` 变为已取得。

## 验证

[regression_results.json](regression_results.json)：25 个场景、260 项检查。新增 `ridership_reference_stage`（12 项）：阶段 DONE、校验 PASS、21 站每月全部映射、三个改名站被标记、份额和为 1、语义标记为非出行量非分时、就绪视图的观测状态为已取得、输入包字段为 acquired/observed、情景包含参照块、量级比值均小于 1、秩相关在区间内、包与已发布包逐字节一致。首次运行时输入包的结构检查拦下了从参照包复制来的一个嵌套 `{month, value}` 对象，已改为平铺字段。

## 未做

OD 与分时客流仍未取得，情景未校准；三个改名站的对应待业主确认；POI 层与步行模型层未实现。
