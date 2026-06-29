# Netlist Split Demo

This directory contains two demos:

- `classic_partition_demo.py`: tool-backed demo for the researched algorithms
  and projects: real KaHyPar, OpenROAD/TritonPart script generation,
  CircuitPartitioning-GNN-style PyTorch partitioning, GL0AM-style logic-cone
  grouping, and Louvain pre-clustering.
- `netlist_split_demo.py`: lightweight standard-library baseline for comparing
  simplified partitioning strategies.

Both demos parse a small Verilog subset:

- `module`, `input`, `output`, and `wire` declarations
- `assign` statements
- simple gate/flop instances with named or positional pins, such as `AND2`,
  `OR2`, `NAND2`, `NOR2`, `INV`, `XOR2`, and `DFF`

The demos model each instance or assign as a cell, then treat every net as a
hyperedge connecting all cells that touch that net.

## Classic / Researched Tool Demo

KaHyPar is installed locally under `.tooling/python`, so use `PYTHONPATH` when
running the classic demo:

```bash
PYTHONPATH=.tooling/python python3 classic_partition_demo.py \
  --input sample_netlist.v --k 4 --backend all --out classic_results
```

Backends:

- `kahypar`: real KaHyPar Python binding, using `classic_configs/*.ini`
- `openroad`: generates hMETIS `.hgr` and OpenROAD/TritonPart Tcl under
  `classic_results/openroad_tritonpart/`; runs it only if `openroad` exists
- `gnn`: PyTorch GCN-style reproduction of the CircuitPartitioning-GNN idea
- `gl0am`: GL0AM-style logic-cone grouping for GPU block style partitioning
- `louvain`: NetworkX Louvain community pre-clustering baseline

The classic run writes:

- `classic_results/<backend>/metrics.json`
- `classic_results/<backend>/partitions.tsv`
- `classic_results/<backend>/partition_<n>.v`
- `classic_results/openroad_tritonpart/run_tritonpart_hypergraph.tcl`
- `classic_results/demo_top.hgr`, `cells.tsv`, and `nets.tsv`

## Lightweight Baseline Demo

Algorithms:

- `random`: seeded random baseline with round-robin balancing
- `greedy`: places high-connectivity cells where they have the most existing
  affinity while respecting size balance
- `fm`: Kernighan-Lin/FM-style local single-cell moves that reduce cut cost
- `multilevel`: explainable spectral/multilevel proxy using weighted BFS order,
  balanced slicing, and local refinement

## Run

```bash
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all
```

Write machine-readable metrics, partition maps, and demo sub-netlists:

```bash
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo all --out results_k4
```

Run one algorithm:

```bash
python3 netlist_split_demo.py --input sample_netlist.v --k 4 --algo fm
```

## Test

```bash
PYTHONPATH=.tooling/python python3 -m unittest -v
```

The report includes partition membership, cut nets, cut cost, balance, and a
rough estimated parallel speedup. The speedup is only a demo heuristic: it
penalizes many cut nets and imbalanced partitions.

When `--out` is set, each algorithm directory contains:

- `metrics.json`: summary metrics
- `partitions.tsv`: cell-to-partition assignment
- `partition_<n>.v`: simplified sub-netlist skeleton with boundary cut nets
