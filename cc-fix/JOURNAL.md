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


## 2026-08-31 推送阻塞解除（原归因不完整，已修正）

**旧归因（已于 2026-08-31 被推翻/修正）**：
> "403 = 账号 YY-C8 对 topprismdata 无写权限，需加权限或 fork。"

**实际是两层独立问题叠加**，只解一层仍失败，故先前误判为单纯的权限问题：

1. **网络层**：Clash fake-ip 将 `github.com` 解析为 `198.18.0.90`（假地址），
   且该域在 Clash 规则中走 DIRECT → `SSL_ERROR_SYSCALL`。
   实证：真实 IP `20.205.243.166` 直连返回 200；经 Clash 代理反而失败；
   同代理访问 google 正常 → 排除代理本身故障。
2. **凭据层**：`/Library/Developer/CommandLineTools/usr/share/git-core/gitconfig`
   配置了 `osxkeychain` helper，抢先提供旧账号 `YY-C8` 凭据，
   导致注入的 token **根本没被使用** → `403`。

**解法**：① 本地 CONNECT 转发代理（固定映射 github.com→真实 IP，
不做 DNS 解析；TLS 与 SNI 仍由 git 端到端完成，安全性不降级）；
② `-c credential.helper=` 先清空 helper 链，再注入 token helper。

**结果**：`origin/CC_main` = 5c0e65f 推送成功。方法已固化至 ROUTING.md。

**诊断价值**：错误信息可区分层次——`SSL_ERROR_SYSCALL` 为网络层未连通，
`403` 表示已连通但认证失败。带 token 仍 403 即为 helper 被 keychain 抢占。

## 2026-08-31 T-002 路径去硬编码（Phase 1）执行完成

### 实施

- 新建 `tools/_paths.py`，实现显式参数 → `SRAF_DATA_DIR` → 仓库根
  `data/gz` 的三级解析；`ROOT` 由 `__file__` 推导，`SOURCE` 指向
  `data/gz/source`。
- 按卡片规则完成 26 个命中文件的路径替换：ROOT/DATA 使用 `_paths`，
  两个 GeoJSON 使用 `_paths.SOURCE`，经销商 CSV 和同目录的 `广州.xlsx`
  使用仓库根同级 `客户数据`，两个 SVG 输出使用数据包目录。
- `yeidai_compile.py` 与 `demo_server.py` 原本没有 `/Users/ghb` 命中，保持未改。

### 独立验收

B1–B6 全部 PASS，具体命令输出已写入 `cc-fix/verify/T-002-verify.txt`。
B4 为 `23 passed in 0.05s`；B5 已越过两个 source GeoJSON 并推进到缺失的
`data/gz/gz_osm_full.json`；B6 的启动异常已指向本地
`data/gz/basic_units_wgs.json`，不再指向原作者目录。另行执行的 28 文件
`py_compile` 与 `git diff --check` 也通过。

### 失败与归因修正

- 中间一次批 B 大补丁因 `unit_allocator.py` 的实际 import 上下文与补丁假设
  不一致而失败；补丁未落盘，随后按实际上下文拆分修正，最终无遗留失败。
- B5/B6 底层的 `FileNotFoundError` 是卡片明确允许的缺失派生数据现象，包装后的
  B5/B6 断言均通过；没有联网拉取、没有伪造 `gz_osm_full.json` 或单元库。
- 被推翻/修正的旧归因是“import 失败仍说明必须依赖 ghb 的 Downloads 或原作者
  数据目录”。B5 证明两个根源 GeoJSON 已从仓库 `data/gz/source` 读通；剩余
  错误仅是本地缺少派生 `gz_osm_full.json`，不再是用户目录硬编码问题。
- 另发现 `component_matcher.py` 的 `/tools` 子路径变体，已按同一 ROOT 规则
  改为 `_paths.ROOT / "tools"`；没有无法由卡片规则覆盖的第五种残留模式。

本次未修改 `cc-fix/CONTRACTS.md`，未联网，未生成或删除数据文件，未执行 Git commit。

## 2026-08-31 同步 main RC2.0 (42cf065) + ★ 发现 RC2.0 自带测试回归

### merge 情况

预检零文件重叠（RC2.0 改 `intelligence/adjust.py`/`knowledge_items.json`/
`demo_server.py`；CC_main 改 tools/ 其余 26 文件），merge 干净无冲突。

merge 后重跑 T-002 断言：B1/B2/B3/B5/B6 **全部仍 PASS**，
证明 CC_main 的路径修复未被 RC2.0 影响。

### ★ 新审查发现：RC2.0 破坏了 5 个既有测试（非 CC_main 引入）

**归属验证**：用独立 worktree 检出**纯 42cf065**（不含任何 CC_main 改动）跑测试：

```
5 failed, 18 passed     ← 与 merge 后完全一致
FAILED test_multicomponent.py::test_proposal_multi_ring
FAILED test_multicomponent.py::test_select_area_spans_components
FAILED test_multicomponent.py::test_transfer_multi_component_preserves_clusters
FAILED test_multicomponent.py::test_transfer_single_component
FAILED test_multicomponent.py::test_transfer_zero_store_removal
```

**结论：回归由 RC2.0 自身引入，与 CC_main 的 merge 无关。**
基点 b82e46e 时为 23 passed，RC2.0 后降为 18 passed。

**根因**（`intelligence/adjust.py:95-105`）：

```python
def _rows() -> list:
    if _DATA_DIR is None:
        raise AdjustError("adjust 未初始化数据目录（set_data_dir）")
    path = _DATA_DIR / "territory_compiled.json"
    if not path.exists():
        raise AdjustError("缺少 territory_compiled.json（先跑 territory_compile.py）")
```

RC2.0 将领地调整**硬绑定到离线编译产物 `territory_compiled.json`**。
5 个测试以纯内存 World 构造、不含数据目录，遂全部抛 AdjustError。

**问题性质（与 RC1.0 同构且更进一步）**：

| 版本 | 对编译产物的依赖 | 失败表现 |
|---|---|---|
| RC1.0 | 回放优先用编译产物，失败**静默降级**到台账(IoU 0.0-0.14) | 伪装成功 |
| RC2.0 | 调整**硬依赖**编译产物，缺失即抛错 | 功能完全不可用 |

且 `territory_compiled.json` 的生成链依赖 `gz_osm_full.json`（需联网 Overpass），
门槛进一步抬高。**讽刺之处**：RC2.0 声称改进多组件领地
（修 `_pieces_union` 截断），却使多组件领地的全部 5 个测试失效。

**处置**：不在当前 Phase 修复（非 CC_main 引入，且属 RC2.0 设计取舍）。
已留档，建议纳入后续 Phase 或单独反馈原作者。
**Phase 3 消除静默降级时需按 RC2.0 新架构重新设计。**

## 2026-08-31 T-003 启动可诊断（Phase 2）执行记录

### 实施

- 删除 `demo_server.py` 的 `/tmp` 数据目录回退；显式 `--data-dir` 优先，
  其次读取 `SRAF_DATA_DIR`，最后使用仓库内 `data/gz`。目录不存在或
  `region.json` 缺失时输出已检查路径、缺失文件、
  `python3 tools/build_region_pack.py`、`--data-dir` 和 `SRAF_DATA_DIR`，
  并以非零状态退出。
- `STATE` 中的 `YeidaiState`、`Ledger` 和 `yeidai_snapshot` 改为惰性槽位；
  通过业代/台账 API 首次访问时按当前数据包加载。缺少基础单元依赖时由
  路由返回 HTTP 503 JSON，列出 `missing_files` 和生成/指定目录指引，
  不再抛裸异常。热切换同时清空这两个可选状态，避免跨区域复用。
- 为 `YeidaiState` 和 `Ledger` 增加可选 `data_dir` 参数；无参数调用仍保持
  `_paths.DATA` 的原有默认路径。业代切割线读取也跟随实例数据目录。
- 验收命令包含 `/api/status`，但基线没有该路由；增加只读状态端点，
  不触碰任何单元库。围栏颜色/邻居是展示派生计算，不是第三个重对象；
  实测其启动期计算约 10 秒，延后到首次 `/api/bootstrap`，使首页可先启动。

### 验收结果

- C1/C1b：PASS。缺目录退出码为 1，无 `/tmp/region.json`，无 Traceback，
  错误含完整操作指引。
- C3：PASS（导入状态槽位为 `None`；`/api/status` 协议探针 HTTP 200）。
- C4：PASS（`/api/ledger_cmd` 协议探针 HTTP 503，合法 JSON，含
  `unit_attributes.json`、`basic_units_wgs.json` 和 `build_region_pack`；
  业代调整同样返回结构化 503）。
- C5：`18 passed, 5 failed`，失败数与已登记的 RC2.0 基线一致，未新增失败。
- 详细实际输出：`cc-fix/verify/T-003-verify.txt`。

### 失败、归因与修正

- 第一次 C2 后台启动尝试被当前受限 shell 报 `nice(5) failed: operation not
  permitted`，没有进入服务进程；改以前台会话复核后确认应用成功加载
  `data/gz` 并走到 HTTP bind。
- 当前执行沙箱禁止本地 TCP `bind`，前台 C2 最终为
  `PermissionError: [Errno 1] Operation not permitted`。该失败归因于执行环境，
  不是数据包或启动逻辑；因此无法在本环境完成真实 curl C2，已在验收文件中保留。
  延后展示派生计算后，应用层初始化约 1.6 秒，已排除原有启动耗时会超过
  验收 `sleep 6` 的风险。
- 中间一次内存 HTTP 探针因把中文直接写入 bytes 字面量而产生 Python 语法错误；
  非产品失败，改为 UTF-8 编码后 C3/C4 协议探针通过。随后一次 5 秒探针超时
  经计时确认是旧的邻接着色计算约 12 秒，已通过按需计算修正，非数据缺失。
- `ref_check.py` 报 `expected 9 specs, found 0`，`consistency_check.py` 报
  `13/73 passed`；均为当前 checkout 的既有文档路径/布局不匹配，不由 T-003
  引入。后者生成的未跟踪 `docs/CONSISTENCY_CHECK_REPORT.md` 已清理。

本次未修改 `cc-fix/CONTRACTS.md`，未联网，未伪造或重建
`basic_units_wgs.json`/`unit_attributes.json`，未删除业务数据，未执行 Git commit。

## 2026-08-31 T-003 验收通过（Phase 2 完成）

**架构层独立执行断言**：

```
C1  PASS 缺数据目录报错可读且含操作指引
C1b PASS 退出码非 0 (1)
C2  PASS 服务启动且首页可访问（HTTP 200）      ← 关键里程碑
C3  /api/status HTTP 200（basic_units_wgs.json 确实不存在的前提下）
C4  PASS ledger_cmd 返回 HTTP 503 结构化错误而非栈
C5  5 failed / 18 passed，未引入新失败（5 个为 RC2.0 自带，T-004 处理）
```

**断言外验证（实际调用 API）**：

| 端点 | 结果 |
|---|---|
| `/` | 200, 39,511B |
| `/api/status` | 200 |
| `/api/regions` | 200 |
| `/fences` | 200, 14,407B |
| **`/api/fences`** | **200, 4,013,665B（dealers/admin/subdistricts）← 围栏数据链路通** |
| `/api/pack_status` | 200 |
| `/api/bootstrap` | **HTTP 000** → 登记 E-003 待查 |

**错误信息质量对比**：

修复前：
```
FileNotFoundError: [Errno 2] No such file or directory: '/tmp/region.json'
```

修复后（启动）：
```
数据包目录不可用：/nonexistent_dir_xyz
已检查路径：/nonexistent_dir_xyz
缺少文件：region.json
请先运行 python3 tools/build_region_pack.py 生成或补齐业务数据包；
如需指定其它目录，请使用 --data-dir <目录> 或设置 SRAF_DATA_DIR。
```

修复后（API，HTTP 503 结构化）：
```json
{"error":"台账功能暂不可用：数据目录 data/gz 缺少 unit_attributes.json、basic_units_wgs.json。…",
 "feature":"台账","missing_files":["unit_attributes.json","basic_units_wgs.json"],
 "data_dir":"data/gz","hint":"python3 tools/build_region_pack.py；--data-dir <目录>；SRAF_DATA_DIR"}
```

**实现合规性**：引入具名异常 `DataPackError`/`OptionalDataError`，
`_get_ledger()`/`_get_yeidai()` 惰性构造并缓存，handler 经
`_require_ledger()`/`_require_yeidai()` 转 503。**无一处裸吞异常**，
成功路径未改变（实测 6 个端点均正常）。

### 联网拉取 OSM 记录（E-001 已获授权执行）

- 首次单次查询 bbox=22.5,112.9,23.95,114.1 → **HTTP 504**
- 实测围栏地理范围：**21.87–25.52°N / 111.93–114.75°E（整个广东）**，
  90 条中仅 35 条属广州；其余分布珠海/佛山/中山/韶关（最北始兴 24.8°N）
- 改 4×4 分块拉取 → 57,162 element，6 块失败（429/502）→ 子块补拉中
- ★ 既有缺陷：`tools/fetch_region_osm.py` 对大 bbox 必然 504，
  README「三步切换新城市」在该规模下不可行 → 登记 E-004

## 2026-08-31 T-004 修复 RC2.0 测试回归（验收通过）

### 实施

- `intelligence/adjust.py` 在有 `territory_compiled.json` 时继续走原有
  TerritoryIR rows 与 `territory_compile.U` piece 路径；无编译产物但有
  `World` 时，为每个 `Fence` 以 `area_id` 生成稳定伪片，并直接使用 fence
  几何完成整体/半区调整。
- 降级模式的 `Proposal.impact["area"]["granularity"]` 明确为 `fence`，
  正常编译模式明确为 `piece`；缺少编译产物时不写回不存在的编译文件。
- 未修改 `tests/`、`cc-fix/CONTRACTS.md`，未伪造编译产物，未执行 Git commit。

### 验收

- D1：`23 passed` 全绿。
- D2：`tests/` 未被修改。
- D3：降级标记为 `fence`。
- D4：有编译产物时正常读取，未被回退抢占。
- 详细实际输出：`cc-fix/verify/T-004-verify.txt`。

## 2026-08-31 T-004 验收通过（RC2.0 测试回归已修复）

**架构层独立执行断言**：

```
D1 PASS 23 passed 全绿        ← 恢复 b82e46e 基线，RC2.0 回归已消除
D2 PASS tests/ 未被修改        ← 靠改实现达成，未动既有契约
D3 PASS 降级被显式标记为 fence 粒度
D4 PASS 有编译产物时正常读取，未被回退抢占
```

**实现评价（71+/20-，仅动 intelligence/adjust.py）**：

设计上乘之处在于**所有新增参数均为可选**，默认 `None` 时行为与 RC2.0 逐字节一致，
这正是 D4 得以通过的原因：

| 新增 | 作用 |
|---|---|
| `_compiled_rows_available()` | 判断编译产物可用性；**特意保留「已加载缓存即便文件后被删仍算正常源」**的既有惰性语义 |
| `_fence_piece_id(fence)` | 以 `area_id` 作稳定片 id（非数组索引，更稳健） |
| `_fence_rows(world)` | 构造与 TerritoryIR 同形状的伪行 |
| `_rows_for_world(world)` | 优先编译产物，否则 fence 粒度 |
| `_piece_geom(k, world)` / `_pieces_union(pieces, world)` | 加可选 world 参数，默认行为不变 |

**★ 超出要求的正确判断**：施工层在降级模式下对**无法正确支持的选择器主动报错**，
而非给出错误答案：

```python
if _fence_granularity(world):
    raise AdjustError("缺少 territory_compiled.json 时，fence 粒度仅支持整个区域或东南西北半区")
```

且 `_piece_impact` 的 `street` 字段在降级模式返回 `None`，不假装拥有街道信息。
这与 CONTRACTS §2「禁止静默降级」完全一致——**宁可明确拒绝，不可静默给错**。

**架构层修正一处**：新增 4 处 docstring 为英文，按全局规范（注释一律中文）已汉化；
汉化后重跑 23 passed 不变。

### 能力矩阵（修复后）

| 场景 | 调整能力 | 标记 |
|---|---|---|
| 有 territory_compiled.json | piece 粒度，全部选择器 | `granularity: "piece"` |
| 无编译产物、有 World | fence 粒度，仅「整个区域/东南西北半区」，其余明确报错 | `granularity: "fence"` |
| 两者皆无 | 抛 AdjustError（原样） | — |

修复前 RC2.0 的行为是：**无编译产物即完全不可用**。

## 2026-08-31 T-005 消除静默降级（实现完成，HTTP 门禁受环境阻塞）

### 实施

- `/api/generate` 的 TerritoryIR S 片回放成功路径新增 `confidence: "high"`，其余响应字段保持不变。
- 回放异常后进入台账重演时改为 `interpretation: "territory-ir-degraded"`、`confidence: "low"`，并透传 `异常类型: 异常文本` 作为 `degraded_reason`。
- 描述词台账路径返回 `ledger/low`；两处草稿路径返回 `draft`，按现有 `draft_quality` 映射 `ok→medium`、`low/未知→low`。
- 降级日志包含本地时间、`area_id` 和原始异常；前端仅对声明为非 `high` 的 `/api/generate` 结果使用橙红告警围栏，并显示降级提示和 `degraded_reason`。
- 未修改 `cc-fix/CONTRACTS.md`、`intelligence/adjust.py`、`tests/` 或 `data/gz`，未执行 Git commit。

### 验收

- 内存请求覆盖四条路径：回放成功、回放异常后台账降级、描述词台账、草稿，全部通过；真实缺失 `gz_osm_full.json` 异常以 `FileNotFoundError` 出现在响应和日志中。
- E3 静态断言通过；前端脚本语法通过。
- E4：`23 passed`。
- `cc-fix/verify/T-005-verify.txt` 保存了完整输出及阻塞说明。

### 门禁阻塞

- 卡片原始 TCP HTTP E1 未能在当前环境执行：沙箱禁止 `127.0.0.1:8794` 监听；本地浏览器访问也被权限策略拒绝，未绕过限制。
- 当前 `data/gz` 还缺少台账所需 `unit_attributes.json`、`basic_units_wgs.json`；未伪造或补写数据以强行通过该 HTTP fixture。

## 2026-08-31 T-005 验收通过（Phase 3 完成：静默降级已消除）

### ★ 架构层自身缺陷留档（第 3 次）：验收场景不可达 + 断言假阳性

**被推翻的设计假设**：
> "回放失败即会落入台账重演路径，故可据此验证降级标记。"

**实证推翻**：台账路径**自身也需要** `unit_attributes.json` / `basic_units_wgs.json`，
当前尚未重建，于是 `_require_ledger()` 抛 `OptionalDataError` → 直接返回 **HTTP 503**，
根本走不到降级响应。

**叠加的断言缺陷**：E1 写作 `assert itp != 'territory-ir'`，而 503 错误对象里
`interpretation` 为 `None`，`None != 'territory-ir'` 恒真 → **假阳性**，
险些把"完全失败"误判为"降级标记正确"。

**修正**：断言补 `assert itp is not None`（识别 503 错误对象），
并在临时数据包中同时 mock 最小台账（2 个单元 + 街道名与 engine_terms 对齐），
使降级路径真正可达。已回写 T-005 卡，保证可复现。

**教训**：验证"降级"必须保证**降级目标本身可用**，否则测到的是另一种失败。

### 实现验收（实现本身完全正确，无需返工）

四条路径均已正确标注：

| 路径 | interpretation | confidence | 其它 |
|---|---|---|---|
| S 片回放成功 | `territory-ir` | `high` | — |
| 台账降级 | `territory-ir-degraded` | `low` | `degraded_reason` = 真实异常 |
| 描述词兜底 | `ledger` | `low` | — |
| 草稿 | `draft` | `_draft_confidence(quality)` → medium/low | — |

`replay_error = f"{type(e).__name__}: {e}"` 捕获真实异常；日志补时间戳与 area_id；
并额外处理了「hit 存在但无 S 片」的边界（给出专门的 degraded_reason）。

**运行时实证**（补齐 mock 台账后）：
```
interpretation:  territory-ir-degraded      ← 不再伪装
confidence:      low
degraded_reason: FileNotFoundError: ... gz_osm_full.json    ← 真实原因
units: 2  area_km2: 2.28                    ← 仍返回可用结果，只是诚实标记
```

### 前端验证（浏览器实测，非仅代码审查）

注入真实降级响应后实测：

| 检查项 | 结果 |
|---|---|
| 告警可见性 | `display: block` |
| 边框 / 背景 | `rgb(230,81,0)` / `rgb(255,243,224)` 醒目橙 |
| 文案 | 「⚠ 降级结果：这是降级结果，精度可能显著偏低。」+ 经销商 + 置信度 + 降级原因 |
| 降级围栏样式 | `#b71c1c` weight 5, dash 4 4, fillOpacity .25 |
| 正常围栏样式 | `#e53935` weight 4, dash 8 5, fillOpacity .10 |
| **正常态是否误告警** | **否**（`isDegradedGenerate({confidence:"high"}) === false`） |

页面截图确认：顶部告警框正常渲染，且左上角显示 **「90 围栏 / 0 门店」**——
即 P0 重建的数据包被完整加载。**端到端链路贯通**。

## 2026-08-31 T-006 验收通过（生成 gz_osm_full.json，解除编译阻塞）

### 实现

- 新增 `tools/build_osm_full.py`，支持 `--data-dir`，默认沿用 `_paths.data_dir()`。
- 从 `osm_raw.json` 按原始顺序逐条生成 roads/rivers WKT；way 顶点不足 2 个或缺少 name 时跳过，其他符合条件的 way 不去重、不丢弃。
- `roads/rivers` 仅将 Overpass 的 `lat/lon` 改写为 WKT 的 `lon lat`，保持 WGS-84；`adm6` 直接由区县 GeoJSON 生成 WKT，保持 GCJ-02，并保留 Polygon 内环及 MultiPolygon 组件。
- 对未覆盖的 `highway` 类别显式失败；本次原始数据的 highway 类别全部在既有 `CLASS_RANK` 覆盖范围内。
- 采用临时文件替换，重复运行输出稳定；未修改 `territory_compile.py`、`cc-fix/CONTRACTS.md` 或任何原始输入，未执行 Git commit。

### 验收

- F1：`roads=70459`、`rivers=2377`、`adm6=11`，字段完整且集合非空。
- F2：与 `osm_raw.json` 动态计算的期望条数完全一致，无数据丢失。
- F3：11 个区县齐备，包含天河区、海珠区、白云区，WKT 全部可解析。
- F4：天河区输出与源 GeoJSON 质心偏移 `0.0000m`，未发生坐标转换。
- F5：`territory_compile` 完整 import 通过，`U=6261`、地物 `72818` 条/`9577` 名、`adm6=11`。
- 幂等性：连续两次生成的 SHA-256 均为
  `b79d80c598889d6510cb1a1a4a80333be529c42c0ba61fc1f7559e1ef3544b2b`。
- 完整断言输出保存于 `cc-fix/verify/T-006-verify.txt`。

### 附加门禁

- `python3 -m unittest discover tests -q`：23 tests，全部通过。
- `tools/ref_check.py`：当前仓库基线报 `expected 9 specs, found 0`。
- `tools/consistency_check.py`：当前仓库基线为 `13/73 passed`，缺少既有 00–08/spec 文档；该检查产生的无关报告已移除。
- 上述两个附加门禁失败与本卡新增数据生成器无关，未据此修改规格或放宽 T-006 的 F1–F5 断言。

## 2026-08-31 T-006 验收通过（编译链路解除阻塞）

**架构层独立执行断言**：

```
F1 PASS roads=70459 rivers=2377 adm6=11
F2 PASS 无数据丢失（逐条与 osm_raw 核对）
F3 PASS adm6 11 区县齐备
F4 PASS adm6 与源 geojson 零偏移（0.0000m），未被误转换   ← 坐标系陷阱已规避
F5 PASS territory_compile 完整 import 成功（6s）
```

F5 输出：
```
数据: 地块2675 街道面174 地物72818条/9577名
统一铺盖U: 6261片   adm6: 11
```

### ★ 坐标系混用的处理（本卡最高风险项）

`gz_osm_full.json` **内部混用两种坐标系，这是代码逻辑的硬要求**：

| 字段 | 坐标系 | 依据 |
|---|---|---|
| roads / rivers | WGS-84 | `territory_compile.py:116` 先将 U(GCJ) 转 WGS 再与地物比对 |
| adm6 | GCJ-02 | `adm6bt` 在 compile_fence 中与 zg/pu/sbt(全GCJ)直接做几何运算 |

两者恰好都无需转换（OSM 原生 WGS，本地区县 geojson 原生 GCJ）。
F4 专门断言 adm6 与源文件**零偏移**，一旦有人"顺手统一坐标系"立即拦截——
该误操作会引入约 623m 系统偏移，且症状隐蔽（编译照常跑完，仅地物贴附全错）。


## 2026-08-31 ★ 关键实证：J=1.0 可复现，但确系自证；IoU 才是真实指标

用 CC_main 自建数据包独立运行 `territory_compile.py 亨啡源`：

```
数据: 地块2675 街道面174 地物72818条/9577名
统一铺盖U: 6261片
[47] 广州亨啡源商贸有限公司  人话5句 引擎37词 J=1.00 over=0 miss=0 IoU=0.997 覆盖=99.93%
[48] 广州亨啡源商贸有限公司  人话9句 引擎29词 J=1.00 over=0 miss=0 IoU=0.988 覆盖=99.35%
```

### 三点结论

1. **J=1.0 真实可复现**，非造假——用完全独立重建的数据包得到同样结果。
2. **但它是自证的**：`over=0 miss=0` 的完美命中本身即信号。
   `synth(zg, T)` 以 T 为输入生成表达式 → 反解得 S → 再比较 S 与 T。
   循环闭合，恒为 1.0，**不度量"文本还原围栏"的能力**。
3. **IoU 是有意义的真实指标**：0.997 ≠ 1.0，差值源自单元边界与手绘围栏
   边界的真实几何偏差，度量的是「单元集合逼近围栏几何」的**天花板**。

**较原审查结论更精确的修正**（原判断把 J 与 IoU 一并归为自证）：

| 指标 | 性质 | 可否对外报 |
|---|---|---|
| `engine_J` | 自证（答案造词再比答案） | ❌ 不得表述为还原能力 |
| `iou` / `cover` | 真实几何天花板 | ✅ 可报，但须注明「天花板，非端到端」 |

→ 直接支撑 Phase 5 的双表设计：表 A 天花板（IoU/cover）、表 B 端到端（需真实语料）。

**附**：47/48 两条独立编译，印证 T-001 的 MultiPolygon 拆分裁决正确。

### ★ 新发现：编译性能不可接受（空间索引建而不用）

全量编译 `timeout 1800` **超时未完成**（退出码 124），单围栏亦超 120s。

根因（`tools/territory_compile.py`）：

```python
Ut = STRtree([x[0] for x in U])          # :109 建好索引……全文仅此一处，从未使用

def compile_fence(fence):
    T = {k for k in range(len(U))         # ← 全量遍历 6261 片
         if U[k][0].intersection(zg).area/max(U[k][0].area,1e-12) >= 0.5
         or U[k][0].intersection(zg).area/fa >= 0.3}   # ← 同一片重复求交两次
    psel = {i for i in pt.query(zg) ...}  # ← 紧邻一行却正确用了 pt 索引
```

同一函数内 parents 用索引、U 不用。量级：6261 片 × 2 次求交 × 90 组件 ≈ **113 万次几何运算**。

**优化方向（结果等价，纯性能）**：改用 `Ut.query(zg)` 预筛
（STRtree 返回 bbox 相交的超集，再做精确判断，集合结果不变），
并缓存单次 `intersection` 结果。预计候选由 6261 降至数十。

**衍生洞察**：RC1.0「固化编译结果回放、不做实时重解析」的设计，
原判断主因是精度（IoU 0.0-0.14 vs 0.95-1.0）；现补充——
**实时编译在当前实现下根本跑不动**，性能亦是主因。
但根子是编译未优化，而非实时解析路线不可行。

→ 登记 E-005，另立任务处理。

## 2026-08-31 T-007 实现与验收记录

### 实现

- 新增 `tools/build_unit_library.py`，通过 `_paths.data_dir()` 解析
  `--data-dir`，从 `territory_compile.U` 按原顺序生成两个台账前提文件。
- 每个 U 单元的 GCJ-02 Polygon 仅在导出边界用 `tc.gcj2wgs` 转为 WGS-84
  WKT；属性严格取 `U[k]`、`pdistrict[parent]` 与 `sorted(feats_of(k))`。
- 输出统一为官方权威 schema `{"units": [...]}`，同目录临时文件替换，
  重复运行字节稳定；导出过程打印 6261 片进度。
- `intelligence/adjust.py:_street_district_map()` 兼容字典包裹格式，同时
  保留顶层数组格式；未修改 `allocation_ledger.py`、`CONTRACTS.md` 或 `tests/`。
- 全量 `feats_of`/导出运行约 9 秒，未接近 30 分钟上报阈值。

### 验收

- G1：6261 个单元，两个文件顶层与字段/id 序正确。
- G2：GCJ→WGS 平均质心偏移 658m。
- G3：district 6261/6261，street 6261/6261，roads 5223/6261，覆盖率通过。
- G4：Ledger 构造成功，街道索引 453 项、区索引 11 项。
- G5：`adjust` 兼容 `{"units":[...]}`，街道→区映射 173 条。
- G6：真实 TCP 监听在当前执行沙箱被操作系统拒绝（`PermissionError: [Errno 1] Operation not permitted`），
  因此 `curl` 得到 HTTP 000，不能将该环境门禁伪报为 TCP PASS；同一实际
  `Handler` 经 socketpair HTTP 请求返回 200，台账加载 `测试商 +21` 单元且无
  `missing_files`。
- G7：`23 passed in 0.03s`。
- 幂等性：两次运行的 basic/attributes SHA-256 分别均为
  `6e25db93bb30819cb8f14db25740ecafd4624476282644732a742a283a2390c6` /
  `9c5d495824c205e5567dc416d60a426613ea9ba307b4fef289a004cda9f21c67`。

完整输出见 `cc-fix/verify/T-007-verify.txt`。当前未执行 Git commit。

## 2026-08-31 T-007 验收通过（单元库重建 + adjust schema 修复）

**架构层独立执行断言**（施工层受沙箱限制未能起真实 TCP 服务，G6 由架构层真跑补验）：

```
G1 PASS 单元数 6261，字段与 id 序均正确
G2 PASS 已正确转为 WGS-84（相对 GCJ 平均偏移 658m，落在 300~900 合理区间）
G3 PASS district 6261/6261  street 6261/6261  roads 5223/6261
G4 PASS Ledger 构造成功（街道索引 453 项，区索引 11 项）
G5 PASS adjust 兼容 {"units":[...]}，映射 173 条
G6 PASS 台账 API 真实可用（架构层实起服务）：
        ledger_cmd HTTP 200
        {"message":"测试商 名下 21 单元","summary":[{"owner":"测试商","units":21,"area_km2":4.1}]}
G7 PASS 23 passed
```

`intelligence/adjust.py` 的 schema 兼容修复正确（+2 行 isinstance 检查），
未触碰 `allocation_ledger.py`。`build_unit_library.py` 无硬编码路径。

### ★ Phase 4 的实测证据（单字截断危害，供 T-009 使用）

单元库就绪后，首次可对 `allocation_ledger.py` 的模糊匹配做真实测量：

```
由 core[:-1] 截断产生的【单字 key 共 96 个】
  例: ['新','仙','小','正','云','石','派','增','永','荔','九','夏', …]

"大" → 247 个单元        "南" → 245 个单元        "新" → 461 个单元
resolve_units() 全部【静默返回，无歧义报错】
```

对照 pilot 分支纪律：同类场景（"大"命中 471 条）**直接抛错**。
两条线在此处的工程纪律差距，现已有同口径实测数据支撑。

## 2026-08-31 T-008 实现与验收记录

### 实现

- 在 `tools/territory_compile.py` 保留独立的 `_select_T_bruteforce(zg, fa)`
  暴力参考路径，并新增 `_select_T(zg, fa)`：使用既有 `Ut.query(zg)` 做
  外接矩形预筛，每个候选片只计算一次 `intersection(zg).area`。
- `compile_fence` 已切换调用 `_select_T`；T 之外的 S/J/IoU、人话和引擎词
  逻辑未改。
- H3 阶段计时发现，主优化后剩余耗时来自每条围栏重复构造
  `ops.unary_union([sbt, adm6bt]).buffer(BAND_BUF)`，而不是 `_select_T`。
  因此增加惰性缓存 `_boundary_band()`，复用同一几何结果，不改变界带表达式。

### 验收

- H1/H2：12 条围栏 T 集合逐例完全相等；暴力 1.2s → 优化 0.10s，实测
  加速约 **11x**，H2 达标。
- H3 编译时间：退出码 0，`territory_compiled.json` 生成，耗时
  **2:03.61**，远低于 30 分钟；产物 70 行，其中 35 行有 S 片。
- H3 行数门禁：**未通过/需规格裁决**。当前 `region.json` 共 90 条围栏，
  其中 20 条 dealer 含“佛山”；`territory_compile.py` 既有正式范围过滤
  “佛山”，所以输出严格为 70 行。卡片要求 `len(rows) >= 80`，与当前数据
  和过滤范围冲突；未自行改变过滤或补造行。此项上报所有者。
- H4：`23 passed in 0.04s`。
- 项目级 `ref_check.py` 为 `expected 9 specs, found 0`，
  `consistency_check.py` 为 `13/73 passed`；两者均因当前规范位于
  `docs/sraf/`、检查器固定查找 `docs/` 的既有布局问题失败，与 T-008 代码
  无关。验证脚本生成的临时 `docs/CONSISTENCY_CHECK_REPORT.md` 已删除。

完整断言输出见 `cc-fix/verify/T-008-verify.txt`。当前未执行 Git commit。

### 诊断运行留档

主优化后的首次 H3 观测显示，耗时已从 T 选择路径转移到重复边界缓冲带
构造；该观测任务未作为验收结果采信。尝试结束其旧进程时被当前执行环境以
`Operation not permitted` 拒绝，故它可能继续运行至自身 timeout；新验收任务
已独立完成，旧任务只写 `/tmp/h3.log`，不改变源代码或验收记录。

## 2026-08-31 T-008 验收通过（编译性能优化）+ ★ 重大口径发现

**架构层独立执行断言**：

```
H1 PASS 12 条围栏 T 集合逐例完全相等（暴力实现 vs 优化实现）
H2 PASS 暴力 1.2s → 优化 0.10s，加速 12x
H3 PASS 全量编译完成，产出 territory_compiled.json（70 行）
H4 PASS 23 passed
```

### ★ 架构层自身缺陷留档（第 4 次）：H3 行数断言写错

**被推翻的假设**：`assert len(rows) >= 80`。
**实际正确值为 70** —— 90 个组件减去 `territory_compile.py` 主动过滤的
20 个佛山组件（`fences = [f for f in reg["fences"] if "佛山" not in f["dealer"]]`）。
断言已修正为 `== 70`。

### ★★ 重大口径发现：一半围栏无法编译，而对外数字把它们排除了

全量编译 70 行，**仅 35 行有 S 片**：

| | 有 S 片（35 条，均属广州） | 无 S 片（35 条） |
|---|---|---|
| `engine_J` | 中位 **1.0000**，**35/35 全为 1.0**，最小值亦为 1.0 | 0 |
| `iou` | 中位 0.9960，**最小 0.7550**，最大 1.0000 | 0 |
| `cover` | 中位 99.84% | 0 |
| 归属地 | 广州 | 珠海13 / 中山7 / 韶关3 / 始兴1 / 其他11 |

**结论一：自证指标无分布，真实指标有分布。**
同一批数据上 `iou` 从 0.7550 到 1.0000 呈真实分布，而 `engine_J`
**35 条精确全等于 1.0，无一例外**。真实的还原任务不可能对所有样本完美命中。
这是 J 系循环论证的最硬证据（补强 2026-08-31 亨啡源单例实证）。

**结论二：分母被静默缩小。**
单元库 U 源自广州路网 geojson，**只覆盖广州**，故非广州围栏
（珠海/中山/韶关/始兴）全部无法编译。而 RC1.0/RC2.0 对外报
"31 dealers, median IoU 0.99"——仅统计可编译的那一半，
**未说明另外 50% 完全失效**。

→ Phase 5 双表必须同时披露：
  - 表 A 天花板：仅广州 35 条，报 IoU/cover 分布（真实指标）
  - 表 B 端到端：需真实语料
  - **两表均须标注覆盖率 35/70，不得以 35 为分母掩盖失效样本**

