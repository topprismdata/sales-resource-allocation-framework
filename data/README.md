# Region Data Pack — Data Switching Guide

Demo supports multiple regions: **Data switching = prepare a directory + start with `--data-dir`**.
Defaults to loading `data/gz` (Guangzhou). All responses carry `Cache-Control: no-store`, preventing stale page delivery.

## Data Pack Structure

```text
data/<region>/
├── region.json      # Required. fences + stores + kinds (schema below)
├── contracts.json   # Required. Contract package (four bounds description + center point)
├── meta.json        # Required. Region name / map center / direct supply brand list
└── osm_parsed.json  # Optional. Without it, "four bounds reconstruction" degrades to requiring manual interpretation
```

## Three Steps to Switch to a New City

```bash
# ① Pull OSM landmarks (waterways/main roads/district boundaries, ~1-3 minutes)
python3 tools/fetch_region_osm.py --bbox 22.8,113.0,23.2,113.6 --out data/mycity

# ② Load store/fence/contract data (schema below), then validate
python3 tools/validate_region_pack.py data/mycity

# ③ Start
python3 tools/demo_server.py --data-dir data/mycity 8765
```

## Schema Quick Reference

### region.json (isomorphic to historical gz_data.json)

```json
{
"fences": [{"area_id": "...", "dealer": "dealer full name", "area_km2": 8.1,
               "rings": [[[lon,lat], …]]}],
"stores": [{"n": "store name", "c": "channel", "d": "district", "u": "actual upstream",
               "lon": 113.2, "lat": 23.0, "direct": false,
"dealers": ["dealer in the fence"], "kind": "OK"}],
  "kinds": {"OK": 0, "OOF": 0, "DIRECT_IN": 0, "DIRECT": 0, "GAP": 0, "MULTI": 0}
}
```

- `kind` six-class semantics (World Model L4, validator enforces valid values):
OK in-fence consistent / OOF out-of-fence supply / DIRECT_IN direct supply KA (internal) /
DIRECT direct supply KA (external) / GAP coverage gap / MULTI multi-fence
- `kinds` count must match stores count (validator checks)
- `direct`: whether upstream is a direct supply brand (refer to meta.direct_markers)

### contracts.json

```json
[{"dealer_id": "dealer full name (must match fences.dealer; no match = greenfield draft generation)",
"district": "district", "four_bounds": {"N":"...","S":"...","E":"...","W":"..."},
  "center": [lon, lat], "reserved_channels": ["…"], "store_count": 100}]
```

### meta.json

```json
{"region_name": "city name", "center": [lon, lat], "zoom": 10,
 "crs": "GCJ-02",
"direct_markers": ["Walmart", "Meiyijia", …],
 "density_assumption_stores_per_km2": 40}
```

**Coordinate System Contract (crs)**: Longitude/latitude declarations in region.json/contracts.json are
`GCJ-02` (Amap/Tencent/Tianditu system, default) or `WGS84` (OSM/Google/frontend point selection).
On server load, normalized to WGS-84 once for internal geometry operations (OSM landmarks/tiles follow the standard),
On persistence write-back, reverse-converted to the declared coordinate system—internal system never mixes the two systems.
Measured mixed use of both systems = ~623m systematic offset in Guangzhou, sufficient to distort four-bounds road-following judgments, fence edge-fitting,
and base map alignment completely.

## Non-existence Before Generation (Existence Semantics)

Initially a blank map—fences are the product of "contract four bounds → interpretation":
- Contract dealer has historical fence → adopt historical interpretation (`interpretation: accepted`)
- No history → OSM boundary reconstruction draft (`draft`, low quality will be marked as requiring manual interpretation)

Multi-pack parallel: different ports + different `--data-dir` can start multiple region instances simultaneously.

## LLM Semantic Adjustment

Relies on local Anthropic-compatible proxy (env in `~/.claude/settings.json`),
Model defaults to MiniMax-M3 (`SRAF_LLM_MODEL` can override). If proxy unavailable, falls back to rule-based fallback.
