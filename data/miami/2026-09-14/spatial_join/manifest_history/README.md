# 空间连接阶段 · 历史 manifest（v1.0 / v1.1 平铺布局）

v1.2（2026-09-14 第二轮复查后）起，空间连接产物以**内容寻址的不可变包目录** `spatial_join/pkg-<id>/` 整包发布，
由 `spatial_join_current.json` 指针指向当前包；旧包目录原样保留即为归档，不再生成 `prev-<sha8>` 副本。

此目录保存 v1.2 之前平铺在 `data/miami/2026-09-14/` 根目录下的两份 manifest，仅供追溯：

- `spatial_join_manifest.prev-c5c15918.json`：v1.1 脚本的前一次构建（上游 F3 修正之前）的 manifest，由当时的
  `prev-<sha8>` 归档规则保存；与下一份只差上游 manifest 哈希及由此带来的产物哈希。
- `spatial_join_manifest.json`：v1.1 最后一次构建的 manifest（第一轮审查修正后；平铺布局，逐文件替换发布）。

两份的脚本 sha256 相同（同为 v1.1 脚本）；schema 均为 `miami-spatial-join-manifest/1.0`。

v1.1 的 8 个平铺产物已删除：它们的分析内容与 v1.2 首个包 `pkg-113ee767a2ca` 内的 8 个文件逐项核对一致（当前包 ID 以 `spatial_join_current.json` 为准；之后因依赖锁文件加入 pyshp 而重发过包，分析产物逐字节不变），
差异仅在于 `upstream.manifest_sha256`（上游 manifest 因 R2 改动而变化）与几何修复诊断中改名的字段
（`projected_area_before_m2` → `projected_area_buffer0_baseline_m2` 等）。核对记录见
`reviews/2026-09-14_miami_spatial_join_recheck/RESPONSE.md`。
