# GrowthNetwork

GrowthNetwork 2.3.4 is a Python 3.12+ museum visitor trajectory co-creative projection system. It turns recorded visitor movements into a dense, flat capillary-red field between four fixed exhibition anchors. Every visible branch is attached either to a real exhibit node or to an observed visitor artery; the model creates no unanchored decorative lines.

The application validates six related CSV files, retains a directed NetworkX graph for analysis, animates an accumulating glow-on-black projection with pygame, and exports the complete parent-child curve hierarchy as Blender-ready JSON. `growth_network.py` remains the only application source file.

## Install and run

From the `GrowthNetwork` directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python growth_network.py
```

The project uses `pygame-ce`, which provides the normal `import pygame` API and publishes wheels for current Python versions. This avoids the legacy `pygame` build failure involving `setuptools._distutils.msvccompiler` on newer Python installations.

The default run reads `./data`, exports `growth_network_curves.json`, and opens the real-time projection window. Existing controls are unchanged:

- Space: pause or resume;
- 1: restart as the early cohort (first 25% of visitors);
- 2: restart as the middle cohort (first 60% of visitors);
- 3: restart as the complete visitor cohort;
- R: restart the accumulation;
- S: save `growth_network_screenshot.png`;
- H: hide or show the status line; and
- Esc or Q: quit.

For a headless, reproducible Blender export:

```powershell
python growth_network.py --no-render --seed 42 --output growth_network_curves.json
```

For a 1920 x 1080 floor projection with slower growth:

```powershell
python growth_network.py --width 1920 --height 1080 --fps 30 --main-duration-scale 4.0
```

Other useful commands:

```powershell
python growth_network.py --validate-only
python growth_network.py --help
python growth_network.py --loop
python growth_network.py --hold 10
python growth_network.py --attraction-strength 0.52 --curvature-strength 0.13
python growth_network.py --capillary-density 1.5 --trail-decay 30 --memory-floor 0.2
python growth_network.py --dendrite-density 1.7 --dendrite-length 1.15
python growth_network.py --visitor-limit 5
python growth_network.py --data-dir "E:\UOE\Dissertation (Design, Context & Communication)\data"
```

`--hold` is negative by default, so the completed collective image remains visible until the window is closed. A non-negative value closes the renderer that many seconds after completion. `--main-duration-scale` controls the animation pace; a larger value creates calmer, slower growth. `--visitor-limit` selects an initial cumulative cohort while retaining the full CSV and JSON export.

## Browser animation

The `web` directory contains an exhibition-site presentation built around the same HTML Canvas 2D geometry. A restrained editorial header, curatorial introduction, anatomical network stage, growth controls, method summary, and source-derived collective metrics frame the live work without replacing it with a screenshot. The page reads `web/data/web_network.json`, which preserves all four node positions, arterial centrelines, recursive capillary segments, parent identifiers, hierarchy levels, taper widths, and deterministic timing from the current Blender JSON. The supplied Brain, Eye, Heart, and Lung PNGs remain visible from the first frame, while deterministic blue parent-child vessels grow inside their transparent silhouettes.

The page now begins with a four-exhibit visitor study. After selecting **Enter**, a visitor can open Brain, Eye, Heart, and Lung in any order. Each detail view measures real dwell time; completing the fourth exhibit records the unique visitor ID, first-view sequence, per-exhibit dwell totals, and individual view events. The result page automatically selects **Your journey**. Its purple route reuses the exact existing arterial points and node-rooted capillary branches from `web_network.json`: no new path geometry is generated. Pointer movement replays the chosen order, while longer dwell selects more of the existing local branch hierarchy.

Completed sessions are always retained in browser storage. The supplied server validates each session and appends a local backup to `web/data/visitor_sessions.jsonl`:

```powershell
python web_server.py
```

When the four GitHub environment variables below are present, the same endpoint also stores each completed session as an independent JSON file in a private repository. One file per session prevents concurrent visitors from replacing a shared file. The fine-grained token must have **Contents: read and write** access only to the private data repository.

```text
GITHUB_TOKEN=<fine-grained token; never commit this value>
GITHUB_OWNER=liguming9
GITHUB_DATA_REPO=GrowthNetwork-Visitor-Data
GITHUB_DATA_BRANCH=main
```

The browser never receives the token. If GitHub storage is unavailable, the API returns an error while retaining the best-effort local backup. `GET /api/health` reports whether the running service is configured for `github` or `local` storage without exposing credentials.

The existing static-server command remains supported when server-side recording is not required:

```powershell
python -m http.server 8000
```

Then open:

```text
http://localhost:8000/web/
```

### Public Render deployment

The repository includes `render.yaml` and `.python-version`. Render can therefore serve the static exhibition page and the narrow Python recording endpoint from the same HTTPS origin; no cross-origin browser permissions are required.

1. In Render, choose **New > Blueprint** and connect the public `liguming9/GrowthNetwork` repository.
2. Render reads `render.yaml` and asks for `GITHUB_TOKEN` because the secret is declared with `sync: false`.
3. Paste the fine-grained token into Render's secret field. Do not put it in GitHub, `app.js`, screenshots, or support messages.
4. Create the Blueprint and wait for the health check to pass.
5. Open `https://<render-service>.onrender.com/web/` and complete one four-exhibit test.
6. Confirm that a new file appears under `sessions/YYYY-MM-DD/` in the private data repository.

The Render build deliberately compiles only `web_server.py`; the public browser service does not require pygame, NetworkX, or a display. Regenerating the desktop and Blender geometry remains a separate local workflow.

The browser uses three independent clocks so short-term observation, long-term exhibition memory, and one visitor's study are not conflated. The segmented control above the network selects which clock the pointer scrubs. **On-site data** controls the red connections between exhibits; **Exhibition memory** controls only the blue vessels on the anatomical images; **Your journey** controls the purple overlay made from the recorded pre-test. On-site arteries replay all visitor movements at their deterministic, staggered start times. A traversal begins at its real source node, so reverse records grow from the opposite end of the same centreline. Every completed traversal reinforces that centreline's local thickness; no parallel copy is created. On desktop, left-to-right means beginning-to-present. The network is proportionally reduced and shifted into the right-hand field so it does not collide with the curatorial title. On mobile, the complete network rotates clockwise by 90 degrees and fills a taller stage; organ images and labels are counter-rotated so they remain upright. An upward swipe advances the selected timeline by relative gesture distance, while a downward swipe rewinds it. The animation stage retains the gesture until the selected layer reaches 100%; a new upward swipe is then handed back to native page scrolling so the visitor can continue to the timeline and information cards. Switching modes, replaying, resetting, or scrubbing one clock never changes the others.

A responsive calendar axis separates the animation from the data cards. It covers 1–30 July 2026 and permanently marks 10 July as the current visitor's attendance date. Exhibition-memory movement updates the axis in real time: the active day grows typographically, turns red, and automatically scrolls into the centre while the on-site-data clock remains unchanged. Every calendar day is a button: selecting it immediately shows the blue anatomical-memory accumulation for that date. Both animation timelines remain accessible in the Growth controls card, with independent play/reset actions and a shared 0.5×/1×/2× playback speed. Canvas rendering uses real high-DPI pixels capped at devicePixelRatio 3.

`growth_network_curves.json` remains the Blender source of truth. After generating a new Python/Blender export, rebuild the compact browser dataset without changing `growth_network.py`:

```powershell
python export_web_network.py
```

This writes identical copies to `export/web_network.json` and `web/data/web_network.json`. New Blender exports include explicit per-traversal timing and direction. For compatibility with an older export, the converter reconstructs the same schedule from its embedded `graph.visitor_routes` and generation configuration. Browser timing is deterministic: visitor routes begin at their own times, each dwell branch waits until its parent reaches the attachment point, and deeper levels start later. Organ images remain visible throughout. Their blue surface-vessel hierarchy uses a separate normalized exhibition schedule, so it persists when the on-site data clock returns to its first frame. A subtle breathing motion starts only when both independent timelines are complete.

## Hierarchical capillary method

The four locations in `nodes.csv` are fixed exhibition anchors. Ordered events in `visitor.csv` are retained as directed source-to-target movements in NetworkX. The renderer then combines both directions of the same artwork pair into one visual corridor.

Each corridor is generated only once. Repeated visits reinforce its width and luminance instead of creating parallel full-edge copies. A low-frequency seeded Perlin field defines one broad organic drift. Repeated smoothing and an explicit curvature bound prevent sharp turns and sinusoidal waves while preserving exact node endpoints.

Local parent-child trees grow from irregular positions on the centreline and directly from the four artwork nodes. A child always begins at its parent, grows away from that junction, becomes thinner and shorter, and normally ends freely. Terminal branches do not reconnect by default, preventing loops, mirrored arches, and road-like bundles.

The rendered hierarchy has three spatial levels:

1. `artery`: exactly one thick collective centreline for all traffic between the same pair of exhibits;
2. `dwell_dendrite`: recursive local branches rooted exactly at an exhibit node; and
3. `route_dendrite`: recursive local branches rooted at data-weighted points along an artery.

Every dendrite segment stores an explicit `parent_id`. Artery-rooted secondary branches retain the 25-35% local-width calculation but are constrained to a projection-readable 1.2-2.2 pixel range. Later child widths are 55-72% of their parent and child lengths are 58-82%, with 25-65 degree bifurcation angles. Every surviving tree can form a tertiary hierarchy; higher normalized `DeepVisitCount` evidence supports fourth and selective fifth generations. Increased continuation survival lets branches branch again instead of ending as isolated twigs. A spatial occupancy grid still suppresses severe crowding and biases headings toward empty tissue, while higher dwell engagement receives greater density tolerance.

Route branch attempts combine normalized `AverageDwell`, the reconciled relationship `Density`, and transition `Count`. Dwell remains the strongest influence, Density now expands the local capillary field more decisively, and Count adds a smaller activity reinforcement. Node-rooted attempts are separately capped by `VisitCount`, producing more numerous short, irregular biological roots around Brain, Eye, Heart, and Lung.

The longest connection is pulled gently toward the inner field, while medium-long perimeter connections receive an inward control-point bias. This breaks the closed fish/leaf-like outline that can otherwise form when upper and lower routes bow away from the centre.

Animation remains cumulative. Main vessels initiate first, local trees unfold as visitor records become active, and completed geometry remains as spatial memory. Keys 1, 2, and 3 restart growth with 25%, 60%, or 100% of the visitor cohort.

## Data-to-visual mapping

| Data evidence | Visual role |
|---|---|
| All traffic across an undirected artwork pair | Exactly one collective `artery` |
| Summed directed edge Count/Weight | Artery width and brightness |
| Timed forward/reverse transitions | Source-end or target-end growth on one centreline; each arrival increases local artery width |
| Corridor `AverageDwell` | Probability and local density of artery-rooted branches |
| Exhibit `VisitCount` | Maximum number of node-rooted first-generation branches |
| Exhibit `AverageDwell` | Root probability, bifurcation probability, line luminance, and node glow |
| Exhibit `DeepVisitCount` | Recursive depth, branch lifetime, and maximum length |
| Ordered route and dwell values | Animation activation and growth duration |
| Seeded 2D Perlin noise | Gentle organic curvature constrained between real anchors |
| Local fine-vessel occupancy | Suppresses crowded splits and encourages exploration |
| Parent generation | Progressively shorter, thinner, and dimmer capillaries |
| Cumulative visitor rank | Determines whether a curve appears in early, middle, or final growth |

The renderer uses pure black with restrained blood-red variations only. Each artery is one clean flat 2D stroke with a single subtle red support glow: there is no inner lumen, shaded vessel body, ribbon, pipe, or cylindrical tube effect. Width changes continuously from about 100% at the artwork node to about 68% at mid-span and back to about 105% at the target. Antialiased boundaries, smooth curves, and rounded terminal caps keep the linework clear. Secondary and tertiary branches remain thinner, taper continuously, and fade toward fine tips. Data is expressed through width, red luminance, density, persistence, and branching complexity. Exhibition anchors use VisitCount-scaled 4.5-8.5 pixel red cores with low-energy red bloom instead of rings.

The main appearance controls remain `--attraction-strength`, `--curvature-strength`, `--capillary-density`, `--dendrite-density`, `--dendrite-length`, `--trail-decay`, and `--memory-floor`. Fine capillaries are cached at 6 Hz while growing arteries remain at the requested frame rate, preserving a calm 30 FPS projection. Results are deterministic for a fixed seed and dataset.

## Sample data provenance

The bundled sample contains 20 visitors, 76 artwork visits, 56 consecutive route segments, all 12 directed transition combinations, and all 6 undirected corridors between the four exhibits. Visitors 1-3 are the supplied source observations. Visitors 4-20 are synthetic records added to provide enough variation for generative testing; they must not be reported as real field observations in dissertation findings.

All aggregate CSV tables were recalculated from the visitor-level records. The original files on drive `E:` were not modified.

Summary values are defined as follows:

- node `VisitCount`: number of visitor events at the exhibit;
- node `AverageDwell`: mean `DwellTime` at the exhibit;
- `DeepVisitCount`: events or transition targets with `DwellTime >= 30` seconds;
- edge `Weight`: observed directed source-to-target transition count;
- edge `AverageDwell`: mean target dwell for the directed transition;
- relationship/network `AvgDwell`: mean source and target dwell for each segment;
- `Thickness`: segment `AvgDwell / 50`; and
- `Density`: transition count divided by the largest transition count.

## Validation

Validation runs before graph construction and reports all discovered issues together. It checks:

- all six files, required headers, non-empty rows, UTF-8 parsing, and finite numeric values;
- non-negative counts, dwell values, weights, thicknesses, and densities;
- unique artwork IDs/names, node IDs, directed edges, relationships, and network segments;
- artwork-to-node identifiers and all graph endpoints;
- unique, contiguous visit order for each visitor;
- the existence of every observed visitor transition in `edges.csv`;
- relationship/network membership in the full directed edge table;
- exact reconciliation of visitor-derived counts, rounded dwell means, deep-visit counts, thickness, and density; and
- agreement between every `network.csv` endpoint and its `artwork.csv` coordinates.

The numeric artwork ID in `artwork.csv` is intentionally distinct from the name-valued `ArtworkID` in `visitor.csv`. Dataset joins use artwork names because those are also the node identifiers.

## Blender JSON

`growth_network_curves.json` retains format version 2.3 for compatibility. It contains source provenance, the directed analytical graph, four anchor nodes, one artery per observed artwork corridor, node/route dendrites, explicit parent IDs, cumulative visitor activation counts, local root fractions, memory-retention floors, visual-tone metadata, reinforcement times, tapered radii, screen coordinates, and Blender coordinates. Blender points lie on a right-handed XY plane at Z=0, centred on the pygame canvas. Screen Y is inverted and coordinates are divided by `pixels_per_blender_unit` (50 by default).

The following Blender script imports the complete artery-and-branch hierarchy:

```python
import bpy
import json

json_path = r"C:\path\to\growth_network_curves.json"
with open(json_path, "r", encoding="utf-8") as handle:
    payload = json.load(handle)

collection = bpy.data.collections.new("GrowthNetwork")
bpy.context.scene.collection.children.link(collection)

for item in payload["curves"]:
    data = bpy.data.curves.new(item["id"], type="CURVE")
    data.dimensions = "3D"
    data.bevel_depth = item["bevel_depth"]
    data.bevel_resolution = 3
    spline = data.splines.new("POLY")
    spline.points.add(len(item["points"]) - 1)
    for point, coordinate, radius in zip(spline.points, item["points"], item["radii"]):
        point.co = (*coordinate, 1.0)
        point.radius = radius
    obj = bpy.data.objects.new(item["id"], data)
    obj["branch_type"] = item["type"]
    obj["brightness"] = item["metrics"]["brightness"]
    collection.objects.link(obj)
```

## Project layout

```text
GrowthNetwork/
|-- growth_network.py          # complete application
|-- requirements.txt           # NetworkX and pygame-ce
|-- pyproject.toml             # Python 3.12+ package metadata
|-- README.md                  # operation and dissertation method notes
|-- growth_network_curves.json # reproducible seed-42 Blender export
|-- growth_network_preview.png # final-frame visual reference
|-- export_web_network.py      # Blender JSON to browser JSON converter
|-- export/web_network.json    # canonical compact browser export
|-- web/                       # Canvas page, controls, organ assets, and data
`-- data/                      # six validated CSV inputs
```
