#!/usr/bin/env python3
"""Small netlist graph partitioning demo.

The parser intentionally supports a compact Verilog subset for experiments:
module/input/output/wire declarations, continuous assign statements, and simple
gate/flop instances. The partitioner treats each instance/assign as a cell and
each net as a hyperedge connecting the cells that touch it.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import random
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set, Tuple


@dataclass
class Cell:
    name: str
    kind: str
    pins: Dict[str, str]
    weight: int = 1

    def nets(self) -> Set[str]:
        return set(self.pins.values())


@dataclass
class Netlist:
    module: str = "unknown"
    inputs: Set[str] = field(default_factory=set)
    outputs: Set[str] = field(default_factory=set)
    wires: Set[str] = field(default_factory=set)
    cells: List[Cell] = field(default_factory=list)

    @property
    def cell_names(self) -> List[str]:
        return [cell.name for cell in self.cells]

    def net_to_cells(self) -> Dict[str, Set[str]]:
        touched: Dict[str, Set[str]] = collections.defaultdict(set)
        for cell in self.cells:
            for net in cell.nets():
                if net and not is_constant(net):
                    touched[net].add(cell.name)
        return dict(touched)

    def adjacency(self) -> Dict[str, Dict[str, int]]:
        adj: Dict[str, Dict[str, int]] = {cell.name: {} for cell in self.cells}
        for cells in self.net_to_cells().values():
            ordered = sorted(cells)
            for i, left in enumerate(ordered):
                for right in ordered[i + 1 :]:
                    adj[left][right] = adj[left].get(right, 0) + 1
                    adj[right][left] = adj[right].get(left, 0) + 1
        return adj


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//.*", "", text)


def split_names(body: str) -> List[str]:
    names: List[str] = []
    for item in body.split(","):
        item = re.sub(r"\[[^\]]+\]", " ", item)
        item = item.replace("reg", " ").replace("wire", " ")
        item = item.strip()
        if item:
            names.extend(part for part in re.split(r"\s+", item) if part)
    return names


def parse_header_ports(body: str, netlist: Netlist) -> None:
    current_direction: Optional[str] = None
    for item in body.split(","):
        item = item.strip()
        if not item:
            continue
        direction_match = re.match(r"(input|output)\b\s*(.*)$", item)
        if direction_match:
            current_direction = direction_match.group(1)
            item = direction_match.group(2)
        if current_direction not in {"input", "output"}:
            continue
        names = split_names(item)
        if current_direction == "input":
            netlist.inputs.update(names)
        else:
            netlist.outputs.update(names)


def is_constant(net: str) -> bool:
    return bool(re.fullmatch(r"(1'b[01xXzZ]|[01])", net.strip()))


def normalize_net(expr: str) -> str:
    expr = expr.strip()
    expr = expr.lstrip("~!")
    expr = expr.strip("() ")
    return expr


def parse_positional_instance(kind: str, name: str, args: str) -> Cell:
    nets = [normalize_net(item) for item in args.split(",") if item.strip()]
    pins: Dict[str, str] = {}
    for i, net in enumerate(nets):
        pin = "Y" if i == 0 else f"A{i}"
        pins[pin] = net
    return Cell(name=name, kind=kind.upper(), pins=pins)


def parse_named_instance(kind: str, name: str, args: str) -> Cell:
    pins: Dict[str, str] = {}
    for pin, net in re.findall(r"\.(\w+)\s*\(\s*([^)]+?)\s*\)", args):
        pins[pin.upper()] = normalize_net(net)
    return Cell(name=name, kind=kind.upper(), pins=pins)


def parse_assign(index: int, stmt: str) -> Cell:
    lhs, rhs = stmt.split("=", 1)
    lhs = normalize_net(lhs)
    terms = re.findall(r"[A-Za-z_][A-Za-z0-9_$]*(?:\[[^\]]+\])?|1'b[01xXzZ]|[01]", rhs)
    pins = {"Y": lhs}
    for i, term in enumerate(terms):
        pins[f"A{i + 1}"] = normalize_net(term)
    return Cell(name=f"assign_{index}", kind="ASSIGN", pins=pins)


def parse_verilog(text: str) -> Netlist:
    clean = strip_comments(text)
    netlist = Netlist()

    header = re.search(r"\bmodule\s+(\w+)\s*\((.*?)\)\s*;", clean, flags=re.S)
    if header:
        netlist.module = header.group(1)
        parse_header_ports(header.group(2), netlist)

    assign_index = 0
    for raw_stmt in clean.split(";"):
        stmt = " ".join(raw_stmt.split())
        if not stmt:
            continue

        module_match = re.match(r"module\s+(\w+)\s*\((.*)\)$", stmt)
        if module_match:
            netlist.module = module_match.group(1)
            continue
        if stmt == "endmodule":
            continue

        decl_match = re.match(r"(input|output|wire)\s+(.+)$", stmt)
        if decl_match:
            target = getattr(netlist, decl_match.group(1) + "s")
            target.update(split_names(decl_match.group(2)))
            continue

        if stmt.startswith("assign "):
            assign_index += 1
            netlist.cells.append(parse_assign(assign_index, stmt[len("assign ") :]))
            continue

        inst_match = re.match(r"(\w+)\s+(\w+)\s*\((.*)\)$", stmt)
        if inst_match:
            kind, name, args = inst_match.groups()
            if args.lstrip().startswith("."):
                netlist.cells.append(parse_named_instance(kind, name, args))
            else:
                netlist.cells.append(parse_positional_instance(kind, name, args))

    return netlist


def load_netlist(path: str) -> Netlist:
    with open(path, "r", encoding="utf-8") as handle:
        return parse_verilog(handle.read())


def round_robin_balance(cells: Sequence[str], k: int) -> Dict[str, int]:
    return {cell: i % k for i, cell in enumerate(cells)}


def random_partition(netlist: Netlist, k: int, seed: int = 7) -> Dict[str, int]:
    names = list(netlist.cell_names)
    rng = random.Random(seed)
    rng.shuffle(names)
    return round_robin_balance(names, k)


def greedy_partition(netlist: Netlist, k: int, seed: int = 7) -> Dict[str, int]:
    adj = netlist.adjacency()
    names = list(netlist.cell_names)
    rng = random.Random(seed)
    rng.shuffle(names)
    names.sort(key=lambda name: sum(adj[name].values()), reverse=True)
    max_size = math.ceil(len(names) / k) if k else len(names)
    parts: Dict[str, int] = {}
    sizes = [0] * k

    for name in names:
        best_part = 0
        best_score: Optional[Tuple[int, int, int]] = None
        for part in range(k):
            if sizes[part] >= max_size:
                continue
            affinity = sum(weight for nb, weight in adj[name].items() if parts.get(nb) == part)
            score = (affinity, -sizes[part], -part)
            if best_score is None or score > best_score:
                best_score = score
                best_part = part
        parts[name] = best_part
        sizes[best_part] += 1
    return parts


def cut_cost(netlist: Netlist, parts: Dict[str, int]) -> int:
    cost = 0
    for cells in netlist.net_to_cells().values():
        touched = {parts[cell] for cell in cells if cell in parts}
        if len(touched) > 1:
            cost += len(touched) - 1
    return cost


def fm_partition(netlist: Netlist, k: int, seed: int = 7, passes: int = 6) -> Dict[str, int]:
    parts = greedy_partition(netlist, k, seed)
    names = list(netlist.cell_names)
    if not names:
        return parts

    min_size = len(names) // k
    max_size = math.ceil(len(names) / k)

    def can_move(cell: str, dst: int) -> bool:
        counts = collections.Counter(parts.values())
        src = parts[cell]
        return src != dst and counts[src] - 1 >= min_size and counts[dst] + 1 <= max_size

    current = cut_cost(netlist, parts)
    for _ in range(passes):
        improved = False
        for cell in names:
            src = parts[cell]
            best_dst = src
            best_cost = current
            for dst in range(k):
                if not can_move(cell, dst):
                    continue
                parts[cell] = dst
                trial = cut_cost(netlist, parts)
                if trial < best_cost:
                    best_cost = trial
                    best_dst = dst
                parts[cell] = src
            if best_dst != src:
                parts[cell] = best_dst
                current = best_cost
                improved = True
        if not improved:
            break
    return parts


def bfs_order(netlist: Netlist) -> List[str]:
    adj = netlist.adjacency()
    remaining = set(netlist.cell_names)
    order: List[str] = []
    while remaining:
        start = max(remaining, key=lambda name: (sum(adj[name].values()), name))
        queue = collections.deque([start])
        remaining.remove(start)
        while queue:
            node = queue.popleft()
            order.append(node)
            neighbors = sorted(
                (nb for nb in adj[node] if nb in remaining),
                key=lambda nb: (-adj[node][nb], nb),
            )
            for nb in neighbors:
                remaining.remove(nb)
                queue.append(nb)
    return order


def multilevel_bfs_partition(netlist: Netlist, k: int, seed: int = 7) -> Dict[str, int]:
    """Explainable spectral/multilevel proxy.

    A real multilevel or spectral partitioner coarsens dense regions, orders the
    coarse graph, then refines. For a lightweight demo, weighted BFS gives a
    locality-preserving ordering; slicing that order into balanced bands mimics
    spectral bisection, and a few FM passes provide refinement.
    """

    order = bfs_order(netlist)
    if not order:
        return {}
    parts: Dict[str, int] = {}
    for i, name in enumerate(order):
        part = min(k - 1, int(i * k / len(order)))
        parts[name] = part

    # One local refinement phase, initialized from the BFS bands.
    current = cut_cost(netlist, parts)
    max_size = math.ceil(len(order) / k)
    min_size = len(order) // k
    for _ in range(4):
        changed = False
        for cell in order:
            src = parts[cell]
            counts = collections.Counter(parts.values())
            best = (current, src)
            for dst in range(k):
                if dst == src or counts[src] - 1 < min_size or counts[dst] + 1 > max_size:
                    continue
                parts[cell] = dst
                trial = cut_cost(netlist, parts)
                if trial < best[0]:
                    best = (trial, dst)
                parts[cell] = src
            if best[1] != src:
                parts[cell] = best[1]
                current = best[0]
                changed = True
        if not changed:
            break
    return parts


def cut_nets(netlist: Netlist, parts: Dict[str, int]) -> List[str]:
    result = []
    for net, cells in netlist.net_to_cells().items():
        touched = {parts[cell] for cell in cells if cell in parts}
        if len(touched) > 1:
            result.append(net)
    return sorted(result)


def estimate_metrics(netlist: Netlist, parts: Dict[str, int], k: int) -> Dict[str, object]:
    counts = collections.Counter(parts.values())
    sizes = [counts.get(i, 0) for i in range(k)]
    total = sum(sizes)
    largest = max(sizes) if sizes else 0
    ideal = total / k if k else total
    imbalance = (largest / ideal) if ideal else 0.0
    cuts = cut_nets(netlist, parts)
    serial_fraction = min(0.95, 0.05 + 0.03 * len(cuts))
    balance_penalty = max(1.0, imbalance)
    speedup = k / (1.0 + serial_fraction * (k - 1) + (balance_penalty - 1.0))
    return {
        "cells": total,
        "sizes": sizes,
        "cut_nets": cuts,
        "cut_count": len(cuts),
        "cut_cost": cut_cost(netlist, parts),
        "imbalance": imbalance,
        "estimated_speedup": speedup,
    }


def partition_groups(parts: Dict[str, int]) -> Dict[int, List[str]]:
    grouped: Dict[int, List[str]] = collections.defaultdict(list)
    for cell, part in sorted(parts.items()):
        grouped[part].append(cell)
    return dict(sorted(grouped.items()))


def format_partition(parts: Dict[str, int]) -> str:
    grouped = partition_groups(parts)
    return ", ".join(f"P{part}=[{', '.join(cells)}]" for part, cells in sorted(grouped.items()))


def write_outputs(
    out_dir: str,
    netlist: Netlist,
    algo: str,
    parts: Dict[str, int],
    metrics: Dict[str, object],
    elapsed_ms: float,
) -> None:
    algo_dir = os.path.join(out_dir, algo)
    os.makedirs(algo_dir, exist_ok=True)

    summary = {
        "module": netlist.module,
        "algorithm": algo,
        "cells": metrics["cells"],
        "nets": len(netlist.net_to_cells()),
        "sizes": metrics["sizes"],
        "cut_nets": metrics["cut_nets"],
        "cut_count": metrics["cut_count"],
        "lambda_minus_one": metrics["cut_cost"],
        "imbalance": metrics["imbalance"],
        "runtime_ms": elapsed_ms,
        "estimated_speedup": metrics["estimated_speedup"],
    }
    with open(os.path.join(algo_dir, "metrics.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    with open(os.path.join(algo_dir, "partitions.tsv"), "w", encoding="utf-8") as handle:
        handle.write("cell\tpartition\n")
        for cell, part in sorted(parts.items()):
            handle.write(f"{cell}\t{part}\n")

    cell_by_name = {cell.name: cell for cell in netlist.cells}
    cut_set = set(metrics["cut_nets"])
    for part, cells in partition_groups(parts).items():
        sub_path = os.path.join(algo_dir, f"partition_{part}.v")
        local_nets = sorted(
            net
            for net, touched in netlist.net_to_cells().items()
            if any(parts.get(cell) == part for cell in touched)
        )
        with open(sub_path, "w", encoding="utf-8") as handle:
            handle.write(f"// Auto-generated demo sub-netlist for partition {part}\n")
            handle.write(f"// Boundary/cut nets: {', '.join(sorted(cut_set & set(local_nets))) or '-'}\n")
            handle.write(f"module {netlist.module}_{algo}_p{part}();\n")
            if local_nets:
                handle.write("  wire " + ", ".join(local_nets) + ";\n")
            for cell_name in cells:
                cell = cell_by_name[cell_name]
                pins = ", ".join(f".{pin}({net})" for pin, net in sorted(cell.pins.items()))
                handle.write(f"  {cell.kind} {cell.name} ({pins});\n")
            handle.write("endmodule\n")


def run_algorithm(netlist: Netlist, algo: str, k: int, seed: int) -> Dict[str, int]:
    if k < 1:
        raise ValueError("k must be >= 1")
    if not netlist.cells:
        return {}
    k = min(k, len(netlist.cells))
    if algo == "random":
        return random_partition(netlist, k, seed)
    if algo == "greedy":
        return greedy_partition(netlist, k, seed)
    if algo == "fm":
        return fm_partition(netlist, k, seed)
    if algo == "multilevel":
        return multilevel_bfs_partition(netlist, k, seed)
    raise ValueError(f"unknown algorithm: {algo}")


def print_report(
    netlist: Netlist,
    algo: str,
    parts: Dict[str, int],
    k: int,
    elapsed_ms: float,
) -> Dict[str, object]:
    effective_k = min(k, max(1, len(netlist.cells)))
    metrics = estimate_metrics(netlist, parts, effective_k)
    print(f"\n[{algo}]")
    print(f"partition: {format_partition(parts)}")
    print(f"part sizes: {metrics['sizes']}  imbalance: {metrics['imbalance']:.2f}x")
    print(f"cut nets ({metrics['cut_count']}): {', '.join(metrics['cut_nets']) or '-'}")
    print(f"cut cost: {metrics['cut_cost']}")
    print(f"runtime: {elapsed_ms:.3f} ms")
    print(f"estimated parallel speedup: {metrics['estimated_speedup']:.2f}x on k={effective_k}")
    return metrics


def available_algorithms(choice: str) -> List[str]:
    algos = ["random", "greedy", "fm", "multilevel"]
    return algos if choice == "all" else [choice]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Compare lightweight netlist partitioning algorithms.")
    parser.add_argument("--input", required=True, help="Simplified Verilog netlist path")
    parser.add_argument("--k", type=int, default=2, help="number of partitions")
    parser.add_argument(
        "--algo",
        choices=["all", "random", "greedy", "fm", "multilevel"],
        default="all",
        help="partitioning algorithm to run",
    )
    parser.add_argument("--seed", type=int, default=7, help="random seed for reproducible baselines")
    parser.add_argument("--out", help="optional output directory for metrics, partitions, and sub-netlists")
    args = parser.parse_args(argv)

    netlist = load_netlist(args.input)
    print(f"module: {netlist.module}")
    print(f"ports: {len(netlist.inputs)} inputs, {len(netlist.outputs)} outputs")
    print(f"cells: {len(netlist.cells)}  nets: {len(netlist.net_to_cells())}")

    for algo in available_algorithms(args.algo):
        started = time.perf_counter()
        parts = run_algorithm(netlist, algo, args.k, args.seed)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        metrics = print_report(netlist, algo, parts, args.k, elapsed_ms)
        if args.out:
            write_outputs(args.out, netlist, algo, parts, metrics, elapsed_ms)
    if args.out:
        print(f"\nwrote output directory: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
