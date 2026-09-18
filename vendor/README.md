# vendor/ · 随项目携带的纯 Python 依赖

| 文件 | 来源 | 版本 | sha256 | 许可 |
|---|---|---|---|---|
| `shapefile.py` | PyPI 包 `pyshp`，wheel `pyshp-3.1.6-py3-none-any.whl`（wheel sha256 `be8cd9436dcbde477c63ea789f7dcdea3af19f17ea84f2744bfc12efe9145d1e`），用 `python3 -m pip download pyshp --no-deps` 取得 | 3.1.6 | `211b44002f628ea9ad697b365a413fbac73e801f2b2337b391ca91c29eeffec5` | License-Expression: MIT; License-File: LICENSE.TXT |

用途：读取 TIGER/Line shapefile（block group、2020 街区、水域面要素）。脚本通过 `sys.path.insert(0, ROOT/'vendor')` 导入，
并按 `requirements-gis.lock.txt` 中的 `pyshp==` 行做运行时版本门禁；不安装到系统环境。
