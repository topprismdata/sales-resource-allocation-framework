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

