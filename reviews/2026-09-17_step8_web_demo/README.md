# 第 8 步 · 静态网页：STAR 叙事 + 能力 + 逐站流程演示（2026-09-17）

业主要求改变优先级：先在网页上讲清这个 AI 产品的 STAR 与个人能力，配一个简单的、展示思考过程的演示；步行路网模型暂停。

## 交付物

- `docs/index.html`：单页静态站点（英文，面向招聘方）。结构：首屏与四个事实条 → STAR 四段 → 六项能力（每项附可核验证据）→ 逐站演示 → 输入台账（观测 / 推算 / 假设 / 未做）→ 八条工作规则 → 来源与包 ID。深浅色两套主题，手机宽度可用，无外部依赖（字体来自 Google Fonts，缺失时回退系统字体）。
- `docs/data/demo_data.js`：由 `scripts/export_web_demo_data.py` 从九个已发布包（先按指针校验整包）导出，只复制不重算；含 21 站四个环带的分区、人口、就业、设施，时刻表与实测上车量，三档情景与 PRT 配置，就绪快照，回归结果计数，以及只用于示意图的简化几何（研究窗口、全网 ½ mile 并集、公园轮廓、设施点、GTFS 服务序列）。
- 演示交互：选站（下拉或点图）、切环带、切情景；六步各显示该站真实数字；**任一数字可点开来源**：来源类别、数据性质、口径、统计期、90% 误差与可靠性、包 ID、证据文件与 ID 模式。地图为示意图（无底图），环带按投影比例画成真圆。
- `scripts/make_artifact_page.py`：去掉文档骨架后生成 Claude Artifact 版本（同一页面）。已发布：https://claude.ai/artifact/3qEKxP7wdmFaLo2a33qbxC（私有，业主可分享）。
- 本地预览：`python3 -m http.server 8765 --directory docs`；GitHub Pages 发布：仓库设置 → Pages → 分支 `main` / 目录 `/docs`。

## 内容边界（与叙事底稿一致）

- 不出现公司名；系统统称 PRT。真实项目只写业主自述已做的事（原始热度需辨别服务相关性、需求分散与场地深度受限、推动较小主站与分散接驳并让四方共同评审）；"识别出货运""周期缩短""公平性审计"等未经证据核对的表述一律不写。
- 页面上的状态标签来自导出时的 readiness 文件，不手填；AI 解读对 V2 为 NOT_RUN，页面明说；V1.1 的规则闸门证据（27 m 曲线 → BLOCKED、生成节点 0 token）链接到公开仓库。
- 每个数字的"不是什么"随来源弹窗给出：五年期估计不是当前人口，岗位联系不是出行，时刻表不是客流，实测上车量不是校准目标，泊位数不是设计。

## 附带处理

- 步行模型（第 7c 步）暂停：抓取脚本与原始 OSM 已归档并校验，构建脚本已写但首次运行超过 10 分钟被停止，未发布任何包；编排器该阶段注释，就绪视图显示 NOT_RUN。README 与记忆已记录恢复方法。
- POI 包新增公园轮廓（`geometry_wgs84`），生产树重建，回归 26 场景 / 272 项全部通过（[step 7b 结果文件](../2026-09-17_step7b_poi/regression_results.json) 已更新）。
- 输入包对"只钉住、无内容"的可选层包（回归假包）做了容错，避免步行模型假包让重建报错。

## 仓库化（2026-09-18）

- 本目录初始化为独立 git 仓库（分支 `main`），与 V1.1 仓库和本地目录互不依赖、互不修改。
- 公开前清理：46 个被指针替换的旧包（326 MB）移到仓库外 `../archive/superseded_packages_2026-09-18/`（附 `MOVED.json`，可移回），`data/` 由 352 MB 降到 41 MB；三份写有公司名的研究底稿、重庆报告的两张页面截图、`.secrets/`、虚拟环境进入 `.gitignore`；一个早期数据文件里的本机绝对路径改为文件名；全树扫描无公司名、无密钥、无邮箱。原根目录 README 改名为 `NOTES_数据接入底稿_2026-09-14.md`，新写面向公开的双语 README。
- 移动旧包后重跑回归：[regression_results.json](regression_results.json) 26 场景 / 272 项全部通过；`readiness --check` 各阶段状态不变。
- 业主已发布公开仓库 https://github.com/TaiNingTy/station-decision-support-v2 。"Deploy from a branch" 方式的 Pages 构建始终没有触发（12 分钟无任何构建记录、接口报站点未创建），改为工作流部署：`.github/workflows/pages.yml`（只检出 `docs/`，上传为 Pages 产物后部署）。首次运行失败：`GITHUB_TOKEN` 无权创建站点（"Resource not accessible by integration"），需业主在 Settings → Pages 把 Source 手动选为 "GitHub Actions" 后重跑；重跑后站点上线：https://tainingty.github.io/station-decision-support-v2/ 与 `presentation.html`、两个数据文件均返回 200。

## 未做

Coze 在 V2 输入上的批跑、Melbourne / Singapore 案例、中文版页面、Squarespace 嵌入。
