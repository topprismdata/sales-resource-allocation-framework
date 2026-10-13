# SRAF · Sales Resource Allocation Framework

销售资源分配决策框架 —— TopPrism 片区规划（模块②）的**决策引擎与规范族**。Part of **TopPrism Decision Intelligence**.

> **决策问题**：经销商/拜访员的片区应该怎么划、划得好不好、要不要重划、怎么重划？
> SRAF 把「世界模型 → 健康诊断 → 缺口分类 → 决策问题合同 → 调整算子 → 方案评估」做成可测试的闭环。

## 仓库结构

| 目录 | 内容 | 状态 |
|---|---|---|
| `docs/sraf/` | **v1.2 规范族**（00 Charter → 08 Canonical Identity，18k 行，含 NORMATIVE_OWNERSHIP 与 SHA256SUMS 完整性清单） | 规范正典 |
| `docs/territory/` | 片区设计（DESIGN / D14 多连通 / FOUR_BOUNDS 重建规范 / 边界匹配理论 / 本体） | 设计文档 |
| `docs/paper/` | 学术论文草稿（bidirectional territory semantics 姊妹篇） | 写作中 |
| `dealer_territory/` | 围栏分配引擎：fence_allocator（四至约束分配）· four_bounds · fence_split（道路/河流切分，基于 market-partition）· fence_from_text · fence_analysis · assignment | 可安装包 |
| `intelligence/` | 分配智能层：world（世界模型）· adjust（迁移/选择算子）· health（健康诊断）· classify · impact · knowledge · roadsem · vision · geom · coords（coords-core shim） | 可安装包 |
| `tools/` | 20+ 工程脚本（编译/评测/可视化/台账） | 脚本，不随包发布 |
| `knowledge_base/` | 04 层的「IQ 源」：机器可读知识项 + 缺口台账 | 数据 |
| `data/` | 数据包目录（发布仓仅含 README；真实围栏数据不随仓发布） | 见测试标记 |

## 安装

```bash
pip install "sraf @ git+https://github.com/topprismdata/sales-resource-allocation-framework.git@v0.1.0"
```

依赖：`shapely` · `numpy` · `coords-core`（坐标帧纪律，组织唯一事实源）· `market-partition`（几何切分引擎）。

## 测试

```bash
python -m pytest tests -q          # hermetic 子集（CI 口径）
python -m pytest tests -m local_data -q  # 需本地数据包（默认排除）
```

`local_data` 标记 = 依赖未发布的区域数据包（如广州路网 pack）；CI 通过 `-m 'not local_data'` 排除，与 Territory-IR 同门禁纪律。

## 核心不变量（测试锁定）

1. **帧纪律**：所有坐标经 `coords_core.frames` 声明制处理，混帧 fail-closed（广州混帧实测 623m 偏差为金标）；
2. **守恒**：调整算子（transfer）前后门店总数不变，同经销商守卫拒绝自迁；
3. **多连通**：1:N 围栏索引（一经销商多不连续簇）为一级公民，切分/合并保持簇结构；
4. **证据链**：诊断（health）→ 缺口（AllocationGap）→ 决策问题（DP01–DP07 合同）逐层可溯源，见 `docs/sraf/02–04`。

## 治理

- 组织元数据：[`topprism.yaml`](topprism.yaml)（maturity 四档制）
- 规范完整性：`docs/sraf/SHA256SUMS.md`
- 版本：git tag（`v0.1.0` 起）；历史 `RC2.0/RC3.0` 为拆仓前快照
- 论文/研究层（analysis/）按白名单评审后入库，默认不发布

## 编制测算与兜底（sraf_intel.sizing / .fallback，v0.2.0 · WP16）

- **覆盖法 sizing**（Zoltners-Sinha 1983，书卡引用见模块 docstring）：
  `RepCapacity`（年可用分钟）× `AccountWorkload`（calls×(duration+drive)）→
  `required_reps` 向上取整；`balance_report` 出分辖区编制+总量编制+EQ+极差比
- **EQ 均衡指数** = (Σx)²/(n·Σx²) ∈ [1/n,1]；零负载辖区计入 n（无主=失衡证据）
- **迁转建议**：贪心确定性（平局全序），每步严格 EQ 增益才保留，
  `MoveProposal.requires_approval` 恒 True——只建议不执行（WP05 纪律）
- **nearby-containers 兜底**：未分配门店→最近可用片区候选（余量>0 硬条件、
  半径、k 截断、(距离,id) 平局全序）；`requires_human_confirmation` 恒 True，
  frozen 不可翻——**不自动合并**
- ⚠️ 书内数值算例不在本地语料（书卡为索引卡）：单测为自洽手核算例锁算术，
  双源逐位核对挂账待 PDF 页（计划 §71 风险预案如实登记）
