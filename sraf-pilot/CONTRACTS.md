# CONTRACTS — 试点唯一真相源

> **状态**：v1.0（2026-08-30）
> **所有权**：只有 **L0（架构，Claude Opus 5）** 可修改本文件。L1/L2 发现问题 →
> 写 `JOURNAL.md` 的 `[ESCALATION]` 条目，等 L0 回复，**不得自行修改本文件**。
> **继承**：本文件继承仓库根 `AGENTS.md` 的全部约束（领域纠正 D11–D14、数据契约、
> 知识库规则、代码约定）。以下为**试点补充**，冲突时以根 `AGENTS.md` 为准。

---

## 1. 硬纪律（违反即作废，共 9 条）

| # | 规则 | 理由 |
|---|---|---|
| **D-1** | **G3 与 G4 必须分两张表报，永不合并为单一数字** | 本项目已两次把天花板当成绩（bbox 掩盖信号、IoU 0.897 反查得来） |
| **D-2** | **所有 G4 输出必须带 `[合成语料]` 标签** | 四至文本是从真值反推的，评测循环。业务方知情决策，但必须标注 |
| **D-3** | **门禁失败必须留档**，不许悄悄重试后只留成功记录 | 失败被解释掉是本项目最贵的教训 |
| **D-4** | **禁止硬编码绝对路径**（如 `/Users/xxx/...`），一律相对仓库根或 CLI 参数 | 主线 `tools/yeidai_ops.py` 已犯此错，在别的机器上跑不了 |
| **D-5** | **客户业务数据永不入 git**：`data/`、`*.geojson`、`*.csv` 一律 gitignore | 根 `AGENTS.md` 数据契约 + 客户合规 |
| **D-6** | **凭证永不入 git、永不打印、永不写进任何文件** | `ghkey.txt` 是组织级 admin token |
| **D-7** | **只在 `feat/cc-unit-selection-pilot` 分支操作**；不碰 `main`；不 `force-push` | 作者在 main 上高频提交 |
| **D-8** | **围栏的本体是单元 id 集合，几何是派生缓存**，不得倒退为几何优先 | 对齐主线 2026-08-29 15:30 提交 |
| **D-9** | **多块领地不做任何特殊处理**，只在输出时报告 `components: N` | K-PRIN-007 / D14：连通性是业务偏好，非本体约束 |

---

## 2. 试点范围（冻结）

```
地理  广州市 海珠区(区县编码 440105) + 荔湾区(区县编码 440103)
单元  官方四级路网 2,675 单元中区县编码属于上述两区者
主线  业代片区（预期 IoU ≥ 0.95）
压测  经销商围栏（无预设阈值，先测基线）
```

---

## 3. 数据契约

### 3.1 输入（只读，不得修改源文件）

源目录常量名 `SRC_DIR`，由 CLI 参数传入，试点默认值：
`/Users/cai/Desktop/达能-SRP-AI/客户数据`

| 逻辑名 | 文件名 | 关键字段 |
|---|---|---|
| `UNITS_SRC` | `边界数据-路网-到区县带海岸线-四级路网-广东省-广州市.geojson` | `区县编码`、`街道[内置]`、`中心点`、`面积`、`主键` |
| `STREETS_SRC` | `区划数据-街道-广东省-广州市.geojson` | `行政区名称`、`区域编码`、`父级id` |
| `DISTRICTS_SRC` | `区划数据-区县-广东省-广州市.geojson` | `行政区名称`、`区域编码` |
| `DEALER_SRC` | `广州办事处经销商围栏数据-20260827.csv` | `围栏名称`、`fence`(WKT)、`中心点经度/纬度`、`围栏面积` |
| `YEIDAI_SRC` | `广州清单内业代的围栏数据-20260824.csv` | 同上 + `办事处名称` |

**CSV 读取注意**：`fence` 字段极长，`csv.field_size_limit(sys.maxsize)` 必设；
编码 `utf-8-sig`。

### 3.2 坐标系（P1 必须验证，不许假设）

- 三份 geojson 无 `crs` 声明；两份 CSV 无声明。
- **假设**：全部为 GCJ-02（客户 CRM / 高德系，与根 `AGENTS.md` D13 的数据包默认一致）。
- **P1 必须给出数字证据**：取经销商围栏顶点，分别在 GCJ 直比与转 WGS 后比，
  对照单元边界求最近距离中位数。若两者一致（同系），偏差应显著小于 D13 记录的
  广州 ~623 m 系统性偏移。
- **试点内部不混用坐标系**：全部数据同系即可，不做转换（除非 P3b 引入 OSM）。
  转换如需进行，复用 `intelligence/coords.py`，不得另写一套。

### 3.3 中间产物（全部写入 `data/pilot/`，已 gitignore）

| 文件 | schema |
|---|---|
| `units.json` | `{"crs":"GCJ-02","units":[{"uid":int,"key":str,"district_code":str,"street":str,"area_km2":float,"centroid":[lon,lat],"geom":"<WKT>"}]}` |
| `unit_graph.json` | `{"adjacency":{"<uid>":[uid,...]},"link_min_m":50}` |
| `streets.json` | `{"streets":[{"name":str,"code":str,"district_code":str,"geom":"<WKT>"}]}` |
| `districts.json` | 同上结构 |
| `fences_dealer.json` | `{"fences":[{"name":str,"src_id":str,"area_km2":float,"center":[lon,lat],"geom":"<WKT>"}]}` |
| `fences_yeidai.json` | 同上 |
| `oracle_unitsets.json` | `{"<fence_name>":{"unit_ids":[int,...],"coverage":float,"straddle":int}}` |
| `data_issues.md` | 脏点处理记录（人可读） |

**`uid` 稳定性契约**：`uid` = 在 `units.json` 中的数组下标，一旦 P2 产出即冻结。
后续任何重建必须保证同一 `key`（源文件 `主键`）映射到同一 `uid`，否则所有
下游结果作废。P2 需产出 `key → uid` 映射并在 JOURNAL 记录单元总数。

### 3.4 邻接判定

沿用主线 `tools/yeidai_ops.py` 的 `LINK_MIN_M = 50`：
两单元共享边界长度 ≥ 50 m 才算邻接。**不得擅自改这个常数**（改则 `split`
行为与主线不一致）。

---

## 4. ★ 筛选规则 DSL（核心资产）

### 4.1 定位

- **LLM 只输出这棵树，绝不输出任何坐标。** 几何一律由确定性执行器计算。
  （对齐主线 D12：规则优先、LLM 兜底）
- 树是**可序列化 JSON**，可存档、可 diff、可人工审阅修改。
- 求值结果是**单元 id 集合**（`set[int]`），不是多边形。

### 4.2 原语（P3-MVP：前 4 个；P3b：后 2 个）

#### P3-MVP（零外部依赖，只用官方街道/区县数据）

```jsonc
// 1. 某街道内的单元
{"op": "in_street", "name": "南石头街道"}

// 2. 某区县内的单元
{"op": "in_district", "name": "海珠区"}

// 3. 并集（★ 多块领地由此天然产生）
{"op": "union", "args": [ <node>, <node>, ... ]}

// 4. 差集
{"op": "minus", "args": [ <node>, <node> ]}   // args[0] - args[1]
```

#### P3b（条件触发，需引入带路名的线要素）

```jsonc
// 5. 某线要素某一侧的单元（scope 限定搜索范围，省略则为全试点区）
{"op": "side_of", "line": "华南快速", "dir": "east",
 "scope": <node|null>}
// dir ∈ {"east","west","south","north"}

// 6. 中心点周边（兜底）
{"op": "near", "center": [lon, lat], "radius_km": 3.0}
```

### 4.3 求值语义（执行器必须严格遵守）

| 原语 | 判定规则 |
|---|---|
| `in_street` | 单元**质心**落在该街道多边形内 → 入选。（不用面积重叠，避免边界单元双属） |
| `in_district` | 单元 `district_code` 等于该区编码 → 入选。（用属性，不做几何判定） |
| `union` | 各子节点结果集的并 |
| `minus` | `eval(args[0]) - eval(args[1])` |
| `side_of` | 单元质心相对该线**最近点的局部切线**的有向侧（不是整线走向）；`scope` 先缩小候选 |
| `near` | 单元质心到 `center` 的球面距离 ≤ `radius_km` |

**名称解析**：街道/区县名支持「精确 → 去后缀（街道/镇/区）→ 包含匹配」三级容错。
匹配到 0 个或 >1 个 → **抛错，不得静默取第一个**。
（主线 `lookup_geometry` 的两字前缀兜底是已知隐患，试点禁止复刻。）

### 4.4 输出契约

```jsonc
{
  "unit_ids": [12, 13, 40, 41, 77],
  "components": 2,              // 邻接图连通分量数（D-9：只报告，不干预）
  "area_km2": 31.7,
  "rule": { /* 原样回填求值用的 DSL 树，供追溯 */ },
  "warnings": ["街道『XX』匹配到 0 个单元"]
}
```

---

## 5. 验收门禁

> **D-1 铁律**：G3 与 G4 分两张表，永不合并。

| 门禁 | 阶段 | 判定 | 通过线 |
|---|---|---|---|
| **G0** | P0 | 业务方确认 CONTRACTS.md | 人工签字 |
| **G1** | P1 | 试点数据抽取正确 | 单测全绿 **且** 坐标系判定有数字证据（不是"应该是"） |
| **G2-a** | P2 | 单元库自洽 | 两两重叠面积 < 总面积 0.1%；无孤立单元（除真实飞地，需列名） |
| **G2-b** | P2 | 表达能力（业代） | oracle 单元集覆盖率**中位 ≥ 0.95** |
| **G2-c** | P2 | 表达能力（经销商） | **无预设阈值**，测基线。< 0.90 → 触发 P2b |
| **G3** | P3 | 几何天花板 | 给定人工写好的 oracle DSL 树，执行器复现单元集**必须 100% 精确**，含退化用例 |
| **G4** | P4 | 端到端 `[合成语料]` | 报中位单元集 Jaccard + `components` 准确率。**无预设通过线，如实报告** |

### 5.1 G3 必含的退化用例（缺一不可）

1. 空结果（街道名不存在 → 抛错，不返回空集）
2. 单单元结果
3. `minus` 结果为空集
4. `union` 含重复子树（幂等）
5. 多分量结果（`components ≥ 2`）
6. 名称匹配歧义（匹配 >1 → 抛错）
7. 嵌套 3 层以上的树

### 5.2 报告格式（P4 产出，两张表）

```markdown
### 表 A：G3 几何天花板（oracle 规则 → 单元集）
| 围栏 | oracle 规则 | 复现 | components |
...
判定：必须全部 100%

### 表 B：G4 端到端 [合成语料]
⚠️ 本表使用的四至文本系从真值围栏反向提取（见 AGENTS.md），
   评测存在循环性，不代表在真实客户合同上的表现。
| 围栏 | 文本 | Jaccard | components 实际/预期 |
...
```

---

## 6. 代码约定

- Python 3.11+；几何用 `shapely`，图用 `networkx`（与主线 `yeidai_ops.py` 一致）
- 试点代码全部在 `sraf-pilot/src/`，**不修改 `tools/`、`intelligence/`、
  `dealer_territory/` 任何既有文件**
- 每个模块配 `sraf-pilot/tests/test_<模块>.py`，用 `unittest`（与主线一致，不引 pytest）
- 路径：`pathlib.Path`，基准点为「本文件所在目录向上找到仓库根」或 CLI 参数（D-4）
- 注释与 docstring 用中文（本目录约定）；变量名英文
- 错误信息面向业务用户的用中文

### 运行命令

```bash
cd <repo-root>
python3 -m unittest discover sraf-pilot/tests -q
python3 sraf-pilot/src/01_extract.py --src <SRC_DIR> --out data/pilot
```

---

## 7. 阶段与依赖

```
P0  L0    建分支 + 本文件 + JOURNAL                         → G0
P1  omp   01_extract.py  数据抽取 + 坐标系验证 + 脏点处理     → G1
P2  omp   02_units.py    单元库 + 街道标签 + 邻接图 + oracle → G2-a/b/c
P2b 条件  若 G2-c < 0.90，引入 OSM 细面补充                  → 重测 G2-c
P3  omp   03_dsl.py      四原语 + 执行器 + 连通分量           → G3（必须 100%）
P3b 条件  05 side_of / near                                  → G3
P4  omp+L0 04_nl2rule.py NL → DSL 树                         → G4 [合成语料]
```

---

## 8. 变更记录

| 版本 | 日期 | 变更 | 批准 |
|---|---|---|---|
| v1.0 | 2026-08-30 | 初版 | 待 G0 |
