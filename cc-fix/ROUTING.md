# 分派路由 v1.0

## 角色分层

| 层 | 承担者 | 职责 | 禁止 |
|---|---|---|---|
| 规格所有者 | 用户(cai) | 裁决规格歧义、改 CONTRACTS.md | — |
| 架构层 | Claude | 写任务卡、定门禁、**独立验收** | 不得替所有者裁决规格 |
| 施工层 | codex | 按封闭任务卡实现 | **不得自行裁决歧义** |
| 子代理 | codex 派发 | 同施工层 | 同受全部约束 |

## 模型策略（已实测验证）

```bash
# 主执行：luna + max effort
codex exec -m gpt-5.6-luna -c model_reasoning_effort=max \
  -C /Users/cai/Desktop/达能-SRP-AI/sraf \
  --add-dir /Users/cai/Desktop/达能-SRP-AI/客户数据 \
  "$(cat cc-fix/tasks/T-XXX.md)" \
  < /dev/null > /tmp/codex-T-XXX.log 2>&1

# 遇阻降级：sol + high effort（同一任务卡重试一次）
codex exec -m gpt-5.6-sol -c model_reasoning_effort=high \
  ... 同上 ...
```

**实测确认**：
- `luna` 是模型名，`max` 是 effort，必须分开传。启动横幅会打印 `reasoning effort: max` 可核对。
- 模型名校验严格：无效名返回 400 而非静默回退，故成功启动即证明模型生效。
- codex 具备子代理工具：`collaboration.spawn_agent` / `followup_task` / `send_message`
  / `interrupt_agent` / `list_agents` / `wait_agent`。**允许派发**。

## 硬性纪律（违反会导致静默失败）

1. **`< /dev/null` 必加**。`codex exec` 无 TTY 时会阻塞在
   `Reading additional input from stdin...`，且该失败**是间歇性的**——
   stdin 恰好已关闭时会侥幸跑通，不要等它复现。
2. **同一时刻只跑一个 codex 实例**。并行会放大错误且挂死后无法定位是哪一路。
3. **日志全部重定向留档**，路径 `/tmp/codex-T-XXX.log`，完成后归档到 `cc-fix/verify/`。
4. **验收由 Claude 独立跑**，不采信 codex 自报。

## 挂死判定（%CPU 不可信）

agent 等 API 响应时 %CPU 接近 0，与挂死无法区分。改看三个量：

```bash
PID=$(ps -eo pid,lstart,etime,command | grep "codex exec" | grep -v grep | awk '{print $1}' | head -1)
lsof -p $PID -i -n -P 2>/dev/null | grep -c ESTABLISHED   # 工作中 15~30，挂死 0
ps -M -p $PID | sed -n '2p'                                # 累计 CPU 应单调增长
ls -la <产出文件>; sleep 60; ls -la <产出文件>              # mtime/size 应变化
```

⚠️ `pgrep | head -1` 常匹配到 wrapper shell 而非真正 agent 进程，
用 `ps -eo pid,lstart,etime,command | grep codex` 按启动时间确认目标 PID。

⚠️ agent 循环耗时以**十分钟计**，判断挂死前先给足时间，不要过早 kill。

## 交接四件套（靠文件不靠对话）

| 文件 | 作用 | 可写者 |
|---|---|---|
| `cc-fix/CONTRACTS.md` | 规格（冻结事实/门禁/协议） | **仅所有者** |
| `cc-fix/tasks/T-*.md` | 封闭任务卡 | Claude |
| `cc-fix/state.json` | 阶段状态机 | Claude + codex |
| `cc-fix/JOURNAL.md` | 日志与升级条目（含被推翻归因） | 全体 |

## Git 约定

- 分支 `CC_main`，基点 `b82e46e`
- 每 Phase 一提交，前缀 `fix:` / `refactor:` / `test:` / `feat:`
- 正文中文，写清「改了什么、为什么、怎么验证的」
- **推送 origin/CC_main 已获所有者授权**

## 推送方法（本机特有，两层阻碍，缺一不可）

本机推送 GitHub 会连撞两个**互相独立**的问题，只解决一个仍然失败：

| 层 | 症状 | 根因 | 解法 |
|---|---|---|---|
| 网络 | `SSL_ERROR_SYSCALL` | Clash fake-ip 把 github.com 解析为 `198.18.0.90` 假地址，且该域走 DIRECT 规则 | 本地 CONNECT 转发代理 |
| 凭据 | `403 denied to YY-C8` | `/Library/Developer/CommandLineTools/.../gitconfig` 配了 `osxkeychain`，抢先提供旧账号凭据 | `-c credential.helper=` 先清空链 |

**诊断要点**：错误信息能区分卡在哪层——`SSL_ERROR_SYSCALL` 是网络层没连上，
`403` 说明已连上、卡在认证。带 token 后若仍报 403，是 helper 被 keychain 抢了。

```bash
# ① 起本地绕过代理（不改 Clash、不需 sudo；TLS/SNI 仍端到端，不降级安全）
python3 <scratchpad>/fakeip_bypass.py > /tmp/bypass.log 2>&1 &

# ② 推送：http.proxy 指向它 + 清空 helper 链后注入 token
git -c http.proxy=http://127.0.0.1:18443 \
    -c credential.helper= \
    -c credential.helper='!f() { echo username=x-access-token; \
        echo "password=$(cat /Users/cai/Desktop/ghkey.txt | tr -d "\r\n ")"; }; f' \
    push -u origin CC_main
```

**安全纪律**：token 只经 credential helper 的 stdout 传给 git——
不进命令行参数（`ps` 不可见）、不写入任何 git config、不落盘。
输出一律过 `sed -E 's/(ghp_|github_pat_)[A-Za-z0-9_]+/[REDACTED]/g'`。
- 不碰 `main`，不合并，不动 `feat/cc-unit-selection-pilot`
