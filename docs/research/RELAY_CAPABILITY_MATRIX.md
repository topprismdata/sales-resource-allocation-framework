# Browser Relay 能力矩阵（SRAF 项目应用场景）

## 已验证
| 能力 | 用法 | 状态 |
|---|---|---|
| ChatGPT 普通 Chat | tab.type → Enter → 提取回复 | ✅ 已跑通 |
| ChatGPT Deep Research | 提交简报 → 等 5-30min → 提取报告 | 🔄 进行中 |
| 对比菜单页面渲染 | CDP 打开 /compare → 截图验证 | ✅ 已跑通 |

## 近期可做（不需要额外开发）
| 能力 | 场景 |
|---|---|
| 文件分析 | 把 region.json / contracts.json 上传给 ChatGPT 分析数据质量 |
| 围栏画图 | 让 ChatGPT Canvas 画围栏叠加图，替代手写 Leaflet |
| 交叉审稿 | 设计文档发给 ChatGPT 独立评审（如 D14 评审） |
| 代码 Review | git diff 发给 ChatGPT 独立 review |
| 论文检索 | ChatGPT web search 替代 web_search 工具 |

## 中期可做（需要少量开发）
| 能力 | 场景 |
|---|---|
| ChatGPT Project | 创建 "SRAF Research" 项目，保存上下文和文件 |
| Model Council | ChatGPT / Claude / Gemini 并行回答同一问题，交叉验证 |
| 自动化测试 | 用 ChatGPT 分析 /compare 页截图，自动判断渲染质量 |
| 数据标注 | 业代片 → 经销商归属校正，ChatGPT 辅助判断 |

## 安全边界
- Browser Relay = 操作你自己的登录态 Chrome
- 不适合高频/无人值守/生产 API
- ChatGPT DOM 结构经常变，代码需要维护
- 不用全局 `browser.relay=true`，只在需要时指定 `app.relay: true`
