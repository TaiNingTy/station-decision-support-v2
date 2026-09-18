# Station Decision Support · V2 data foundation (Miami)

**English** · [中文摘要](#中文摘要) · Public portfolio repository · independent from the V1.1 demo

The real-data foundation and the static web page behind an AI product manager's case study: an AI station-configuration
and decision-support workflow for a personal rapid transit (PRT) system, demonstrated on public data for the 21 stations
of Miami's Metromover. Every number the page shows is copied from a versioned, validated data package and carries its
provenance (observed / derived / assumption), its period and its uncertainty.

- **Live page** (GitHub Pages, served from [`docs/`](docs/)): `https://<github-user>.github.io/<this-repository>/`
- **V1.1 agent pipeline and rule gate** (separate, frozen repository): https://github.com/TaiNingTy/AI-Station-Configuration-Decision-Support-System
- This repository never modifies V1.1 and does not depend on it; the page links to it as evidence.

## What this repository is, and is not

It **is** a reproducible data pipeline for one case (Miami, full-line conversion study as a demonstration): station
entities, zoning bands, residents, jobs and job-to-home links, the timetable, published boardings, facilities, a
low / medium / high scenario chain, PRT sizing per station, readiness flags, a fault-injection regression harness, and
a self-contained web page that reads the exported results.

It **is not** a forecast, a calibration, an engineering design, a validated walk catchment, or an approved project.
The AI interpretation layer for V2 has not been run yet; the readiness view and the page say so. No employer data,
supplier operating data or company name appears here: the method is public, the employer's data is not.

## Layout

| Path | What it holds |
|---|---|
| `docs/` | the static pages: `index.html` (STAR narrative, capabilities, per-station demo with click-to-provenance) and `presentation.html` (a four-minute walkthrough with an offline basemap; see `PRESENTATION_README.md`), both reading the exported dataset `data/demo_data.js` |
| `scripts/` | one script per stage, the readiness aggregator, the orchestrator, the regression harness, the web export |
| `data/miami/2026-09-14/` | station master, study window, per-stage immutable packages `<stage>/pkg-<sha12>/` and their pointers `<stage>_current.json`, the readiness view, the data README (Chinese, detailed) |
| `raw/miami/…/` | the acquired sources with URLs, hashes and retrieval times (TIGER/Line, ACS, LODES, GTFS, DTPW reports, county / city / USDA layers, OpenStreetMap) |
| `config/` | station registry, platform modules (from owner drawings, imperial as drawn), generic PRT operating assumptions |
| `reviews/` | one folder per build step: what was checked, what failed, regression results |
| `V2_站点输入包字段契约.md`, `V2_数据语义与客流转换规则.md` | the field contract and the data-semantics rules written before the code |
| `NOTES_数据接入底稿_2026-09-14.md`, `B1-B6_…`, `V2_面试Demo静态优先架构.md` | earlier working notes (Chinese) |
| `vendor/` | pyshp 3.1.6 vendored; `requirements-gis.lock.txt` is enforced by every geometry stage |

Working notes that mention the employer are kept local and listed in `.gitignore`. Superseded packages are moved out of
the tree (see the data README); the nine current packages are the ones the pointers name.

## Pipeline

```
station_master → spatial_join → demography → jobs → service_baseline → ridership_reference → poi
             → input_package → scenarios → config → readiness --check        (walk_model: written, paused)
```

Rebuild everything, in order, with one interpreter:

```bash
python3 scripts/build_all_miami.py
```

Each stage publishes a content-addressed package and switches one pointer atomically; a stage publishes nothing unless
its validation passed. `python3 scripts/miami_readiness.py --check` derives the readiness view from the packages (single
writer). Requirements: Python 3.13 with the versions in `requirements-gis.lock.txt` (shapely 2.1.2, pyproj 3.8.0); the
ACS fetch needs a Census API key in `.secrets/census_api_key` (never committed); every other source is a plain download
recorded in `raw/`.

Regression: `python3 scripts/test_miami_pipeline_regression.py --out results.json` rebuilds the pipeline in isolated
copies and injects faults (corrupt packages, changed inputs, an optional layer that appears later, a publish that fails
halfway); the latest results live under `reviews/`. Web export: `python3 scripts/export_web_demo_data.py`, then preview
with `python3 -m http.server 8765 --directory docs`.

## Status (2026-09-18)

| Item | Status |
|---|---|
| Station entities, zoning bands, residents, jobs and links, timetable, published boardings, facilities | built, validated, byte-identical on rebuild |
| Station input packages, scenario chain, PRT configuration, readiness | built; scenario results and site space are assumption-backed and labelled |
| Regression harness | 26 scenarios / 272 checks, all passing |
| Web page | built and exported from the packages; English |
| Network walk model | fetched and written, build paused (performance); readiness shows NOT_RUN |
| AI interpretation on V2 inputs, V2 knowledge base and rule pack | not started |
| Melbourne and Singapore cases | not started |
| Owner confirmations (berth counts read from drawings, three renamed stations, constructible site space) | pending |

## Sources and attribution

U.S. Census Bureau (ACS 2020–2024 5-year, TIGER/Line 2024 and 2020 P.L. blocks, LEHD LODES 8 Florida 2023) ·
Miami-Dade County (GTFS static feed, DTPW monthly Ridership Technical Reports, county GIS layers) · City of Miami
(Miami 21 zoning and park boundaries, CC-BY-4.0) · USDA FNS (SNAP retailer locations) · © OpenStreetMap contributors
(ODbL; cross-check and the paused walk model only). Each raw file's URL, size, hash and retrieval time is in the
`source_manifest.json` next to it. Raw files are included so the pipeline reproduces without network access except for
the ACS pull.

## 中文摘要

这是"AI 站点配置与决策支持系统"作品集案例的 V2 数据底座与静态网页，以迈阿密 Metromover 21 站的公开数据演示方法；
与 V1.1（Coze 智能体流水线与规则闸门，独立仓库）分开维护、互不依赖。页面上每个数字都来自带版本与校验的数据包，
并带来源类别（观测 / 推算 / 假设）、统计期与不确定性。**不是**客流预测、校准、工程设计或步行范围验证；V2 的 AI
解读层尚未运行，就绪视图如实标注。仓库不含公司名与任何雇主或供应商数据。

- 一键重建：`python3 scripts/build_all_miami.py`；回归：`python3 scripts/test_miami_pipeline_regression.py`；
  网页导出：`python3 scripts/export_web_demo_data.py`；本地预览：`python3 -m http.server 8765 --directory docs`。
- 详细说明见 [数据 README](data/miami/2026-09-14/README.md)、[字段契约](V2_站点输入包字段契约.md)、
  [数据语义与客流转换规则](V2_数据语义与客流转换规则.md) 与 `reviews/` 下各步的评审记录。
