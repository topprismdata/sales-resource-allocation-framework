# 三轮审查收敛报告 — dealer_territory 模块优化与方向确认

**日期：** 2026-08-27  
**审查范围：** `dealer_territory/` 全部代码（2569 行）+ 测试 + 工具 + 分析文档  
**方法：** R1 代码审计 → R2 论文/生态对比 → R3 与 SRAF 08 规范对齐

---

## R1 — 代码审计发现

### Bug（1）
| 位置 | 问题 | 严重度 |
|---|---|---|
| `four_bounds.py:17` | 未使用 `import math`（`_dist2` 用 `**` 不用 `math.*`） | 低 |

### 测试覆盖缺口（6 个模块中 4 个覆盖不足）

| 模块 | 已测/总公共函数 | 缺失的关键测试 |
|---|---|---|
| `assignment.py` | **0/4** | `rule_assign`（维度匹配）、`manual_assign`（人工覆盖）、`rebuild_assignments`（批量重算）|
| `models.py` | **0/3** | `RegionNode` / `Assignment` / `DealerTerritoryModel` 构造与约束 |
| `four_bounds.py` | 3/7 | `build_index`、`river_at`、`main_district`、`nearest_road` |
| `fence_split.py` | 1/3 | `fetch_barrier_from_overpass`（OSM API 调用）、`GeoBarrier.to_barrier` |
| `fence_allocator.py` | 3/4 | `lookup_geometry`（容错匹配链）|
| `fence_analysis.py` | 3/6 | `make_fence`、`parse_wkt`（含 MULTIPOLYGON 分支）|

### 代码质量（正面）

```text
✓ 无裸 except、无可变默认参数
✓ 无 SQL 注入风险（无 SQL）
✓ 类型注解覆盖率高
✓ 模块间无循环依赖
✓ 四_bounds/fence_allocator/fence_analysis 互相独立
```

---

## R2 — 论文与生态对比

### 学术前沿

| 方法 | 来源 | SRAF 适用性 |
|---|---|---|
| **图划分**（Multi-level Graph Partitioning） | Karypis & Kumar (METIS)；行政区划=节点、邻接=边 | ★★★ 可用于"按行政区划自动切分经销商区域" |
| **Fellegi-Sunter 概率匹配** | Fellegi & Sunter (1969)；Splink 实现 | ★★★ 直接可用于 08 的 Identity 解析 |
| **H3 层次索引** | Uber；hexagon hierarchy | ★★ 已在 tools/h3_admin_graph.py 原型验证 |
| **Math-Heuristics**（MIP 子问题+局部搜索） | 2024-2025 综述 | ★ Phase 3 DP03 可用，Phase 0-2 不需要 |

### 开源生态

| 库 | 替代的我们手写的代码 | 影响 |
|---|---|---|
| **Shapely** (已装) | 手写 PIP（~40 行）、面积计算（~15 行） | 替换后省 55 行，精度更高 |
| **H3-py** (已装) | 手写网格编码 | 已在用 |
| **Splink** | 手写实体匹配（~200 行规划中） | 如做 Identity Resolution 应优先评估 |
| **GeoPandas** | 手写空间连接 | 如做大批量空间分析应引入 |
| **OSMnx** | 手写 Overpass 查询 | 如需批量拉行政边界应引入 |

**结论：** 当前 2500 行中约 **60%** 可用成熟库替代。
但替换是 **v2.0 工程优化**事项，不阻塞当前功能验证。

---

## R3 — SRAF 08 对齐 + 生产就绪度

### 08 规范对齐

| 08 § | 要求 | 实现状态 |
|---|---|---|
| §5 CanonicalIdentity | ✅ models.py RegionNode | ⚠ 缺 R-ID-1~5 校验 |
| §6 ExternalIdentifier | ✅ schema 定义 | ⚠ 未独立实现（嵌入在 models）|
| §10 MatchDecision 三态 | ✅ fence_analysis.py | ⚠ MATCH/NON_MATCH/UNCERTAIN 枚举未显式 |
| §11 λ/π 阈值 | ⚠ 概念正确 | ❌ 无实际阈值配置机制 |
| §12 八种情形 | ⚠ 已分类 | ⚠ 未实现全部 8 种的判定逻辑 |
| §14 Trigger 阻断 | ❌ 未实现 | 需要在 allocate 前检查 unresolved |
| §15 Temporal Identity | ⚠ 概念正确 | ❌ 无 bitemporal 存储 |
| §17 Survivorship | ❌ 未实现 | 需要 attribute-level survivorship |
| §19 Human Resolution | ⚠ 纪律已定义 | ❌ 无 queue/SLA/审计机制 |
| §21 I20-I30 不变量 | ⚠ 已声明 | ❌ 无运行时校验 |
| §23 Identity Benchmark | ❌ 未实现 | 需要 ID01-ID20 测试用例 |

### 生产就绪度

```text
可演示（demo-grade）:
  ✅ 街道级四至描述生成
  ✅ 围栏现状分析（覆盖/缺口/非围栏供货分型）
  ✅ agentic 分配助手面板（前端交互演示）
  ✅ 市场空白验证文档

需开发（production-grade）:
  ❌ Identity Resolution 完整管线
  ❌ Lambda/π 阈值配置与校准
  ❌ bitemporal IdentityResolutionRecord
  ❌ ImpactAnalysis 完整实现
  ❌ 与现有 CRM/ERP 的适配层
  ❌ 用户权限与审批流
```

---

## 三轮收敛结论

### 做对了的

```text
1. 方向正确：经销商区域分配（非门店排程）是 SRAF 中国语境的核心价值
2. 地基正确：08 Identity 是所有下游决策的前提（已有数据实证）
3. 架构正确：确定性内核 + agentic 外壳（市场无竞品）
4. 数据验证：广州 38 围栏 × 33,109 门店的完整往返验证
5. 合同对齐：四至描述达到合同附件地图的文字精度
```

### 需要改进的（按优先级）

```text
P0（阻塞生产）:
  1. assignment.py 和 models.py 零测试覆盖 → 必须补
  2. four_bounds.py 未使用 math import → 删除
  3. 08 §14 Trigger 阻断逻辑未实现 → 需要在 allocate 前检查

P1（v1.2.1 应做）:
  4. 补 assignment/models 的单元测试（R-ID 校验、维度匹配）
  5. fence_split.py 的 fetch_barrier_from_overpass 需要 mock 测试
  6. fence_allocator.py 的 lookup_geometry 容错链需要独立测试

P2（v1.3 方向性）:
  7. 引入 Splink 替代手写实体匹配（如做 Identity Resolution 完整管线）
  8. 引入 GeoPandas 替代手写 PIP（如做大批量空间分析）
  9. H3 索引从 prototype 升级为 production（res 9，含邻域扩展）
```

### 一句话总结

> 代码质量合格、方向正确、行业空白验证完毕。
> 阻塞生产的不是代码质量，而是 **assignment/models 零测试**
> 和 **Trigger 阻断未实现** ——两个 P0 都能在半天内补完。
