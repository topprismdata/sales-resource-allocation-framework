这三个新证据之后，我会调整上次评审的主结论：

P4b-2「联合划分 / global partition」现在是比“单经销商侧向场 + 最小代价环”更高一级的主假设。

但我不建议直接实现成“把所有道路、河流、行政界全部 planarize，然后求 faces”。正确方向应该是：
有限候选原子面/候选边图 + 全局标签分配 + 软边界证据 + 连通性约束。

更重要的是，下一步不要马上写 P4b solver。先做一个使用真值“作弊”的 Global Oracle Face Assignment，直接测量这个表示空间的理论上限。它是目前单一最高杠杆实验。

0. 三个新证据分别改变了什么
证据1：P1 oracle 弧实验——真正被证伪的是「local boundary → loop」范式

median Δ(P1−V1c) = -0.036 非常重要。

但我要稍微修正“弧选择不是瓶颈”这句话：

它严格证明的是：

在当前“弧 → 闭环 → bbox fallback”的生成机制下，单纯提高弧段定位精度没有正收益。

它还不能证明 arc selection 永远不重要，因为你的 oracle 剪弧同时改变了拓扑闭合条件。

胜意隆和穗穗盛尤其有判决力：

胜意隆：错误的长 barrier 反而产生正确闭环

穗穗盛：正确 landmark 本身穿过 territory，hard barrier 反而切坏 territory

两个案例共同说明：
landmark ≠ 必须被 territory boundary 完整采用的 barrier

所以 hard barrier 的语义已经被实证削弱。

而且 V1c 的 0.493 必须重新解释：

它不是纯粹的“边界语义重建能力 = 0.493”，而是 boundary evidence + accidental closure + bbox prior 的混合成绩。

建议以后所有结果额外报告：

IoU
final
	​

,IoU
no-bbox
	​

,IoU
bbox-only
	​

,FallbackRate

否则 bbox 很容易继续掩盖真正的问题。

证据2：行政区容器假设基本可以判死刑

25/37 跨区、10/11 区被多个经销商分摊，这个数据足够强。

因此：

R
i
	​


≈AdminPolygon
j
	​


而应改成：

∂Admin
j
	​

∈candidate boundary evidence

即：

行政区是“边素材”，而不是“面先验”。

这其实也解释了为什么原 P4 有时表现不错：不是“行政区就是 territory”，而是区界恰巧贡献了真实边界的一部分。

证据3：37 个区域近似 tiling，是目前最大的新信息

如果这个结论经拓扑审计成立，那么问题发生了本质变化。

原问题是：

Contract
i
	​

→R
i
	​


37 次独立求解。

新问题是：

{Contract
1
	​

,…,Contract
37
	​

}→P(M)={R
1
	​

,…,R
37
	​

}

其中：

R
i
	​

∩R
j
	​

≈∅,
i
⋃
	​

R
i
	​

≈M

这是一个 regionalization / territory partitioning 问题。

而 territory design 文献长期就是把较小 basic units 聚合成互斥、连续 territory；早期 Zoltners 等已经用 set partitioning 处理销售区域设计，后来的 commercial territory design 也大量采用 basic units + disjoint assignment + contiguity。
PubsOnline
+2
ScienceDirect
+2

这和你现在的数据结构高度一致。

A. P4b-2 联合划分是不是比独立“侧向场+环”更大的杠杆？
我的判断：是，而且很可能是目前最大的算法级杠杆。

我现在会把优先级调整为：

Global Partition > arc selection > gap repair > 更复杂的 fuzzy side function

原因不是“global optimization 更高级”，而是它利用了你以前完全没有使用的信息守恒关系。

A1. 一条共享边界不应该被估计两次

独立算法实际上是在做：

∂R
i
	​

^
	​

,
∂R
j
	​

^
	​


分别推断。

理论上如果 i,j 相邻，它们之间应存在：

B
ij
	​

=∂R
i
	​

∩∂R
j
	​


联合模型只需要决定一次：

B
^
ij
	​


这是很大的统计优势。

因为一个内部边界往往同时有：

A 合同：“东至 XX 路”

B 合同：“西至 XX 路”

行政界证据

道路/河流几何

A/B 中心点位置

其他邻居形成的拓扑关系

可以共同决定一条 edge。

换句话说：

四至单独看信息不足，但 37 份四至 + tiling constraint 可能把缺失信息补回来。

这是一个非常重要的变化。

A2. 它还能直接消除你现在最麻烦的“闭环问题”

local 模型要求每个 territory：

L
N
	​

+L
E
	​

+L
S
	​

+L
W
	​

→closed cycle

所以道路断一点、河道换名、弧剪短一点就 leak。

global face 模型根本不要求四条合同 landmark 自己构成闭环。

它只要求：

每个 atomic face 最终属于谁？

闭环由标签集合自然产生：

R
k
	​

=
f:x
f
	​

=k
⋃
	​

f

因此：

不需要 corner stitching；

不要求四条 landmark 相交；

不要求每条 landmark 成为完整 barrier；

行政边界、道路、河流可以只贡献局部 edge；

邻居的合同可以帮助补全未描述边。

这正好对症你 P1 的失败。

但 P4b-2 有 8 个必须防的失败模式
1. 最大风险：Face Explosion

如果你真的把：

广州所有道路

所有河流

level-6

level-8

所有合同线

全部求 arrangement：

一般平面曲线集合的交点/face 数最坏可达到近似：

O(n
2
)

而真实 OSM 还会产生：

双向车道两条线；

高架/地面路；

河岸双线；

轻微错位的行政边界；

断线；

sliver polygon。

最后不是几百个 face，而可能几十万甚至百万级碎面。

所以我反对：

全 OSM → planar subdivision → optimization

我支持：

Candidate Boundary Graph → controlled atomic units → assignment

只允许以下对象进入 candidate boundary set：

合同实际提到的 road/river；

level-6；

level-8；

被 gap repair 选中的 connector；

少量 topology-supporting major roads/rivers。

而不是所有道路。

2. 原子面太粗

这是比 face explosion 更致命的另一端。

假设一个街道实际上被 3 个经销商切分：

那么 street polygon 若不可分：

f⊂R
A
	​

∪R
B
	​

∪R
C
	​


无论 solver 多聪明，都无法恢复。

这就是为什么 P4b-3 必须先做 representation ceiling 测试。

3. tiling 可能没有你现在看起来那么严格

必须防：

飞地；

多 component 经销区域；

渠道型 territory 与地理 territory 重叠；

特殊客户 carve-out；

水域、机场、工业区无人负责；

合同生效日期不同；

手绘 polygon 自身有 overlap/gap。

因此 production model 最好不要写死：

k
∑
	​

x
fk
	​

=1

而是：

k
∑
	​

x
fk
	​

+x
f,∅
	​

=1

保留 UNASSIGNED / VOID label。

硬 tiling 只在验证后开启。

4. 合同间可能相互矛盾

例如：

A：

东至 X 路

B：

西至 Y 路

但 X、Y 相差 800m。

local 方法只是产生两个不同 polygon。

global 模型会第一次暴露：

Constraint
A
	​

∩Constraint
B
	​

=∅

这其实是优点，但要求 solver 支持：

hard constraint + soft evidence + slack

而不能“所有文字都必须满足”。

5. 连通性也不能默认 hard

你的真实 territory 可能：

岛屿；

飞地；

被大河分隔；

因行政历史产生不连通 component。

所以先统计 ground truth：

components(R
i
	​

)

若 37 个里全部 single-component，再启用 hard connectivity。

否则允许：

components(R
i
	​

)≤c
i
	​


甚至学习 component prior。

6. 中心点不宜变 hard seed

如果中心点来源是客户地址、办公点、手工 POI，它可能：

接近边界；

甚至在 territory 外；

坐标误差。

所以：

x
seed
i
	​

,i
	​

=1

最好在实验确认后再作为 hard constraint。

初期应是强 unary prior。

7. 相关证据会被重复计票

典型情况：

街道边界沿某条主路。

那么：

road evidence

admin-8 evidence

事实上是同一个物理边界。

如果简单加权：

w
road
	​

+w
admin
	​


就会人为翻倍。

必须有一个 evidence provenance / correlation layer：

同源或近重合 geometry dissolve 后只产生一个 candidate edge，但保留多个 evidence tags。

8. 时间错配会在 global 模型里被放大

一个旧合同配：

2026 OSM；

当前街道边界；

旧手绘 territory；

如果期间街道撤并或道路改名，联合模型可能让错误传播给多个经销商。

所以每条行政证据最好有：

valid_from,valid_to,source_date
A 的最终判定

所以我给 P4b-2：

高杠杆，应该升主线。

但不是：

「先生成很多 face，然后做一下 assignment」。

而是：

Global constrained graph labeling / regionalization

从 OR 角度，它已经非常接近经典 territory design：basic areas、disjoint assignment、contiguity、graph partitioning。饮料配送 territory 文献正是用 city blocks / basic units 组成互斥 territory。
ScienceDirect
+1

B. 中国 OSM level-8 vs 国家统计局 12 位代码，哪个更稳？

这里必须纠正一个关键认识：

这两个不是同一种数据，不能互相替代。

国家统计局 12 位代码不是边界 geometry

12 位统计用区划代码结构是：

2+2+2+3+3

即：

1–2：省

3–4：地

5–6：县

7–9：乡/镇/街道

10–12：村/社区

所以你要的 level-8 对应的实际上是前 9 位的乡级实体。
国家统计局

但代码告诉你的是：

“有哪些 entity、叫什么、属于谁”

不是：

“边界在哪里”。

而且从 2024 年 10 月开始，国家统计局已经不再公开最新具体代码

国家统计局 2025 年明确答复：

自 2024 年 10 月起，继续公开编制规则，但不再向社会公开具体统计用区划代码。
国家统计局

所以更不能把 NBS 当成长期互联网公开 geometry 数据源。

有意思的是：国家统计系统内部确实有 boundary geometry

2026 年农业普查培训资料明确提到：

系统预置了 2025 年全国 1% 人口抽样调查的边界数据，并存在“区域统计代码边界”模块。
tjj.ordos.gov.cn
+1

也就是说：

中国事实上存在：
Code↔Polygon

的官方统计边界库。

但它不是你可以稳定公开下载的全国公共 shapefile 服务。

所以我的数据源优先级改成
Tier A — 官方公开地方 geometry

优先寻找：

广东/广州天地图；

广州市/区自然资源部门；

民政/规划公开地图；

地方政府开放数据。

OSM China Wiki 本身也列出了部分地方天地图乡镇级数据，例如北京天地图可以精确到乡镇。
OpenStreetMap 维基

Tier B — OSM admin_level=8

OSM 对中国乡、镇、街道的标准映射确实是：

admin_level=8

OpenStreetMap 维基
+1

它最大的优势：

geometry 可下载；

topology 可处理；

与你的现有 pipeline 一致；

免费；

易自动化。

但必须把它视为：

candidate geometry，不是 ground truth。

OSM China 自己就提醒其统计数量不一定及时、准确；其边界项目也建议结合多方正式资料核验。
OpenStreetMap 维基
+1

甚至有 level-8 relation 的 source=estimated 实例。
spatial.demo.geocode.earth

Tier C — MCA/NBS 作为 Entity Authority

建议把：

民政部 → 法定行政实体、调整历史；

NBS → 统计区划 entity / code；

OSM → candidate polygon；

拆开。

特别是民政部门才是行政区划建制主管来源；国家统计局也明确指出统计用代码是用于统计工作的区域代码，与法定行政区划不是同一概念。
贵州省移动政务服务平台
+1

所以回答“哪个更稳”

如果问 entity identity：

MCA > NBS > OSM

如果问 互联网可直接获取的 level-8 geometry：

地方官方公开地图 > OSM >>> NBS code

因为 NBS code 本身没有 geometry。

对你的工程，我建议：
MCA / historical notices
       ↓
canonical street entity registry
       ↓
OSM level-8 geometry
       ↓
topology QA
       ↓
official map / road / river cross-validation
       ↓
candidate admin-8 boundary
C. “河是侧约束，不是切断”在 Face Assignment 里怎么表达最干净？

这是 P4b 最大的概念收益之一。

答案：

把“河流”从 hard topological barrier 降级成 unary side potential + optional pairwise boundary reward。

不要再写：

River⇒x
f
	​


=x
g
	​


而应该：

River⇒prefer certain labels on certain sides
1. Face graph

定义：

G=(F,E)

其中：

F：atomic faces

E：相邻 faces

标签：

x
f
	​

∈{1,…,K,∅}

表示 face 属于哪个经销商。

2. 四至形成 unary side field

比如合同：

北至珠江后航道

对 dealer k，生成：

μ
k,b
	​

(p)∈[0,1]

它表示位置 p 满足：

“位于珠江后航道的 territory-side”

的程度。

一个 face：

μ
k,b
	​

(f)=
∣f∣
1
	​

∫
f
	​

μ
k,b
	​

(p)dp

然后产生 unary cost：

U
k,b
	​

(f)=−log(ϵ+μ
k,b
	​

(f))

总 unary：

U
k
	​

(f)=
b∈B
k
	​

∑
	​

w
b
	​

U
k,b
	​

(f)

因此 river 即使穿过 territory：

另一侧 face 不是非法，只是 cost 增高。

这正好可以容纳你的“穗穗盛”。

3. 河作为 boundary evidence，只降低“在这里切开”的代价

对于相邻 face f,g：

P
fg
	​

=ρ
fg
	​

1[x
f
	​


=x
g
	​

]

普通地方：

ρ
fg
	​

=high

意思是：

不要无缘无故制造 territory boundary。

如果共同边界落在合同指定的河/路上：

ρ
fg
	​

=low

意思变成：

如果一定要在附近切，这里是更合理的位置。

注意：

ρ
fg
	​

>0

所以它不是必须切开。

这比 barrier 模型漂亮得多

hard barrier：

River⇒cut

P4b：

River⇒{
side preference
boundary likelihood
	​


两种信息完全分离。

我认为这应该成为新语义框架中的一个核心原则：

Reference object ≠ boundary object.

合同中的 landmark 产生的是：

BoundaryEvidence

而不直接产生：

BoundaryGeometry
一个完整的 P4b objective 可以写成
x
min
	​

text/side/center
f,k
∑
	​

U
k
	​

(f)x
fk
	​

	​

	​

+λ
b
	​

boundary preference
(f,g)∈E
∑
	​

ρ
fg
	​

1[x
f
	​


=x
g
	​

]
	​

	​

+λ
c
	​

P
connectivity
	​

+λ
s
	​

P
slack
	​


subject to：

k
∑
	​

x
fk
	​

=1

其中允许 VOID 后就是：

k∪{∅}
∑
	​

x
fk
	​

=1

这已经非常接近一个有业务语义的 Potts/graph-labeling regionalization model。

D. P4b-3 怎么做才真正有判决力？

这里我强烈反对只做：

“GT boundary 距离街道边界多少米？”

因为这个实验会产生一个严重的伪阳性。

原因：中国街道行政边界本身大量沿道路、河流划定

第五次全国经济普查的边界划定规则就明确要求：

普查区边界尽可能使用街巷、道路、河流、田埂等明显地物。
蚌埠市政府门户网站
+1

所以：

GT ──靠近── road
           ↑
street boundary 也沿 road

你会观察到：

GT ≈ street boundary

但这并不能证明：

经销商按“街道积木”划分。

可能只是两者都跟着同一条路。

真正有判决力的是“Atomic Unit Oracle Test”
H3
H
street
	​

:R
k
	​

≈
f∈StreetUnits
⋃
	​

f

也就是：

不切开任何街道 polygon，能不能重建真实 territory？

D1. 样本量

不要抽样。

你一共只有 37 个真实 territory：

37 个全部进入实验。

统计单位应当是：

n=37 territories

而不是几千个 boundary vertices。

否则会产生严重 pseudoreplication。

如果专门分析“老城区”，预注册 old-city inclusion rule，例如：

territory 至少 30% 面积落在旧城区范围。

但主表仍报告 37 个。

置信区间用：

territory-level clustered bootstrap

如果按区分层，再做 district-cluster sensitivity。

D2. 最关键指标：Atomic impurity

对一个 street face f：

a
fk
	​

=Area(f∩R
k
	​

)

如果它完全属于某 territory，则：

k
max
	​

a
fk
	​

≈Area(f)

定义全局不可恢复误差：

E
atom
	​

=
Area(M)
∑
f
	​

(Area(f)−max
k
	​

a
fk
	​

)
	​


这个指标非常重要。

它回答：

如果街道 polygon 不允许被切，至少有多少面积永远不可能分对？

如果：

E
atom
	​

=20%

那么 street-as-building-blocks 基本已经死了。

solver 无关。

D3. 最强指标：Street Oracle IoU

直接使用 ground truth “作弊”。

对于每个 street unit：

把它分给真实 overlap 最大的 dealer。

得到：

R
^
k
street−oracle
	​


然后算：

IoU
k
street
	​

=IoU(R
k
	​

,
R
^
k
street−oracle
	​

)

这就是：

street building-block representation ceiling

D4. 不要只测 street，要同时跑四套 representation

这是我认为最关键的设计：

Oracle	Atomic representation
O1	level-8 street polygons
O2	road-block faces
O3	合同提到的 road/river/admin arcs arrangement
O4	level-8 + contract landmark hybrid

然后比较：

IoU
O1
,IoU
O2
,IoU
O3
,IoU
O4

这会直接告诉你应该走哪条架构。

D5. Boundary overlap 仍然可以算，但只是辅助指标

对于 source S：

BR
S
	​

(τ)=
Length(∂R)
Length(∂R∩Buffer(∂S,τ))
	​


建议：

τ=50m, 100m, 300m

都报告。

更重要的是做exclusive attribution：

street only；

road only；

street ∩ road；

river；

district；

none。

特别要把：

street∩road

单独拿出来。

否则无法判定行政积木假设。

D6. 建议预先写死判决标准

不是文献标准，是你的 engineering gate。

我建议：

Street-only PASS

满足：

Median(IoU
street−oracle
	​

)≥0.85

并且：

Q
25
	​

≥0.75

同时：

E
atom
	​

≤5%

而 hybrid 的增益：

Median(IoU
hybrid
	​

−IoU
street
	​

)<0.03

那么：

可以大胆采用 street polygons 作为 basic units。

HYBRID

如果：

IoU
street
	​

=0.70∼0.85

但：

IoU
hybrid
	​

−IoU
street
	​

>0.05

说明：

街道是重要积木，但必须允许合同道路/河流进一步切 street。

这其实是我目前先验认为最可能出现的结果。

Street hypothesis REJECT

如果：

Median(IoU
street−oracle
	​

)<0.70

或者大量 territory：

IoU<0.60

那就不要继续投入“街道积木法”。

D7. 还有一个非常有价值的指标

直接统计：

GT boundary 穿过多少个 street polygon interior。

定义：

SplitRate=
Length(∂R)
Length(∂R∩Interior(StreetPolygons))
	​


如果经销商真的是 street-union：

SplitRate→0

这是比“边界距离”更具可证伪性的指标。

E. 下一步单一最高杠杆实验是什么？

不是继续 P1。

不是 gap repair。

甚至不是单独 P4b-3。

我建议直接做：
P4b-O：Global Oracle Atomic Partition Experiment

目标只有一句话：

在完全不考虑 NLP 和优化器能力的情况下，验证“global face assignment”这个表示空间最高究竟能做到多少 IoU。

实验只做四件事
Step 1 — 建四种 candidate atomization
A. level-8 only

B. contract-mentioned:
   road + river + admin-6 + admin-8

C. road-block

D. hybrid:
   level-8
   + contract-mentioned road/river
   + district boundary
Step 2 — 用 ground truth 作弊分配每个 face

对于每个 face：

label(f)=arg
k
max
	​

Area(f∩GT
k
	​

)

强制：

one face → one dealer

这一步：

不解析四至；

不做 side model；

不做 fuzzy logic；

不做 solver。

只有 representation。

Step 3 — 得到每套 representation 的理论 ceiling

报告：

MedianIoU
Q
25
	​

,Q
75
	​

Worst5
E
atom
	​

BoundaryF1
50/100/300
	​


以及：

components
Step 4 — 与当前 V1c 0.493 比较

最有价值的不是：

P4b solver 做到了多少。

而是首先知道：

P4b 表示空间最多能做到多少。

我会这样解释不同结果
情况1
StreetOracle=0.90

那么：

你中了大奖。

问题实际上不是“自然语言 → polygon”，而是：

自然语言 → street-unit labels

问题复杂度会骤降。

情况2
Street=0.72,Hybrid=0.92

我认为这是现在最值得期待的结果。

意味着：

街道/乡镇是 coarse building blocks，四至中的道路、河流、区界负责局部 split。

于是整个新架构非常清晰：

Admin-8 base tessellation
          ↓
contract landmark local split
          ↓
atomic faces
          ↓
global graph assignment
          ↓
territories

这可能成为最终方案。

情况3
HybridOracle<0.75

那么应立即停止实现复杂 global solver。

因为这意味着：

候选 geometry 本身仍然没有足够表达力。

需要继续寻找：

村/社区 level-10；

未写入合同的隐式边界；

门店归属；

历史销售区域；

更多 road hierarchy；

artificial connectors。

最后一个我认为非常重要的理论变化

你之前的问题可以描述成：

Four bounds → reconstruct one polygon

现在证据越来越支持另一种定义：

Given a jointly exhaustive set of weak boundary descriptions, recover a labeled planar partition.

也就是：

Four-Bounds Reconstruction→Weakly Supervised Planar Regionalization
	​


这是明显更准确的研究问题。

它还解释了为什么“四条线 + 一个点”的表达力上限以前这么严重：

单个合同根本未必提供完整 topology。

但是在全局系统里：

自己的四至+邻居的四至+tiling+shared boundaries

会产生一种 constraint completion。

所以我现在认为，真正值得押注的不是把 directional field 再精调 20%，而是：

把 37 个 underdetermined local reconstruction problems，改造成一个 over-constrained / softly-constrained global labeling problem。

这是这批新证据带来的最大变化。

如果只能批准一个下一步实验，我会批准 P4b-O Global Oracle Atomic Partition，并暂停 arc-selection、gap-repair 和复杂 fuzzy calculus 的继续优化，直到这个 ceiling 出来。

