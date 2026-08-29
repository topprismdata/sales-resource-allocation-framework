# JOURNAL — 试点工作日志（追加式）

> **规则**（详见 `ROUTING.md` §4）：
> 1. 任何 agent 完成任何动作后**必须**追加一条，否则该任务不算完成
> 2. **只许追加，不许修改历史条目**
> 3. 门禁失败（`[GATE-FAIL]`）必须与成功同等留存 —— 本项目最贵的教训是失败被解释掉了
> 4. 子代理产出必须由父代理代为记录并注明
>
> 条目格式见 `ROUTING.md` §4。最新条目追加在文件**末尾**。

---

## 2026-08-30 (P0) | L0 claude-opus-5 | 初始化

- **动作**：克隆仓库、创建分支 `feat/cc-unit-selection-pilot`、建立试点工作区文档
- **输入**：
  - 上游 `main` HEAD = `b879583`（feat(demo): yeidai_ops rewritten as unit-set paradigm）
  - 本地客户数据 6 份（3 geojson + 3 csv），位于仓库外
- **输出**：
  - `sraf-pilot/00_BRIEF.md`（背景与坑，L1 必读）
  - `sraf-pilot/CONTRACTS.md`（唯一真相源，仅 L0 可改）
  - `sraf-pilot/ROUTING.md`（路由规则）
  - `sraf-pilot/JOURNAL.md`（本文件）
  - `sraf-pilot/state.json`
  - `.gitignore` 补充试点条目
- **门禁**：G0 待业务方确认
- **数据条件**：尚未处理任何数据

### [DECISION] 试点范围 = 海珠(440105) + 荔湾(440103)
- **依据**：作者 `docs/basic_units_comparison.md` 就是用「海珠荔湾 11 片」验证的
  （业代 IoU 0.966–0.970），我方数字可直接对标；失败案例「穗穗盛」（IoU 0.12）
  亦在此范围，密集老城区跑通证明力最强
- **决策人**：业务方选定，L0 确认
- **影响范围**：P1 数据抽取的筛选条件；所有 G2/G3/G4 的样本集

### [DECISION] 单元库用官方四级路网 2,675 单元，不用 OSM polygonize
- **依据**：客户已提供
  `边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson`（8.7MB，2,675 要素），
  与作者 §12 所用同一份数据产品。副作用是坐标系风险降低（客户侧数据同系，不混用）
- **风险已知**：作者实测官方单元对**经销商围栏**中位 IoU 仅 0.764（对业代 0.970）。
  故 G2-c 不设预设阈值，< 0.90 触发 P2b（引入 OSM 细面）
- **决策人**：L0
- **影响范围**：P2 全部；P2b 是否触发

### [DECISION] G4 只用现有合成语料
- **依据**：业务方在知悉「四至文本系从真值反推、评测存在循环性」后，
  明确选择只用现有合成文本，不额外采集人工描述
- **代价**：G4 数字不能作为端到端能力对外陈述
- **对策**：CONTRACTS D-2 强制所有 G4 输出带 `[合成语料]` 标签，
  报告模板内置局限性声明
- **决策人**：业务方拍板，L0 记录并设置对策

### [DECISION] `--thinking max` 对 glm-5.3-flash 可能是空操作，仍照加
- **依据**：实测 `omp -p --model glm-5.3-flash --thinking max` 不报错，
  但 omp 模型注册表中 `glm-5.3-flash` 的 effort 档位一栏为空
  （对照 `glm-5.3` 本体明确支持 `low/high/max`）
- **对策**：ROUTING §5 —— 同一门禁连续 2 次失败即升级到 `glm-5.3`
- **决策人**：业务方要求加参数，L0 记录限制与退出条件

### [DECISION] 允许 codex/omp 派发子代理，但受同等约束
- **依据**：业务方授权。`omp` 有 `task`/`agents`/`cleanse` 并行能力，`codex` 有 `agents`
- **约束**：ROUTING R-5 —— 子代理任务同样须封闭、须过门禁、须由父代理代记 JOURNAL
- **决策人**：业务方授权，L0 加约束

### [DECISION] 试点文档用中文
- **依据**：三个 agent 均可读中文；业务术语（街道/围栏/四至）中文更精确；
  这是工作区文档而非 SRAF 规范文件
- **注意**：根 `docs/CHANGELOG_v1.2.3.md` 要求主线文档英文化。
  若本试点将来并入主线，需按该规范翻译
- **决策人**：L0

### 观察：主线代码的两个已知问题（不修，但试点不得复刻）
1. `tools/yeidai_ops.py` 与 `tools/component_matcher.py` 硬编码
   `/Users/ghb/sales-resource-allocation-framework/...`，在他机无法运行
   → CONTRACTS D-4 禁止试点复刻
2. `dealer_territory/fence_from_text.py` 的 `lookup_geometry` 兜底匹配用
   `nm.startswith(name[:2])`（两字前缀），会静默认错地标
   → CONTRACTS §4.3 规定试点名称解析匹配 0 或 >1 一律抛错

- **下一步**：等待业务方 G0 签字 → 推送分支 → L1(codex) 拆 P1 任务卡

---
