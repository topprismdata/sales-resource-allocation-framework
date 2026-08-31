# CC_main 修复契约 v1.0

> **规格所有者：用户（cai）。** 任何层级不得自行修改本文件。
> 发现规格缺陷 → 写升级条目到 JOURNAL.md → 上升给所有者裁决。

## 0. 背景与判据

基点 `b82e46e`(RC1.0)。修复判据是 **稳定实现最终效果**：
换一台机器、换一个人，能不能跑出来、跑出来的东西可不可信。
不以代码风格/规范为验收依据。

## 1. 冻结事实（已实测，不得推翻，不得重新论证）

### 1.1 坐标系（关键，误判代价 623m）

| 事实 | 值 | 证据 |
|---|---|---|
| 围栏 CSV 与路网/区划 geojson 的坐标系 | **同为 GCJ-02** | `data/pilot/crs_evidence.json` verdict=`SAME_CRS_GCJ02` |
| 同系直接比对误差 | 0.0017 m | median_A_m |
| 若误判为 WGS84 的位移 | **623.8 m** | median_C_disp_m |

契约：`region.json` 声明 `crs=GCJ-02`；服务端 `pack_from_disk()` 加载时一次性转 WGS-84 供内部几何使用；写回时反转。**内部绝不混用两系。**

### 1.2 根数据位置（全部在本地，无需外部索要）

目录：`/Users/cai/Desktop/达能-SRP-AI/客户数据/`

| 文件 | 用途 | 规格 |
|---|---|---|
| `边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson` | **单元库 U 的源头** | 2675 个 Polygon feature；properties 含 `街道[内置]`、`区[内置]` |
| `区划数据-街道-广东省-广州市.geojson` | 街道行政面 | 174 个；properties 含 `行政区名称` |
| `区划数据-区县-广东省-广州市.geojson` | 区县面 | — |
| `广州办事处经销商围栏数据-20260827.csv` | `region.json` 的 fences | 71 行，schema 见 1.3 |
| `广州清单内业代的围栏数据-20260824.csv` | 业代围栏 | 同构 |
| `广州及华南MT办事处业代图层围栏数据-20260824.csv` | MT 业代围栏 | 同构 |
| `广州.xlsx`、`副本进离店报表导出 (4).xlsx` | 门店数据（待确认） | **必须用 officecli 读，禁止 pandas/openpyxl** |

### 1.3 围栏 CSV schema（内联，不要去猜）

字段（10 个，表头带 BOM，用 `encoding='utf-8-sig'`）：

```
片区id, area_code, 业代组织编码, 围栏名称, layer, 中心点经度, 中心点纬度, 围栏面积, area_level, fence
```

| 字段 | 映射到 region.json | 说明 |
|---|---|---|
| `片区id` | `area_id` | 如 `694236818` |
| `围栏名称` | `dealer` | 经销商全称 |
| `围栏面积` | `area_km2` | float，单位 km² |
| `fence` | `rings` | **WKT POLYGON 字符串**，需 shapely 解析后转坐标数组 |
| `中心点经度/纬度` | `center` | GCJ-02 |

**⚠️ 已知坑（必须处理）**：`fence` 字段长度超过 Python csv 默认上限 131072，
直接 `csv.DictReader` 会抛 `_csv.Error: field larger than field limit`。
必须先 `csv.field_size_limit(sys.maxsize)`。

**⚠️ 数据范围**：CSV 含非广州围栏（首行为韶关始兴，经纬 114.08/24.81）。
是否过滤属规格问题 → **不得自行决定，上报所有者。**

### 1.4 数据文件分类（27 个依赖的溯源结论）

- **根数据**（只读不写，来源见 1.2）：路网/街道 geojson、围栏 CSV、门店 xlsx
- **可重建**：`osm_parsed.json`、`gz_osm_full.json` ← `tools/fetch_region_osm.py`（Overpass）
- **派生产物**（跑脚本即得，不得手工伪造）：`unit_attributes.json`、`basic_units_hybrid.json`、
  `territory_compiled.json`、`fence_registry.json`、`desc_cover_eval.json`、
  `all_dealer_descriptions*.json`、`yeidai_compiled.json`、`match_result.json`、`desc_vs_units.json`

### 1.5 语料现状（Phase 5 前提，不得美化）

- main 的 `contracts.json` four_bounds：**从真实围栏反推**（证据：`tools/bench_rebuild.py:4` 原注释）
- pilot 的 G4 21 条：**同样从真值反推**，已自标 `[合成语料]`（证据：`data/pilot/G4_REPORT.md`）
- **结论：两条线都没有真实客户合同文本。** 任何一方都不得宣称"真实端到端能力"。

## 2. 门禁分级（不可协商）

### 2.1 确定性组件 → 100% 逐例完全相等，禁止阈值

适用：路径解析、数据包校验、集合运算、歧义判定、方位判定、降级标记。

> 禁止使用 Jaccard/IoU/相似度阈值放行。
> 依据：231 条中错 1 个时，J=0.991 会被 `≥0.99` 放行，而那 1 个背后是规格完备性破缺。

### 2.2 含数据/模型不确定性 → 统计指标，且必须分表

适用：`J_recall`（真实文本→单元集）。无预设通过线，只报数。

### 2.3 天花板与端到端永不合并

- **表 A 天花板**：给定正确输入，机制能否精确复现 → 判定 100%
- **表 B 端到端**：从真实输入出发 → 报统计指标
- 合成一个数字会同时误导两边。**禁止合并。**

### 2.4 防循环论证

期望值必须来自被测代码之外。若语料从真值反推，**必须逐条打 `[合成语料]` 标签
并内置局限性声明**，禁止表述为"端到端能力"。

## 3. 升级协议（禁止代答）

```
codex 遇歧义 → 【不得自行裁决】→ 写 JOURNAL 升级条目 → Claude 复核
     ↓ luna/max 失败
  切 sol/high 重试一次（同一任务卡）
     ↓ 仍失败
  升级 Claude → 若涉及规格本身 → 【Claude 不得替所有者决定】→ 上升用户
```

**子代理同受全部约束**：codex 可用 `collaboration.spawn_agent` 派发，
但子代理同样须持封闭任务卡、同样禁止代答、同样留档。

## 4. 失败留档纪律

门禁失败、挂死、走错的归因**全部写入 JOURNAL.md**，不许悄悄重试后只留成功记录。
**归因被推翻时，旧归因保留并标注"已于 X 被推翻"**，避免重走错路。

## 5. Phase 定义与验收

| Phase | 目标 | 门禁类型 |
|---|---|---|
| 0 | 数据包重建（`data/gz`） | 确定性 100% |
| 1 | 路径去硬编码（26 文件） | 确定性 100% |
| 2 | 启动可诊断 | 确定性 100% |
| 3 | 消除静默降级 | 确定性 100% |
| 4 | 语义正确性（歧义/方位） | 确定性 100% |
| 5 | 评测口径改造（双表） | 分表：A=100%，B=统计 |
| 6 | 清理固化 | 确定性 100% |

**验收由 Claude 独立执行，不采信 codex 自报成功。**
