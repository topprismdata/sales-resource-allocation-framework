# CC_main 修复日志

> 纪律：失败、挂死、走错的归因全部留档。归因被推翻时**保留旧归因并标注**，避免重走错路。

---

## 2026-08-31 P0 启动

### 审查结论（来自 b82e46e 代码审查，判据=稳定实现最终效果）

| 级别 | 问题 | 证据 |
|---|---|---|
| P0 | 26 文件硬编码 `/Users/ghb` 绝对路径 | `territory_compile.py:6,14,20,31,282` 等 |
| P0 | `data/gz` 缺失时回退 `/tmp`，启动崩溃且报错误导 | `demo_server.py:111-116` → `FileNotFoundError: /tmp/region.json` |
| P0 | 单元库源头在 ghb `~/Downloads`，未纳入数据契约 | `territory_compile.py:20,31` |
| P1 | **静默降级伪装成功**：回放失败→台账重演(IoU 0.0-0.14)，仍返回 `interpretation:"territory-ir"` | `demo_server.py:668-691` |
| P1 | 街道名索引 `core[:-1]` 截出单字 key + `k in term` 模糊匹配 → 静默吞并大量单元 | `allocation_ledger.py:36-39,55-74` |
| P1 | 方位判定用质心二分，凹形/L形区域错判 | `allocation_ledger.py:98-105` |
| P2 | **J=1.0 循环论证**：`synth(zg,T)` 用 T 造词，再拿反解 S 与 T 比 | `territory_compile.py:187-206,255-306` |
| P2 | 44 提交 4480 行**零测试**，`tests/` 未被触碰 | `git log b879583..HEAD -- tests/` 为空 |
| P3 | `territory_compiler.py` 死代码，与在用文件仅差一字母 | 无任何 import |
| P3 | README Demo 章节不提主服务 `demo_server.py` | `README.md:84-93` |

### 归因修正记录 ★

**旧归因（已于 2026-08-31 被推翻）**：
> "根数据缺失，必须向 ghb 索要 `data/gz`；Phase 5 可能长期阻塞。"

**推翻证据**：`客户数据/` 目录下已存在全部根数据——
路网 geojson（properties 含 `街道[内置]`/`区[内置]`，与 `territory_compile.py:24-25`
读取字段完全一致，文件名亦一致）、街道/区县 geojson、3 份围栏 CSV。

**真因**：ghb 把根数据放在个人 `~/Downloads` 而未纳入仓库数据契约，
造成"无法复现"的假象。这本身就是 P0 问题的根源，而非额外障碍。

**影响**：`data/gz` 可本地完整重建 → 修复完成后可立即端到端验证，不阻塞。

### 语料现状澄清（不得美化）

- main 的 four_bounds 系**从真实围栏反推**（`bench_rebuild.py:4` 原注释）
- pilot G4 21 条**同为反推**，已自标 `[合成语料]`
- ghb 早期 bench 有 blind/oracle 分档且标注 `cheating`（`bench_oracle_ladder.py:8-11`），
  但 TerritoryIR/RC1.0 阶段**该区分消失**，只剩单一 J=1.0 对外
- 结论：**双方均无真实客户合同文本**。把分表纪律捡回来即可，非新增要求。

---

## 2026-08-31 推送阻塞（待所有者处理）

`git push -u origin CC_main` 失败：

```
remote: Permission to topprismdata/sales-resource-allocation-framework.git denied to YY-C8.
fatal: ... The requested URL returned error: 403
```

当前 git 凭据账号 `YY-C8` 对 `topprismdata` 仓库**无写权限**。
分支已在本地提交（97b81cc），推送待所有者解决权限后重试。
**不阻塞后续 Phase 施工。**

可选处置（需所有者决定）：
- (a) 请仓库管理员给 `YY-C8` 加 write 权限
- (b) fork 到个人账号后推 fork
- (c) 换用有权限的凭据

---

## 2026-08-31 T-001 升级：业代 CSV schema 与经销商 CSV 不一致（阻塞）

按 T-001 的强制门禁停止施工，未生成或覆盖 `data/gz`，未修改
`cc-fix/CONTRACTS.md`。使用 `encoding='utf-8-sig'`、`csv.field_size_limit(sys.maxsize)`
只读探查三份 CSV，结果如下：

| 文件 | 字段数 | 数据行数 |
|---|---:|---:|
| `广州办事处经销商围栏数据-20260827.csv` | 10 | 71 |
| `广州清单内业代的围栏数据-20260824.csv` | 13 | 33 |
| `广州及华南MT办事处业代图层围栏数据-20260824.csv` | 13 | 60 |

经销商 CSV 表头为：
`片区id, area_code, 业代组织编码, 围栏名称, layer, 中心点经度, 中心点纬度, 围栏面积, area_level, fence`

两份业代 CSV 彼此一致，但相对经销商 CSV 多出三个字段：
`layer_name, org_code, 办事处名称`。共同字段及 `fence` 均存在，不能据此自行假定
应忽略新增字段或按共同字段适配。

根据 T-001“若两份业代 CSV 的 schema 与经销商 CSV 不同，停止并上报差异，不要自行适配”
的要求，等待业务/架构所有者明确业代 CSV 的转换规则后再继续。Excel 探查及数据包生成
尚未执行；当前没有验收文件可上报。

## 2026-08-31 T-001 升级裁决（架构层）

### 施工层上报（合规，已独立复核属实）

codex 按门禁停止，未生成数据包、未伪造数据、仅追加 JOURNAL。独立复核确认：

| 文件 | 字段 | 数据行 |
|---|---:|---:|
| 经销商围栏 | 10 | 71 |
| 清单内业代 | 13 | 33 |
| 华南 MT 业代 | 13 | 60 |

业代 CSV 相对经销商多出：`layer_name`、`org_code`、`办事处名称`。

### 架构层裁决

**判定：属实现细节，不属业务规格，架构层可裁决，不上升所有者。**

理由：多出的 3 个字段为附加元数据，不影响几何（`fence`）与归属（`围栏名称`）；
共同字段齐全，转换无歧义。

**处置**：共同字段按经销商 CSV 同规则映射；多出字段**原样保留到 `extra` 子对象**。
此为无损处置——不丢信息，且原始 CSV 始终在位，随时可再提取。
（若 `办事处名称` 日后被证明有业务语义，可从 extra 直接取用，无需重跑。）

### ★ 架构层自身缺陷留档（阻塞粒度过粗）

**被推翻的设计假设**：
> "T-001 的任一上报条件触发即停止整卡施工。"

**问题**：`yeidai_fences.json` 是次要附带产物，其 schema 歧义却阻塞了主线
`region.json` —— 而主线数据（经销商 CSV）**完全无歧义，本可独立完成**。
结果是一次本可产出 80% 成果的施工，产出为 0。

**修正**：上报条件改为**分级阻塞**——
- 阻塞主线的歧义 → 停止整卡
- 仅影响次要产物的歧义 → **主线照常完成**，次要产物单独标记待裁决

**另修正卡内笔误**：原写"71 行（含表头）→ 70 条数据"有误。
实测 `csv.DictReader` 读出 **71 条数据行**（文件 72 行含表头）。
A2 断言本身用动态比较，未受影响，但注释须更正以免误导。

## 2026-08-31 T-001 主线升级：A4 与无损 rings 语义矛盾（阻塞）

按架构层修订后的分级阻塞规则继续施工前，先对主线 `region.json` 的 A4
做了只读可行性检查；未创建或覆盖 `data/gz`，未修改原始数据和
`cc-fix/CONTRACTS.md`。

经销商 CSV 使用 `utf-8-sig` 和 `csv.field_size_limit(sys.maxsize)` 读取，实测
71 条数据行、60 个 `Polygon`、11 个 `MultiPolygon`，共存在 60 个内环。
卡片要求 `rings[0]` 为 WKT 外环，而 A4 使用
`Polygon(f["rings"][0]).area`，没有把 `rings[1:]` 作为内环传给 Shapely。

第一个确定失败样本：

| area_id | WKT | 外环重建面积 | 原 WKT 面积 | 相对误差 |
|---|---|---:|---:|---:|
| `694419549` | `POLYGON`，3 个内环 | `0.0015634269981749426` | `0.0015634269599349422` | `2.4459089768117584e-08` |

相对误差大于 A4 的 `1e-9`，所以任何保持外环原始坐标、并按标准语义保留内环
（例如 `rings=[外环, 内环...]`）的无损转换都会被当前 A4 判定失败。直接删除
内环会丢失几何语义；修改外环以迎合面积会伪造源数据，均不合规。此为主线
`region.json` 验收规格本身的阻塞，不是实现阈值或坐标转换问题。

同次 `officecli view` 只读探查两份 Excel：`广州.xlsx` 有经度/纬度、客户名、
渠道、区县和上游名称，但没有可直接对应的 `direct`、`dealers`、`kind`；
进离店报表有打卡经纬度和客户名，但同样没有完整的上游/围栏归属/直供字段。
因此若主线规格修订后继续施工，`stores` 应保持空数组并单独报告，不应猜测映射。

待裁决：请修订 A4 为按 rings 的完整拓扑计算面积（至少传入内环；对
MultiPolygon 明确组件语义），或明确允许有损地忽略内环/调整外环。收到主线
规格修订前停止 T-001；本次未生成 `T-001-verify.txt`，因为六条门禁尚未进入
可执行验收阶段。

## 2026-08-31 T-001 第二次升级裁决：几何拓扑（架构层缺陷）

### 施工层上报（合规且正确，已独立复核）

codex 指出 A4 断言 `Polygon(f["rings"][0]).area` 与「无损转换」自相矛盾：
含内环的围栏，外环面积必然大于真实面积，任何无损映射都会被 A4 判失败。
样本 `694419549` 相对误差 2.4459e-08 > 阈值 1e-9。

**独立复核结论：上报完全成立。这是架构层的规格缺陷，不是施工层的实现问题。**

### 实测拓扑

| 指标 | 值 |
|---|---:|
| CSV 数据行 | 71 |
| 单体 Polygon / MultiPolygon | 60 / 11 |
| **拆分后组件总数** | **90** |
| 含洞围栏 / 内环总数 | 9 / 60 |
| 丢弃内环导致的总面积虚增 | 0.003186% |
| 最大单条虚增（694419783 珠海龙进） | 0.2201% |

### ★ 架构层自身缺陷留档（第 2 次）

**被推翻的设计假设**：
> "围栏几何均为简单多边形，`rings[0]` 即可无损表达。"

**实证推翻**：11 条为 MultiPolygon（最多 7 组件），9 条含内环（共 60 个洞）。

**根本原因**：编写 region.json schema 时未核对真实数据的几何拓扑，
直接沿用了"单外环"假设，导致 A4 断言与无损要求在逻辑上不可同时满足。

### 架构层裁决（属实现细节，与 main 既有范式一致，不上升所有者）

**1. MultiPolygon → 拆为多条 fence 记录**

依据：`intelligence/world.py:19-24` 的 `Fence` 为 frozen dataclass，
只含单个 `ring` 字段，**结构上无法表达多组件**；多组件由
`fences_by_dealer`（同 dealer 多条记录）表达。此即 main 既有的
「area_id rekeying / 亨啡源 split」范式——实测 `广州亨啡源商贸有限公司`
确为 2 组件，与 main 记录的「亨啡源=2块」完全吻合。

规则：`area_id = f"{原片区id}#{序号}"`，序号自 1 起，按组件面积降序。
单组件围栏**不加后缀**，保持原 area_id。

**2. 内环（洞）→ 存入 `holes` 字段，不丢弃**

`Fence` 结构存不下内环，但 region.json 可以保留。
规则：`rings=[外环]` 供 World 消费；`holes=[[内环],...]` 保留原始洞几何。
**信息零丢失**；World 暂按外环渲染，影响仅限显示（总面积虚增 0.0032%，已量化）。

**3. `area_km2` → 按组件面积占比分配 CSV 原值**

`area_km2 = CSV围栏面积 × (该组件面积 / 该围栏全部组件面积之和)`

理由：避免引入度²→km² 换算常数。**实测仓库内该常数不一致**——
`territory_compile.py:15` 用 `KM2=12364.0`，而 `demo_server.py:713` 用
`area*11320*1.0084`(≈11415)，两者差 8.3%。本阶段不触碰该分歧，
改用占比分配使总和严格守恒于 CSV 原值。

> **待办（后续 Phase）**：KM2 常数不一致需单独处置，已记录。

## 2026-08-31 T-001 执行记录：数据包构建与验收

### 已执行

- 新增 `tools/build_region_pack.py`，支持 `--src` / `--out`，默认值为
  `../客户数据` / `data/gz`；未写入任何用户目录硬编码。
- 使用 `utf-8-sig` 和 `csv.field_size_limit(sys.maxsize)` 读取三份围栏 CSV；
  未做坐标转换，`meta.crs` 写为 `GCJ-02`。
- 经销商 CSV 中包含始兴等非广州市区县的源围栏；按卡片默认策略全量无损入库，
  未擅自过滤。
- 经销商围栏 71 行拆为 90 个组件；MultiPolygon 按组件面积降序拆分，
  内环保存在 `holes`，`area_km2` 按组件面积占比分配并守恒。
- 两份业代 CSV 共 93 行拆为 186 个组件；多出的
  `layer_name`、`org_code`、`办事处名称` 原样保存在每条记录的 `extra`。
- 生成 `region.json`、`meta.json`、`contracts.json`、`yeidai_fences.json`，
  并将三个 GeoJSON 原样复制到 `data/gz/source/`。
- Excel 只用 `officecli` 探查。两份表均缺少能无歧义映射到
  `direct`、`dealers`、`kind` 的字段，故 `region.json.stores` 保持空数组，
  未猜测或伪造门店语义。

### 验收证据

`cc-fix/verify/T-001-verify.txt` 已记录实际输出。A1、A2、A3、A4、A4b、A5、A6
全部 `exit_code: 0`：90 个组件、71 个 `src_area_id` 及组件数匹配、90 个组件
几何（含内环）逐条一致、71 条面积总和守恒、World 加载 90 个围栏、三个
GeoJSON 字节一致。重复执行后预期输出文件 SHA-256 未变化。

### 启动 smoke test 与归因

实际执行 `python3 tools/demo_server.py --data-dir data/gz 8765` 仍以
`exit_code: 1` 退出。围栏包已成功加载；失败发生在顶层初始化
`tools/yeidai_ops.py:20` 的 `YeidaiState`，其既有常量路径指向
`/Users/ghb/sales-resource-allocation-framework/data/gz/basic_units_wgs.json`，
而该业代单元库不属于本卡输入或允许生成的产物。归因是后续路径/业代依赖问题，
不是 `region.json` 几何或 A1-A6 验收失败；本次没有伪造该文件，也没有越界修改
`tools/yeidai_ops.py`。

本次执行没有修改 `cc-fix/CONTRACTS.md`，没有 Git commit。

## 2026-08-31 T-001 验收通过（架构层独立复核）

**独立执行全部断言**（未采信施工层自报）：

```
A1 PASS 三文件齐备
A2 PASS 组件总数 90
A3 PASS 71 条 src_area_id 及各自组件数全对
A4 PASS 90 个组件几何逐条一致（含内环）
A4b PASS 71 条面积总和守恒
A5 PASS World 加载 90 个围栏 / 68 个经销商
A6 PASS 三个 geojson 字节一致
```

**断言之外的独立检查**（防自写断言盲区）：

| 检查项 | 结果 |
|---|---|
| `meta.json` crs 声明 | `GCJ-02` ✓ 符合契约 §1.1 |
| `contracts.json` | `[]` ✓ 未伪造 four_bounds |
| `yeidai_fences.json` | 186 组件，`extra` 含 layer_name/org_code/办事处名称 ✓ 裁决被正确执行 |
| `build_region_pack.py` 硬编码 | 无 `/Users/` ✓ |
| 是否误用 pandas/openpyxl | 未使用 ✓ 符合本机 officecli 约定 |
| 幂等性 | 重跑 sha256 不变 ✓ |
| stores | 保持 `[]` 并上报，未猜测 Excel 映射 ✓ |

### ★ Phase 0 目标达成的判据

服务启动崩溃点**前移**，证明数据包问题已解决：

- 修复前：`demo_server.py:161` `_load_pack` → `FileNotFoundError: /tmp/region.json`
- 修复后：`demo_server.py:163` `YeidaiState()` → `FileNotFoundError: /Users/ghb/.../basic_units_wgs.json`

即 `region.json/meta.json/contracts.json` 已被成功加载，
新崩溃点是 Phase 1 待修的硬编码路径。

### 新发现的阻塞（转入 Phase 1/后续）

`basic_units_wgs.json` 与 `unit_attributes.json` 是**基础单元库**，
既不在 `客户数据/`，仓库内也无生成脚本（只被读、从不被写）。

**处置判断**：`territory_compile.py` 已实现「从路网 geojson 构建单元面 U」的逻辑，
且 `data/gz/source/` 现已备齐该 geojson，故单元库**可本地重建**，非阻塞。
但需先完成 Phase 1 去硬编码——否则 `build_hybrid_*.py` 等生成脚本自身跑不起来。

→ 顺序确认：**先 T-002 去硬编码，再用修好的脚本重建派生数据。**

