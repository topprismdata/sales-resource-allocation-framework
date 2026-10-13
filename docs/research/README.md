# docs/research · 研究文档层（analysis/ 白名单入库）

WP13a（2026-10-13）：本地 `analysis/` 17 份研究文档经 PII 筛查后**白名单入库 13 份**。
筛查标准：不含**未公开的客户/经销商身份信息**（门店户名、电话、合同原文）。
「亨啡源」等项目名已存在于本仓公开代码与文档（tools/、docs/territory/），不构成新增暴露；
公开连锁品牌（美宜佳/华润万家等）为行业常识，不属 PII。

## 入库清单（13）

| 文件 | 主题 |
|---|---|
| CHATGPT_DEEP_RESEARCH_four_bounds.md | 四至语义 GPT 深研（含 Fréchet 匹配文献线） |
| CHATGPT_RESEARCH_four_bounds.md | 四至研究第一轮 |
| research_brief_four_bounds.md | 四至研究任务书 |
| FOUR_BOUNDS_LADDER_2026-08-29.md | 四至解释阶梯（F1→F4 能力分层） |
| CN_MARKET_distributor_territory_reality.md | 中国经销商片区现实调研 |
| CN_THEORY_territory_allocation_understanding_v2.md | 片区分配方法论理解 v2 |
| DESIGN_04_allocation_intelligence.md | 04 分配智能设计稿 |
| DP06_GAP_ANALYSIS_v2_full.md | DP06 缺口分析全量版 |
| DP06_GAP_ANALYSIS_visit-scheduling-optimizer.md | DP06 与拜访排程器的交叉缺口 |
| INDUSTRY_GAP_contract_to_fence.md | 行业缺口：合同文本→围栏 |
| RELAY_CAPABILITY_MATRIX.md | 接力能力矩阵 |
| THREE_ROUND_REVIEW.md | 三轮评审记录 |
| WORLD_MODEL_dealer_management.md | 经销商管理世界模型笔记 |

## 排除清单（4，含经销商户名「浩盛」等未公开身份信息）

- CONTRACT_PACK_guangzhou.md（合同语料包）
- FENCE_FOUR_BOUNDS.md · FENCE_NATURAL_DESCRIPTIONS.md · FENCE_TOWNSHIP_DESCRIPTIONS.md（围栏描述语料，含户名）

排除件保留在本地 `analysis/`（gitignore 区），如未来脱敏改写可再走白名单评审。

## 纪律

- 本目录文档为**研究/设计过程记录**，规范性内容以 `docs/sraf/`（v1.2 正典）为准；
- 新增入库需过一次 PII 筛查（grep 户名/电话/证件号模式 + 人工复核），在此表登记。
