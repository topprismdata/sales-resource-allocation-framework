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

