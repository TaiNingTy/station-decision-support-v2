# Miami · V2 原始数据获取（第 2 步，2026-09-15）

按 [字段契约第 1 节](../../../V2_站点输入包字段契约.md) 锁定的版本获取，脚本 [`scripts/fetch_miami_v2_raw.py`](../../../scripts/fetch_miami_v2_raw.py)。
每个文件的 URL、字节数、sha256、HTTP Last-Modified / ETag、获取时刻和发布方校验状态在 `source_manifest.json`；
完整性与契约变量检查在 `acquisition_validation.json`。脚本可重复运行：哈希已匹配的文件只复核不重下。

**当前状态：PASS（2026-09-15 完成）。** 37 个来源全部取得，59 项硬性检查全部通过。Census API 的数据拉取需要密钥：
密钥由本人申请后写入 `.secrets/census_api_key`（该目录 git-ignored）或设置环境变量 `CENSUS_API_KEY`；脚本经 stdin
把它传给 curl，不进入进程参数，也不写入任何清单（清单里只记录 `api_key_used: true`）。

## 已取得

| 组 | 文件 | 内容 | 校验结果 |
|---|---|---|---|
| tiger | `tl_2024_12_bg.zip` | TIGER/Line 2024 佛州 block group（2020 划分） | 全州 13,388 个，Miami-Dade 1,843 个，GEOID 12 位 |
| tiger | `tl_2020_12086_tabblock20.zip` | TIGER/Line 2020 P.L. 94-171 版 Miami-Dade 2020 街区 | 31,622 个街区全部属县 086；其中 1,075 个 `ALAND20 = 0` 的纯水域街区 |
| tiger | `tl_2024_12086_areawater.zip` | TIGER/Line 2024 Miami-Dade 水域面要素 | 2,380 个要素，AWATER 合计与街区 AWATER20 合计相差 0.004% |
| lodes | `fl_wac/rac_S000_JT00/JT01_2023`、`fl_od_main/aux_JT00/JT01_2023`、`fl_xwalk` | LODES 8，佛州 2023，Data Vintage 20251202_1657，格式 8.4 | 九个文件全部与发布方 `lodes_fl.sha256sum` 一致。注意：发布方列的是**解压后 CSV** 的 sha256，清单同时记录压缩包与解压内容两个哈希 |
| lodes | `lodes_fl.sha256sum`、`version.txt`、`LODESTechDoc8.4.pdf` | 发布方校验文件、版本说明、技术文档 | 原样保存 |
| acs | `acs5_2024_bg_12086_<表>.json` × 11 | ACS 2020–2024 五年期各表，Miami-Dade 全部 block group，`group()` 拉取即含 E / M / EA / MA 全部列 | 每表 1,843 行，GEOID 集合与 TIGER 2024 县内 block group 完全相同；契约变量全部在列。特殊值只出现在 B19013 收入中位数：215 个 block group 样本不足无估计（`-666666666`，MOE `-222222222`），33 个中位数落在开放区间（MOE `-333333333`），与契约第 7 节的缺失状态映射一致 |
| acs | `groups/<表>.json` × 11 | 各表字段字典（标签、概念、宇宙） | 契约列出的全部变量都在字典里；关键标签断言通过：`B08301_003E` 独自驾车、`_004E` 合乘、`_010E` 公共交通、`_017E` 摩托车、`_018E` 自行车、`_019E` 步行、`_021E` 在家办公；`B25044_003E` / `_010E` 无车；宇宙与契约一致 |

## 跨来源一致性检查

- 2020 街区的 12 位前缀集合与 2024 block group 集合完全相同；每个 block group 的街区并集与其多边形的对称差最大 0.38%，没有超过 0.5% 的。两个 TIGER 版本可以配合使用。
- 街区 `ALAND20` 按 block group 求和与 2024 block group 的 `ALAND` 相比，3 个 block group 差异超过 1%，最大 3.96%，属于版本间边界与水域修订，只作记录；正式陆地面积按契约用擦除水域后的几何计算。
- LODES 交叉表中县 086 的街区集合与 TIGER 2020 街区集合完全相同（31,622 个）。
- JT00 对账：WAC 县内岗位 1,244,071 = OD main 工作地在县内 1,239,144 + OD aux 工作地在县内、居住地在州外 4,927。
- RAC 县内居民持有岗位 1,171,050 比 OD main 居住地在县内 1,162,746 多 8,304，即县内居民在州外工作的岗位；这些联系只在其他州的 aux 文件里，本项目不取，是契约里已声明的缺口，占比约 0.7%。
- OD main JT00 全州 8,416,045 行；两端都在县内 906,722 份岗位联系，仅居住地在县内 256,024，仅工作地在县内 332,422。这些是县级计数，研究窗口子集在第 3 步生成。

## 版本说明

街区用 2020 P.L. 版县级文件（6.8 MB）而不是 2024 版州级文件（190 MB）：两者都是 2020 普查街区，LODES 8 以 2020 街区为地理；上面的嵌套检查证明它与 2024 block group 一致到 0.4% 以内。读取 shapefile 用随项目携带的 `vendor/shapefile.py`（pyshp 3.1.6，MIT），版本写入依赖锁。
