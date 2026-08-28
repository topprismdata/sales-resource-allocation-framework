<p align="center">
  <img src="https://raw.githubusercontent.com/topprismdata/.github/main/assets/brand/topprism-repo-header.png" alt="TopPrism dual-prism visual" width="100%" />
</p>

# SRAF — 经销商区域分配智能决策框架

> **语言 / Language:** 中文为主 · English overview follows。
>
> **English overview:** SRAF is a dealer-territory decision design framework combining a business world model, governed knowledge, and evidence-linked recommendations. Recommendations remain subject to human review.


> SRAF = 给经销商区域管理装大脑。围栏绘制/门店归类/排班引擎是"怎么做"的肌肉；
> 本框架补上"为什么"的大脑：哪个店是谁的（身份）、缺口是真的还是假的（诊断）、
> 改了会怎样（影响预测）、该怎么改（带证据链的建议）。

```text
智能 = 世界模型（骨架） + 知识库（血肉） + 推理（给人建议）
产出定位：建议给人，不是自动决策——每条建议自带证据链。
```

## 仓库结构

| 路径 | 内容 |
|---|---|
| `docs/` | 规范集 00-08（**v1.2.1 FROZEN**：章程/世界模型/决策本体/问题合同/分配智能/编排/评测/参考架构/身份解析）+ CHANGELOG 治理文件 |
| `docs/DESIGN.md` | 实施阶段总体设计（活文档）+ ADR 决策记录（D1-D13） |
| `intelligence/` | 世界模型切片、区域调整引擎（区域优先 + 逻辑围栏合并）、GCJ-02⇄WGS-84 坐标系边界归一、道路语义、视觉终审、LLM 语义解析 |
| `dealer_territory/` | Layer-D 围栏切分/分配/四至/分析 6 模块 |
| `knowledge_base/` | 31 条有出处知识条目（json 机器可读 + md 人读索引） |
| `tools/` | 区域数据包热切换 Demo（stdlib server + Leaflet 单页前端）、OSM 抓取、包校验 |
| `data/README.md` | 数据包 schema 与坐标系（crs）契约 |

## Demo 三步流程

1. **合同 → 区域**：四至文本 → OSM 地标重建围栏草案 + 冲突检测（错位/重叠/缺口）
2. **区域语义调整**：`把 @甲 的东部片区划给 @乙` —— 决策对象是【片区】，
   门店归属是附带效果（店随区域走）；规则主路径 + LLM 兜底；提案带面积/门店/
   契约信号证据链；应用=逻辑合并（门店重分配，围栏=门店派生视图）
3. **分析**：围栏健康排名（Q1）+ 覆盖缺口四分类（Q2）

运行：`python3 tools/demo_server.py`（业务数据包 `data/*` 不入库，
按 `data/README.md` 自备；坐标系声明 GCJ-02 的包加载时自动归一为 WGS-84）。

## 关键工程决策（ADR 摘录）

- **D11 区域优先 + 逻辑围栏合并**：划转只重分配门店归属（唯一事实），
  围栏 = 经销商门店点集凸包的派生视图；废弃多边形 union/difference 手术
- **D12 规则优先、LLM 兜底**：@ 提及引擎保证 LLM 只见全名
- **D13 坐标系边界归一**：数据包按 `meta.crs` 声明；加载 GCJ→WGS 一次、
  写盘逆转换、内部纯 WGS-84——混系 = 广州实测 ~623m 系统偏移
- **D10 三级独立决策层**（D/B/V）：仅接口交接，禁止跨层干预

## 不做什么（Non-goals）

不做 LLM 端到端诊断；不自动执行（建议止于人审）；不跨层开方子；
v0 不做在线学习。业务数据与凭证一律不入库。

## TopPrism status

| Field | Value |
|---|---|
| Purpose | Customer Decision · Integrated Framework |
| Maturity | Implementation phase / demonstrator |
| Evidence | Published specifications, operational snapshot artifacts and test/demo paths; scenario-bound, not a universal performance claim |
| Boundary | Produces evidence-linked recommendations for human review; does not silently auto-decide or cross layer contracts |
| Related | `market-partition`, `visit-scheduling-optimizer` |
