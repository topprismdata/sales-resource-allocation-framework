# 区域数据包（Region Data Pack）— 换数据指南

Demo 支持多区域：**换数据 = 准备一个目录 + `--data-dir` 启动**。
默认加载 `data/gz`（广州）。所有响应带 `Cache-Control: no-store`，不会吃到旧页面。

## 数据包结构

```text
data/<region>/
├── region.json      # 必需。fences + stores + kinds（schema 见下）
├── contracts.json   # 必需。合同包（四至描述 + 中心点）
├── meta.json        # 必需。区域名 / 地图中心 / 直供品牌清单
└── osm_parsed.json  # 可选。无它则「四至重建」降级为需人工解释
```

## 三步换到新城市

```bash
# ① 抓 OSM 地标（河道/主干道/区县边界，约 1-3 分钟）
python3 tools/fetch_region_osm.py --bbox 22.8,113.0,23.2,113.6 --out data/mycity

# ② 放入门店/围栏/合同数据（schema 见下），然后校验
python3 tools/validate_region_pack.py data/mycity

# ③ 启动
python3 tools/demo_server.py --data-dir data/mycity 8765
```

## schema 速查

### region.json（与历史 gz_data.json 同构）

```json
{
  "fences": [{"area_id": "…", "dealer": "经销商全名", "area_km2": 8.1,
               "rings": [[[lon,lat], …]]}],
  "stores": [{"n": "门店名", "c": "渠道", "d": "区县", "u": "实际上游",
               "lon": 113.2, "lat": 23.0, "direct": false,
               "dealers": ["所在围栏经销商"], "kind": "OK"}],
  "kinds": {"OK": 0, "OOF": 0, "DIRECT_IN": 0, "DIRECT": 0, "GAP": 0, "MULTI": 0}
}
```

- `kind` 六分类语义（世界模型 L4，校验器强制合法值）：
  OK 围栏内一致 / OOF 非围栏供货 / DIRECT_IN 直供KA(内) /
  DIRECT 直供KA(外) / GAP 覆盖缺口 / MULTI 多围栏
- `kinds` 计数必须与 stores 数一致（校验器检查）
- `direct`: 上游是否直供品牌（对照 meta.direct_markers）

### contracts.json

```json
[{"dealer_id": "经销商全名（须与 fences.dealer 对应；无对应=greenfield 草案生成）",
  "district": "区", "four_bounds": {"北":"…","南":"…","东":"…","西":"…"},
  "center": [lon, lat], "reserved_channels": ["…"], "store_count": 100}]
```

### meta.json

```json
{"region_name": "城市名", "center": [lon, lat], "zoom": 10,
 "crs": "GCJ-02",
 "direct_markers": ["沃尔玛", "美宜佳", …],
 "density_assumption_stores_per_km2": 40}
```

**坐标系契约（crs）**：region.json/contracts.json 的经纬度声明为
`GCJ-02`（高德/腾讯/天地图系，缺省即此）或 `WGS84`（OSM/谷歌/前端点选）。
服务端加载时一次性归一为 WGS-84 供内部几何运算（OSM 地标/瓦片同标准），
持久化写盘时逆转换回声明坐标系——内部系统绝不混两系。
实测混用两系 = 广州 ~623m 系统偏移，足以让四至沿路判定、围栏贴边、
底图对齐全部失真。

## 生成前不存在（存在性语义）

初始为空白地图——围栏是「合同四至 → 解释」的产物：
- 合同 dealer 有历史围栏 → 采用历史解释（`interpretation: accepted`）
- 无历史 → OSM 界线重建草案（`draft`，质量低会标注需人工解释）

多包并行：不同端口 + 不同 `--data-dir` 可同时开多个区域实例。

## LLM 语义调整

依赖本地 Anthropic 兼容代理（`~/.claude/settings.json` 的 env），
模型默认 MiniMax-M3（`SRAF_LLM_MODEL` 可覆盖）。代理不可用自动落规则兜底。
