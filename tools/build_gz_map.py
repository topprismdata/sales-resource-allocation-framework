#!/usr/bin/env python3
"""生成经销商围栏现状地图（自包含 HTML，Leaflet CDN + 内嵌数据 JSON）。

用法：python3 tools/build_gz_map.py /tmp/gz_data.json docs/visualizations/gz_dealer_fences_map.html
数据源与口径见 analysis/DP06_GAP_ANALYSIS*.md 与 analysis/CN_MARKET_*.md。
"""
import json
import sys
from pathlib import Path

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>广州办 · 经销商围栏现状地图（v1.2 基线 · 现状即基线）</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html,body{margin:0;height:100%;font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
  #map{height:100%}
  #panel{position:absolute;top:10px;left:10px;z-index:1000;background:#fff;
    padding:12px 14px;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,.25);
    width:305px;max-height:94%;overflow:auto;font-size:13px;line-height:1.55}
  h1{font-size:15px;margin:0 0 6px}
  .sub{color:#666;font-size:11.5px;margin-bottom:8px}
  table{width:100%;border-collapse:collapse;font-size:12px}
  td{padding:1px 4px}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
  label.k{display:block;margin:2px 0;cursor:pointer}
  select{width:100%;padding:4px;margin-top:4px}
  .note{color:#8a6d3b;background:#fcf8e3;border:1px solid #faebcc;border-radius:6px;
    padding:6px 8px;font-size:11.5px;margin-top:8px}
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h1>广州办 · 经销商围栏现状</h1>
  <div class="sub">围栏 = 经销商责任服务区（应然）· 上游客户 = 实际供货（实然）。<br>
  非围栏供货是正常业务形态的洞察信号，不是错误。</div>
  <table>
    <tr><td><span class="dot" style="background:#2e7d32"></span>围栏内·上游一致</td><td align="right" id="nOK"></td></tr>
    <tr><td><span class="dot" style="background:#ef6c00"></span>非围栏供货（洞察）</td><td align="right" id="nOOF"></td></tr>
    <tr><td><span class="dot" style="background:#1565c0"></span>直供KA·围栏内</td><td align="right" id="nDIN"></td></tr>
    <tr><td><span class="dot" style="background:#9e9e9e"></span>直供KA·围栏外(正常)</td><td align="right" id="nDIR"></td></tr>
    <tr><td><span class="dot" style="background:#c62828"></span>覆盖缺口</td><td align="right" id="nGAP"></td></tr>
    <tr><td><span class="dot" style="background:#6a1b9a"></span>多围栏交界</td><td align="right" id="nMUL"></td></tr>
  </table>
  <div style="margin-top:8px">
    <b>门店筛选</b>
    <label class="k"><input type="checkbox" checked onchange="filt()" data-k="OK"> 围栏内一致</label>
    <label class="k"><input type="checkbox" checked onchange="filt()" data-k="OOF"> 非围栏供货</label>
    <label class="k"><input type="checkbox" checked onchange="filt()" data-k="DIRECT_IN"> 直供KA(内)</label>
    <label class="k"><input type="checkbox" onchange="filt()" data-k="DIRECT"> 直供KA(外)</label>
    <label class="k"><input type="checkbox" checked onchange="filt()" data-k="GAP"> 覆盖缺口</label>
    <label class="k"><input type="checkbox" onchange="filt()" data-k="MULTI"> 多围栏</label>
  </div>
  <div><b>聚焦经销商</b><select id="dealer" onchange="filt()"><option value="">全部</option></select></div>
  <div class="note">现状即基线：本页是现状数字化视图。区域调整建议由 agentic 分析另行产出，
  全部落在 PLANNING 模型走审批，不直改生效围栏。</div>
</div>
<script>
const DATA = __DATA__;
const KIND_COLOR = {OK:"#2e7d32", OOF:"#ef6c00", DIRECT_IN:"#1565c0",
                    DIRECT:"#9e9e9e", GAP:"#c62828", MULTI:"#6a1b9a"};
const KIND_NAME = {OK:"围栏内一致", OOF:"非围栏供货", DIRECT_IN:"直供KA(内)",
                   DIRECT:"直供KA(外)", GAP:"覆盖缺口", MULTI:"多围栏"};
const counts = DATA.kinds;
for (const [id,k] of [["nOK","OK"],["nOOF","OOF"],["nDIN","DIRECT_IN"],["nDIR","DIRECT"],["nGAP","GAP"],["nMUL","MULTI"]])
  document.getElementById(id).textContent = counts[k] || 0;

const map = L.map("map", {preferCanvas: true, minZoom: 8});
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  {attribution: "© OpenStreetMap contributors", maxZoom: 18}).addTo(map);

const PALETTE = ["#e6194b","#3cb44b","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6",
"#bcf60c","#fabebe","#008080","#9a6324","#800000","#808000","#000075","#808080"];
const dealerColor = {};
let pi = 0;
for (const f of DATA.fences) dealerColor[f.dealer] = PALETTE[pi++ % PALETTE.length];

const canvas = L.canvas({padding: 0.3});
const storeLayers = {};
const dealerSelect = document.getElementById("dealer");
const dealers = [...new Set(DATA.fences.map(f => f.dealer))].sort();
for (const d of dealers) {
  const o = document.createElement("option"); o.value = d; o.textContent = d;
  dealerSelect.appendChild(o);
}

for (const f of DATA.fences) {
  const poly = L.polygon(f.rings[0].map(p => [p[1], p[0]]), {
    color: dealerColor[f.dealer], weight: 1.4, fillOpacity: 0.12,
  }).addTo(map);
  poly.bindTooltip(
    `<b>${f.dealer}</b><br>围栏面积 ${f.area_km2} km² · 门店 ${f.store_count}`,
    {sticky: true});
}

for (const s of DATA.stores) {
  const ly = L.circleMarker([s.lat, s.lon], {
    renderer: canvas, radius: 1.8, stroke: false,
    fillColor: KIND_COLOR[s.kind], fillOpacity: 0.75,
  }).bindTooltip(`<b>${s.n}</b><br>${s.d} · ${s.c}<br>上游: ${s.u||"—"}<br>状态: ${KIND_NAME[s.kind]}`,
    {sticky: true, direction: "top"});
  ly._kind = s.kind;
  ly._dealers = s.dealers || [];
  ly.addTo(map);
  (storeLayers[s.kind] = storeLayers[s.kind] || []).push(ly);
}

function filt() {
  const shown = {};
  document.querySelectorAll("input[data-k]").forEach(cb => shown[cb.dataset.k] = cb.checked);
  const focus = dealerSelect.value;
  for (const kind in storeLayers) {
    for (const ly of storeLayers[kind]) {
      let vis = shown[kind] !== false;
      if (vis && focus) vis = ly._dealers.includes(focus);
      if (vis) ly.addTo(map); else map.removeLayer(ly);
    }
  }
}
map.fitBounds([[22.4, 112.6], [23.9, 114.8]]);
filt();
</script>
</body>
</html>
"""


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"written {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
