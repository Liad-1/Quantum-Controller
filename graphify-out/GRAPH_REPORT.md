# Graph Report - Quantum-Controller  (2026-11-25)

## Corpus Check
- Corpus is ~12,333 words - fits in a single context window. You may not need a graph.

## Summary
- 332 nodes · 582 edges · 18 communities (12 shown, 6 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 39 edges (avg confidence: 0.87)
- Token cost: 52,106 input · 0 output

## Community Hubs (Navigation)
- MyDaq Hardware Driver
- Loopback Analysis & Raster
- GUI App & DC Panel
- Recording Alignment & Session
- Signal Configuration GUI
- Loopback Panel & Results
- Digital Input Test Rig
- Device Connection Panel
- Sent-vs-Received View Plan
- Device Session State
- Pytest Hardware Selection
- Digital Input Tests
- Word Doc Generator
- Graphify Usage Rules

## God Nodes (most connected - your core abstractions)
1. `MyDaq` - 21 edges
2. `LoopbackPanel` - 13 edges
3. `DevicePanel` - 12 edges
4. `DeviceSession` - 12 edges
5. `SimulatedDaq` - 12 edges
6. `App` - 11 edges
7. `ChannelPanel` - 10 edges
8. `DcPanel` - 10 edges
9. `OutputTestTab` - 10 edges
10. `LiveComparison` - 10 edges

## Surprising Connections (you probably didn't know these)
- `_setup_axes(fig, rate, k, view)` --references--> `plot_beam_path()`  [EXTRACTED]
  docs/plan_sent_vs_received_view.md → app/plotting/beam_path.py
- `LiveComparison view support` --references--> `LiveComparison`  [EXTRACTED]
  docs/plan_sent_vs_received_view.md → app/plotting/compare.py
- `plot_comparison view parameter (replaces remove_fit)` --references--> `plot_comparison()`  [EXTRACTED]
  docs/plan_sent_vs_received_view.md → app/plotting/compare.py
- `main()` --calls--> `App`  [EXTRACTED]
  main.py → app/gui/app.py
- `Loopback` --uses--> `MyDaq`  [INFERRED]
  tests/hardware/analog/conftest.py → app/hardware/mydaq.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **compare.py view-switch changes** — docs_plan_sent_vs_received_view_views, docs_plan_sent_vs_received_view_setup_axes, docs_plan_sent_vs_received_view_setup_transfer, docs_plan_sent_vs_received_view_livecomparison_change, docs_plan_sent_vs_received_view_plot_comparison_change [EXTRACTED 1.00]

## Communities (18 total, 6 thin omitted)

### Community 0 - "MyDaq Hardware Driver"
Cohesion: 0.08
Nodes (11): MyDaq, daq(), dc_sweep(), device(), loop(), Loopback, low_range_sweep(), pytest_terminal_summary() (+3 more)

### Community 1 - "Loopback Analysis & Raster"
Cohesion: 0.09
Nodes (17): work(), analyze(), ChannelResult, clarity_word(), LoopbackResult, run_loopback(), generate_raster_waveform(), get_scan() (+9 more)

### Community 2 - "GUI App & DC Panel"
Cohesion: 0.09
Nodes (5): DcPanel, _descendants(), OutputTestTab, plot_ao_outputs(), plot_beam_path()

### Community 3 - "Recording Alignment & Session"
Cohesion: 0.09
Nodes (7): _Aligner, _check_ao(), _check_waveform(), _find_start(), open_device(), SimulatedDaq, _valid_correlation()

### Community 4 - "Signal Configuration GUI"
Cohesion: 0.10
Nodes (6): App, ChannelPanel, closest_option(), make_signal(), signal_options(), main()

### Community 5 - "Loopback Panel & Results"
Cohesion: 0.12
Nodes (6): LoopbackPanel, format_table(), _finish_axes(), LiveComparison, plot_comparison(), _setup_axes()

### Community 6 - "Digital Input Test Rig"
Cohesion: 0.11
Nodes (10): ao_source(), AOSource, device(), di_all(), falling_thresholds(), InputRig, pytest_terminal_summary(), rig() (+2 more)

### Community 8 - "Sent-vs-Received View Plan"
Cohesion: 0.18
Nodes (14): Difference Graph (removed), Ideal y = x Reference Line, LiveComparison view support, LoopbackResult / ChannelResult (unchanged), Plan: Sent vs Received View, plot_comparison view parameter (replaces remove_fit), _setup_axes(fig, rate, k, view), _setup_transfer(ax, ch, sent, labels) (+6 more)

### Community 10 - "Pytest Hardware Selection"
Cohesion: 0.23
Nodes (6): _hardware_folder(), pytest_configure(), pytest_ignore_collect(), pytest_report_header(), pytest_sessionfinish(), _selected()

### Community 11 - "Digital Input Tests"
Cohesion: 0.24
Nodes (6): _lines_where(), test_all_inputs_high(), test_all_inputs_low(), test_inputs_toggle(), test_threshold_falling(), test_threshold_rising()

### Community 12 - "Word Doc Generator"
Cohesion: 0.22
Nodes (3): add_code_block(), add_heading(), build_document()

### Community 13 - "Graphify Usage Rules"
Cohesion: 0.50
Nodes (5): graphify-out/graph.json, GRAPH_REPORT.md / wiki index, graphify query / path / explain / section, Graphify Usage Rules (CLAUDE.md), graphify update . (AST-only refresh)

## Knowledge Gaps
- **4 isolated node(s):** `graphify query / path / explain / section`, `GRAPH_REPORT.md / wiki index`, `Plan: Sent vs Received View`, `Ideal y = x Reference Line`
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 125 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `OutputTestTab` connect `GUI App & DC Panel` to `Device Session State`, `Signal Configuration GUI`, `Loopback Panel & Results`, `Device Connection Panel`?**
  _High betweenness centrality (0.070) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `MyDaq` (e.g. with `Loopback` and `_sweep()`) actually correct?**
  _`MyDaq` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `graphify query / path / explain / section`, `GRAPH_REPORT.md / wiki index`, `Plan: Sent vs Received View` to the rest of the system?**
  _4 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `MyDaq Hardware Driver` be split into smaller, more focused modules?**
  _Cohesion score 0.07878787878787878 - nodes in this community are weakly interconnected._
- **Why does `MyDaq` connect `MyDaq Hardware Driver` to `Recording Alignment & Session`?**
  _High betweenness centrality (0.068) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `LoopbackPanel` (e.g. with `LiveComparison` and `OutputTestTab`) actually correct?**
  _`LoopbackPanel` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Should `Loopback Analysis & Raster` be split into smaller, more focused modules?**
  _Cohesion score 0.08961593172119488 - nodes in this community are weakly interconnected._