# ROUTING — Agent 路由规则

> **读者**：L1 项目经理（codex）必读。L0 维护。
> L2（omp）不读本文件，其约束由任务卡内联传达。

---

## 1. 三层职责

| 层 | 执行者 | 模型 | 职责 | **禁止** |
|---|---|---|---|---|
| **L0 架构** | Claude Opus 5（人机同席） | `claude-opus-5` | 契约、DSL 设计、验收标准、所有判断题拍板、Phase 收尾签字 | 不写大段实现 |
| **L1 项管** | codex CLI | `gpt-5.6-sol` + effort `high` | 拆封闭任务卡、排依赖、跑门禁、交叉评审 L2 产出、维护 `state.json`、汇总状态 | **不得自行做架构决策；不得修改 CONTRACTS.md** |
| **L2 施工** | omp CLI | `glm-5.3-flash` + thinking `max` | 按任务卡写代码 + 单测 | **不得做设计判断；遇歧义必须上报，不得自行取舍** |

### 调用命令

```bash
# L1 项目经理
codex exec -m gpt-5.6-sol -c model_reasoning_effort="high" "<指令>"

# L2 施工（只喂一张任务卡）
omp -p --model glm-5.3-flash --thinking max @sraf-pilot/tasks/T-XXX.md "按卡执行"
```

**已知限制**：`glm-5.3-flash` 在模型注册表中未列出任何 reasoning 档位，
`--thinking max` 实测不报错但**可能是空操作**。见 §5 升级条件。

---

## 2. 路由规则（5 条，L1 必须执行）

### R-1 任务卡不封闭，不许派给 L2

一张合格任务卡**必须齐三样**，缺一不得下发：

1. **明确输入**：文件路径（相对仓库根）+ schema 片段**内联**在卡里
2. **明确输出**：文件路径 + schema
3. **可执行的验收断言**：`assert` 级别的具体判据，不是「看起来对」

> 快模型的失败模式是「在大文档里抓不住重点」。把 schema 内联进卡，
> 不要让 L2 自己去 `CONTRACTS.md` 里找。

### R-2 L2 产出必须过门禁脚本才算完成

L1 跑门禁 → 不过则打回并附失败输出 → **最多重试 2 次** → 仍不过则上升 L0。

### R-3 L2 报「歧义」时，L1 不得代答

必须写 `JOURNAL.md` 的 `[ESCALATION]` 条目并停下，等 L0 回复。

> 理由：防止快模型的错误判断被 PM 层固化成既成事实。这正是主线
> K-PRIN-008「手绘噪声论」一天内被推翻两次的成因。

### R-4 每个 Phase 结束由 L0 人工 review 签字，才进下一 Phase

### R-5 子代理同受本文件全部约束

`omp` 的 `task` 工具、`codex` 的 `agents`、`omp cleanse` 的并行子代理均**允许使用**，
但：
- 子代理的任务同样必须封闭（R-1）
- 子代理的产出同样必须过门禁（R-2）
- **每个子代理完成后必须由其父代理在 JOURNAL 追加一条记录**，注明是子代理产出

> 并行会放大快模型的错误。没有留痕的并行，事后无法定位是哪一路出的错。

---

## 3. 交接协议：靠文件，不靠对话

三个 agent 上下文互不共享。**唯一的交接媒介是这 5 个文件。**

| 文件 | 写 | 读 |
|---|---|---|
| `CONTRACTS.md` | **仅 L0** | L1 全文；L2 不读（由任务卡内联） |
| `00_BRIEF.md` | 仅 L0 | L1 全文；L2 不读 |
| `ROUTING.md` | 仅 L0 | L1 |
| `tasks/T-XXX.md` | L1 | L2（**只读自己那一张**） |
| `state.json` | L1 | L0/L1 |
| `JOURNAL.md` | **所有人（追加）** | 所有人读末尾若干条 |

---

## 4. JOURNAL 写入规范（强制）

**任何 agent 完成任何动作后必须追加一条，否则该任务不算完成。**
**只许追加，不许修改历史条目。**

### 标准条目

```markdown
## 2026-08-30 14:23 | L2 omp:glm-5.3-flash | T-102
- 动作：实现 03_dsl.py 的 in_street 原语
- 输入：data/pilot/units.json (N=412), data/pilot/streets.json
- 输出：sraf-pilot/src/03_dsl.py, sraf-pilot/tests/test_dsl.py
- 门禁：G3-a PASS (37/37 断言)
- 数据条件：海珠+荔湾，官方四级路网单元，GCJ-02
- 备注：「海珠荔湾07」重复名按 T-101 决议取面积大者
```

### 三种特殊标记

```markdown
## ... | [DECISION]
- 决策：<做了什么判断>
- 依据：<数字/文档/上位约束>
- 决策人：L0
- 影响范围：<哪些下游会受影响>

## ... | [ESCALATION]
- 上报人：L2
- 歧义：<具体是什么说不清>
- 我的两种理解：A... / B...
- （L0 回复必须追加在同一条下面，不另起）

## ... | [GATE-FAIL]
- 门禁：G3
- 失败：<断言名> expected X got Y
- 原始输出：<粘贴关键行>
- 处置：重试第 N 次 / 上升 L0
```

**`[GATE-FAIL]` 是硬要求**：失败记录必须与成功记录同等留存（CONTRACTS D-3）。
本项目最贵的教训就是失败被解释掉了。

---

## 5. 模型升级条件

| 触发 | 动作 |
|---|---|
| L2 在同一门禁**连续 2 次**失败 | 从 `glm-5.3-flash` 升级到 `glm-5.3`（真支持 `low/high/max`），并在 JOURNAL 记 `[DECISION]` |
| 升级后仍失败 | 上升 L0，L0 可能亲自实现该模块 |
| L2 报告任务卡本身有矛盾 | 不升级模型，回到 L1 重写任务卡（这是 R-1 没做到位） |

---

## 6. 安全约束（凭证与推送）

1. GitHub token 位于 `/Users/cai/Desktop/ghkey.txt`（**仓库外**）。
   只以环境变量方式读取，**禁止打印、禁止写入任何文件、禁止提交**。
2. 只在 `feat/cc-unit-selection-pilot` 分支操作。**禁止** push `main`、
   **禁止** `--force`。
3. 推送前必须 `git status` 确认无 `data/`、`*.geojson`、`*.csv`、`ghkey*` 被暂存。
4. **L1/L2 无推送权限**：所有 `git push` 由 L0 执行并向业务方确认。
   L1/L2 只做本地 commit。
