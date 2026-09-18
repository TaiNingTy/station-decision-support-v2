# 面试演示入口

打开 `presentation.html`。它与原有 `index.html` 共用 `data/demo_data.js`；前者适合讲解，后者保留详细证据与计算说明。没有修改上游数据或计算管线。

## 约 4 分钟的讲解顺序

1. **The product story（约 60 秒）**：说明站点配置为什么需要规划、工程与运营协作；自己的任务是把专业判断转成可重复、可解释、可审核的产品工作流。STAR 中的结果指当前可验证的原型能力，不是未经证实的业务收益。
2. **Try the workflow（约 2 分钟）**：选一个站点，依次点击 Read the place、Frame demand、Size the station、Explain & review。切换 Low / Medium / High，说明采用率等假设如何影响需求和配置。点击带下划线的数字可以查看来源、口径和假设。
3. **Across markets（约 45 秒）**：Miami 已可演示；Melbourne 与 Singapore 是待运行的迁移方向。强调共享数据契约与决策方法，同时重建当地单位、来源、场地限制和服务目标。

建议用英文解释的主线：

> I translated planning expertise into a repeatable decision-support workflow. The product combines spatial evidence, deterministic calculations and a planned layer of knowledge-grounded AI interpretation, while keeping assumptions and human decision ownership explicit. This public-data demonstration shows how I carry a planning question through to a reviewable station configuration.

## 目前的演示边界

- 使用已导出的 21 站、三档情景和配置结果；切换是读取预计算结果，没有后台实时调用。
- Coze / KB 对 V2 站点包的解释尚未运行，页面标为下一步；没有模拟 AI 输出或加载动画。
- 站台模块依据当前数据包；运营参数与可建设空间仍包含假设。泊位符号仅说明数量，不是布局图或已验证的工程设计。
- 距离圈是英制欧氏代理；步行模型尚未发布，不作真实步行可达结论。
- 页面不依赖外部字体、地图瓦片或第三方脚本。将整个 `docs` 文件夹保留在一起即可本地打开或静态托管。

## 本地预览

在数据基础目录运行：

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory docs
```

然后打开 `http://127.0.0.1:8765/presentation.html`。

更新数据时仍使用现有 `scripts/export_web_demo_data.py`，两个页面会共用新导出结果。正式展示前应确认导出的 package ID 与当前发布指针一致。

## 离线城市底图

`presentation.html` 额外读取 `data/miami_basemap.js`。底图使用已有 OSM 道路、TIGER 水域、人口层街区几何、公园和 GTFS 路线形状生成；不依赖在线瓦片。灰色多边形是街区，不是建筑轮廓。底图仅作展示，不改变步行模型或分析就绪状态。

地图支持 Network / Station area、放大缩小及点击选站；英制比例尺和距离圈基于 EPSG:26917 米制坐标绘制。生成方法与来源哈希保存在 `data/miami_basemap_manifest.json`。

使用已安装 GIS 锁定依赖的解释器重新生成：

```sh
PYTHONDONTWRITEBYTECODE=1 /opt/anaconda3/bin/python3 scripts/export_miami_basemap.py
```
