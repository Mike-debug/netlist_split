#!/usr/bin/env python3
"""Tool-backed and literature-backed netlist partitioning demo.

This script complements ``netlist_split_demo.py``.  The original script is a
lightweight educational baseline.  This one targets the tools mentioned in the
research plan:

* KaHyPar: real Python binding invocation when available.
* OpenROAD/TritonPart: hMETIS hypergraph export + runnable Tcl script.
* METIS: graph projection + real gpmetis invocation when available.
* Mt-KaHyPar: real shared-memory hypergraph partitioner CLI invocation.
* PaToH: real PaToH standalone CLI invocation when the binary is available.
* CircuitPartitioning-GNN: a compact PyTorch GCN-style partitioning demo.
* GL0AM: cone/block partitioning inspired by GL0AM's logic-cone grouping.

The OpenROAD/TritonPart path is generated even when OpenROAD is not installed,
so the demo remains useful on a lightweight workstation.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import netlist_split_demo as base


DRIVER_PINS = {"Y", "Z", "ZN", "Q", "QN", "O", "OUT"}


@dataclass
class HypergraphData:
    cell_names: List[str]
    hyperedges: List[Tuple[str, List[int]]]


def local_tooling_path() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tooling", "python")


def repo_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def ensure_local_python_tools() -> None:
    path = local_tooling_path()
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


def build_hypergraph_data(netlist: base.Netlist) -> HypergraphData:
    cell_names = netlist.cell_names
    cell_to_id = {name: i for i, name in enumerate(cell_names)}
    hyperedges: List[Tuple[str, List[int]]] = []
    for net, cells in sorted(netlist.net_to_cells().items()):
        pins = sorted(cell_to_id[cell] for cell in cells if cell in cell_to_id)
        if len(pins) >= 2:
            hyperedges.append((net, pins))
    return HypergraphData(cell_names=cell_names, hyperedges=hyperedges)


def write_hmetis_files(out_dir: str, netlist: base.Netlist) -> Dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    hg = build_hypergraph_data(netlist)
    hgr_path = os.path.join(out_dir, f"{netlist.module}.hgr")
    cells_path = os.path.join(out_dir, "cells.tsv")
    nets_path = os.path.join(out_dir, "nets.tsv")

    with open(hgr_path, "w", encoding="utf-8") as handle:
        handle.write(f"{len(hg.hyperedges)} {len(hg.cell_names)}\n")
        for _, pins in hg.hyperedges:
            handle.write(" ".join(str(pin + 1) for pin in pins) + "\n")

    with open(cells_path, "w", encoding="utf-8") as handle:
        handle.write("vertex_id\tcell\n")
        for i, name in enumerate(hg.cell_names, start=1):
            handle.write(f"{i}\t{name}\n")

    with open(nets_path, "w", encoding="utf-8") as handle:
        handle.write("hyperedge_id\tnet\tvertices\n")
        for i, (net, pins) in enumerate(hg.hyperedges, start=1):
            vertices = ",".join(str(pin + 1) for pin in pins)
            handle.write(f"{i}\t{net}\t{vertices}\n")

    return {"hgr": hgr_path, "cells": cells_path, "nets": nets_path}


def write_partition_artifacts(
    out_dir: str,
    netlist: base.Netlist,
    backend: str,
    parts: Dict[str, int],
    elapsed_ms: float,
    extra: Optional[Dict[str, object]] = None,
) -> Dict[str, object]:
    k = max(parts.values(), default=0) + 1
    metrics = base.estimate_metrics(netlist, parts, k)
    base.write_outputs(out_dir, netlist, backend, parts, metrics, elapsed_ms)
    metrics_path = os.path.join(out_dir, backend, "metrics.json")
    with open(metrics_path, "r", encoding="utf-8") as handle:
        merged = json.load(handle)
    if extra:
        merged.update(extra)
    with open(metrics_path, "w", encoding="utf-8") as handle:
        json.dump(merged, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return merged


def run_kahypar(
    netlist: base.Netlist,
    k: int,
    out_dir: str,
    seed: int,
    epsilon: float,
    objective: str,
) -> Tuple[Dict[str, int], Dict[str, object]]:
    ensure_local_python_tools()
    import kahypar  # type: ignore

    hg = build_hypergraph_data(netlist)
    indices = [0]
    flat: List[int] = []
    edge_weights: List[int] = []
    for net, pins in hg.hyperedges:
        flat.extend(pins)
        indices.append(len(flat))
        # A small timing-ish hook: clock/reset nets get higher cut penalty.
        edge_weights.append(10 if net.lower() in {"clk", "clock", "rst", "rst_n", "reset"} else 1)

    if not hg.cell_names:
        return {}, {}

    node_weights = [1] * len(hg.cell_names)
    effective_k = min(k, len(hg.cell_names))
    config_name = "km1_kKaHyPar_sea20.ini" if objective == "km1" else "cut_kKaHyPar_sea20.ini"
    config_path = os.path.join("classic_configs", config_name)

    hypergraph = kahypar.Hypergraph(
        len(hg.cell_names),
        len(hg.hyperedges),
        indices,
        flat,
        effective_k,
        edge_weights,
        node_weights,
    )
    context = kahypar.Context()
    context.loadINIconfiguration(config_path)
    context.setK(effective_k)
    context.setEpsilon(epsilon)
    context.setSeed(seed)
    context.suppressOutput(True)

    started = time.perf_counter()
    kahypar.partition(hypergraph, context)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    parts = {name: int(hypergraph.blockID(i)) for i, name in enumerate(hg.cell_names)}
    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "kahypar",
        parts,
        elapsed_ms,
        {
            "tool": "KaHyPar Python binding",
            "objective": objective,
            "kahypar_cut": int(kahypar.cut(hypergraph)),
            "kahypar_lambda_minus_one": int(kahypar.connectivityMinusOne(hypergraph)),
            "epsilon": epsilon,
            "config": config_path,
        },
    )
    return parts, metrics


def write_openroad_tritonpart_demo(
    netlist: base.Netlist,
    k: int,
    out_dir: str,
    run_openroad: bool,
) -> Dict[str, object]:
    backend_dir = os.path.join(out_dir, "openroad_tritonpart")
    os.makedirs(backend_dir, exist_ok=True)
    files = write_hmetis_files(backend_dir, netlist)
    solution_file = os.path.join(backend_dir, f"{netlist.module}.hgr.part.{k}")
    tcl_path = os.path.join(backend_dir, "run_tritonpart_hypergraph.tcl")
    with open(tcl_path, "w", encoding="utf-8") as handle:
        handle.write("# Auto-generated OpenROAD Partition Manager / TritonPart demo\n")
        handle.write(f"set num_parts {k}\n")
        handle.write("set balance_constraint 2\n")
        handle.write("set seed 7\n")
        handle.write(f"set hypergraph_file \"{files['hgr']}\"\n")
        handle.write(f"set solution_file \"{solution_file}\"\n")
        handle.write("triton_part_hypergraph -hypergraph_file $hypergraph_file \\\n")
        handle.write("  -num_parts $num_parts -balance_constraint $balance_constraint \\\n")
        handle.write("  -seed $seed\n")
        handle.write("evaluate_hypergraph_solution -num_parts $num_parts \\\n")
        handle.write("  -balance_constraint $balance_constraint \\\n")
        handle.write("  -hypergraph_file $hypergraph_file -solution_file $solution_file\n")

    openroad_exe = find_openroad_exe()
    openroad_env = build_openroad_env()

    status: Dict[str, object] = {
        "tool": "OpenROAD Partition Manager / TritonPart",
        "mode": "script-generated",
        "run_status": "not_requested",
        "available": bool(openroad_exe),
        "openroad_exe": openroad_exe,
        "hgr": files["hgr"],
        "tcl": tcl_path,
        "solution_file": solution_file,
    }
    if run_openroad and openroad_exe:
        status["run_status"] = "executed"
        started = time.perf_counter()
        proc = subprocess.run(
            [openroad_exe, "-exit", tcl_path],
            cwd=os.getcwd(),
            env=openroad_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        status["runtime_ms"] = elapsed_ms
        status["returncode"] = proc.returncode
        status["log"] = proc.stdout[-4000:]
        with open(os.path.join(backend_dir, "openroad_run.log"), "w", encoding="utf-8") as handle:
            handle.write(proc.stdout)
        if os.path.exists(solution_file):
            parts = read_openroad_solution(solution_file, netlist.cell_names)
            metrics = write_partition_artifacts(
                out_dir,
                netlist,
                "openroad_tritonpart",
                parts,
                elapsed_ms,
                {
                    "tool": "OpenROAD Partition Manager / TritonPart",
                    "openroad_exe": openroad_exe,
                    "solution_file": os.path.abspath(solution_file),
                    "openroad_version": get_openroad_version(openroad_exe, openroad_env),
                    "note": "Metrics are computed from the OpenROAD-generated .hgr.part.k solution file.",
                },
            )
            status["metrics"] = metrics
    elif run_openroad:
        status["run_status"] = "skipped"
        status["skipped_reason"] = "openroad executable not found"

    with open(os.path.join(backend_dir, "status.json"), "w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return status


def find_openroad_exe() -> Optional[str]:
    env_exe = os.environ.get("OPENROAD_EXE")
    if env_exe and os.path.exists(env_exe):
        return env_exe
    path_exe = shutil.which("openroad")
    if path_exe:
        return path_exe
    local_exe = os.path.join(os.getcwd(), ".tooling", "openroad_extracted", "usr", "bin", "openroad")
    if os.path.exists(local_exe):
        return local_exe
    return None


def build_openroad_env() -> Dict[str, str]:
    env = os.environ.copy()
    candidates = [
        os.path.join(os.getcwd(), ".tooling", "openroad_extracted", "opt", "or-tools", "lib"),
        os.path.join(os.getcwd(), ".tooling", "openroad_deps_extract", "usr", "lib", "x86_64-linux-gnu"),
        os.path.join(os.getcwd(), ".tooling", "openroad_runtime_libs"),
    ]
    existing = [path for path in candidates if os.path.isdir(path)]
    old = env.get("LD_LIBRARY_PATH")
    env["LD_LIBRARY_PATH"] = ":".join(existing + ([old] if old else []))
    return env


def get_openroad_version(openroad_exe: str, env: Dict[str, str]) -> str:
    try:
        proc = subprocess.run(
            [openroad_exe, "-version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env=env,
        )
        return proc.stdout.strip()
    except Exception as exc:
        return f"unknown: {exc}"


def read_openroad_solution(solution_file: str, cell_names: Sequence[str]) -> Dict[str, int]:
    with open(solution_file, "r", encoding="utf-8") as handle:
        values = [int(line.strip()) for line in handle if line.strip()]
    if len(values) != len(cell_names):
        raise ValueError(f"solution has {len(values)} assignments, expected {len(cell_names)}")
    return {name: values[i] for i, name in enumerate(cell_names)}


def find_metis_exe() -> Optional[str]:
    env_exe = os.environ.get("GPMETIS_EXE") or os.environ.get("GPMETIS")
    if env_exe and os.path.exists(env_exe):
        return env_exe
    path_exe = shutil.which("gpmetis")
    if path_exe:
        return path_exe
    local_exe = os.path.join(repo_root(), ".tooling", "metis_extracted", "usr", "bin", "gpmetis")
    if os.path.exists(local_exe):
        return local_exe
    return None


def build_metis_env() -> Dict[str, str]:
    env = os.environ.copy()
    candidates = [
        os.path.join(repo_root(), ".tooling", "metis_extracted", "usr", "lib", "x86_64-linux-gnu"),
        os.path.join(repo_root(), ".tooling", "metis_extracted", "usr", "lib"),
    ]
    existing = [path for path in candidates if os.path.isdir(path)]
    old = env.get("LD_LIBRARY_PATH")
    if existing or old:
        env["LD_LIBRARY_PATH"] = ":".join(existing + ([old] if old else []))
    return env


def write_metis_graph(out_dir: str, netlist: base.Netlist) -> str:
    os.makedirs(out_dir, exist_ok=True)
    names = netlist.cell_names
    n = len(names)
    weights: Dict[Tuple[int, int], int] = {}
    for left, right, weight in graph_edges(netlist):
        key = (min(left, right), max(left, right))
        weights[key] = weights.get(key, 0) + int(weight)

    graph_path = os.path.join(out_dir, f"{netlist.module}.graph")
    cells_path = os.path.join(out_dir, "cells.tsv")
    adjacency: List[List[Tuple[int, int]]] = [[] for _ in range(n)]
    for (left, right), weight in sorted(weights.items()):
        adjacency[left].append((right, weight))
        adjacency[right].append((left, weight))

    with open(graph_path, "w", encoding="utf-8") as handle:
        handle.write(f"{n} {len(weights)} 001\n")
        for neighbors in adjacency:
            tokens: List[str] = []
            for neighbor, weight in sorted(neighbors):
                tokens.extend([str(neighbor + 1), str(weight)])
            handle.write(" ".join(tokens) + "\n")
    with open(cells_path, "w", encoding="utf-8") as handle:
        handle.write("vertex_id\tcell\n")
        for i, name in enumerate(names, start=1):
            handle.write(f"{i}\t{name}\n")
    return graph_path


def read_metis_solution(solution_file: str, cell_names: Sequence[str]) -> Dict[str, int]:
    with open(solution_file, "r", encoding="utf-8") as handle:
        values = [int(line.strip()) for line in handle if line.strip()]
    if len(values) != len(cell_names):
        raise ValueError(f"gpmetis solution has {len(values)} assignments, expected {len(cell_names)}")
    return {name: values[i] for i, name in enumerate(cell_names)}


def read_partition_vector(solution_file: str, cell_names: Sequence[str], tool_name: str) -> Dict[str, int]:
    with open(solution_file, "r", encoding="utf-8") as handle:
        values = [int(line.strip()) for line in handle if line.strip()]
    if len(values) != len(cell_names):
        raise ValueError(f"{tool_name} solution has {len(values)} assignments, expected {len(cell_names)}")
    return {name: values[i] for i, name in enumerate(cell_names)}


def run_metis(netlist: base.Netlist, k: int, out_dir: str, seed: int) -> Tuple[Dict[str, int], Dict[str, object]]:
    if not netlist.cells:
        return {}, {}
    backend_dir = os.path.join(out_dir, "metis")
    graph_path = os.path.abspath(write_metis_graph(backend_dir, netlist))
    gpmetis = find_metis_exe()
    if not gpmetis:
        raise RuntimeError("gpmetis executable not found on PATH, GPMETIS_EXE, or .tooling/metis_extracted")

    effective_k = min(k, len(netlist.cells))
    if effective_k < 1:
        raise ValueError("k must be >= 1")
    solution_file = f"{graph_path}.part.{effective_k}"
    if os.path.exists(solution_file):
        os.remove(solution_file)

    command = [gpmetis, "-ptype=rb", f"-seed={seed}", graph_path, str(effective_k)]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=backend_dir,
        env=build_metis_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    with open(os.path.join(backend_dir, "gpmetis.log"), "w", encoding="utf-8") as handle:
        handle.write(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"gpmetis failed with exit code {proc.returncode}; see {backend_dir}/gpmetis.log")
    if not os.path.exists(solution_file):
        raise FileNotFoundError(f"gpmetis did not produce expected solution file: {solution_file}")

    parts = read_metis_solution(solution_file, netlist.cell_names)
    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "metis",
        parts,
        elapsed_ms,
        {
            "tool": "METIS gpmetis",
            "gpmetis_exe": gpmetis,
            "graph_file": graph_path,
            "solution_file": solution_file,
            "command": command,
            "ptype": "rb",
            "log_tail": proc.stdout[-2000:],
            "note": "Hyperedges are projected to a weighted cell-cell graph before running METIS.",
        },
    )
    return parts, metrics


def find_mtkahypar_exe() -> Optional[str]:
    env_exe = os.environ.get("MTKAHYPAR_EXE") or os.environ.get("MT_KAHYPAR_EXE")
    if env_exe and os.path.exists(env_exe):
        return env_exe
    for name in ("MtKaHyPar", "mt-kahypar"):
        path_exe = shutil.which(name)
        if path_exe:
            return path_exe
    local_exe = os.path.join(
        repo_root(),
        ".tooling",
        "src",
        "mt-kahypar",
        "build_gcc13",
        "mt-kahypar",
        "application",
        "MtKaHyPar",
    )
    if os.path.exists(local_exe):
        return local_exe
    return None


def build_mtkahypar_env() -> Dict[str, str]:
    env = os.environ.copy()
    candidates = [
        os.path.join(repo_root(), ".tooling", "src", "mt-kahypar", "build_gcc13", "gnu_13.3_cxx11_64_release"),
        os.path.join(repo_root(), ".tooling", "src", "mt-kahypar", "build_gcc13", "lib"),
    ]
    existing = [path for path in candidates if os.path.isdir(path)]
    old = env.get("LD_LIBRARY_PATH")
    if existing or old:
        env["LD_LIBRARY_PATH"] = ":".join(existing + ([old] if old else []))
    return env


def run_mtkahypar(
    netlist: base.Netlist,
    k: int,
    out_dir: str,
    seed: int,
    epsilon: float,
    objective: str,
    threads: int,
) -> Tuple[Dict[str, int], Dict[str, object]]:
    if not netlist.cells:
        return {}, {}
    backend_dir = os.path.join(out_dir, "mt_kahypar")
    files = write_hmetis_files(backend_dir, netlist)
    hgr_path = os.path.abspath(files["hgr"])
    mtkahypar = find_mtkahypar_exe()
    if not mtkahypar:
        raise RuntimeError("MtKaHyPar executable not found on PATH, MTKAHYPAR_EXE, or .tooling/src/mt-kahypar")

    effective_k = min(k, len(netlist.cells))
    for filename in os.listdir(backend_dir):
        if filename.startswith(os.path.basename(hgr_path) + ".part"):
            os.remove(os.path.join(backend_dir, filename))

    command = [
        mtkahypar,
        "-h",
        hgr_path,
        "-k",
        str(effective_k),
        "-e",
        str(epsilon),
        "-o",
        objective,
        "--preset-type=default",
        "-t",
        str(max(1, threads)),
        "--seed",
        str(seed),
        "--write-partition-file",
        f"--partition-output-folder={os.path.abspath(backend_dir)}",
    ]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=backend_dir,
        env=build_mtkahypar_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    log_path = os.path.join(backend_dir, "mtkahypar.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"MtKaHyPar failed with exit code {proc.returncode}; see {log_path}")

    solution_candidates = [
        os.path.join(backend_dir, filename)
        for filename in os.listdir(backend_dir)
        if filename.startswith(os.path.basename(hgr_path) + ".part")
    ]
    if not solution_candidates:
        raise FileNotFoundError(f"MtKaHyPar did not produce a partition file in {backend_dir}")
    solution_file = os.path.abspath(sorted(solution_candidates)[-1])

    parts = read_partition_vector(solution_file, netlist.cell_names, "MtKaHyPar")
    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "mt_kahypar",
        parts,
        elapsed_ms,
        {
            "tool": "Mt-KaHyPar CLI",
            "mtkahypar_exe": mtkahypar,
            "hgr": hgr_path,
            "solution_file": solution_file,
            "command": command,
            "objective": objective,
            "epsilon": epsilon,
            "threads": max(1, threads),
            "log_tail": proc.stdout[-2000:],
        },
    )
    return parts, metrics


def find_patoh_exe() -> Optional[str]:
    env_exe = os.environ.get("PATOH_EXE") or os.environ.get("PATOH")
    if env_exe and os.path.exists(env_exe):
        return env_exe
    path_exe = shutil.which("patoh")
    if path_exe:
        return path_exe
    local_exe = os.path.join(repo_root(), ".tooling", "patoh_extracted", "build", "Linux-x86_64", "patoh")
    if os.path.exists(local_exe):
        return local_exe
    return None


def write_patoh_hypergraph(out_dir: str, netlist: base.Netlist) -> str:
    os.makedirs(out_dir, exist_ok=True)
    hg = build_hypergraph_data(netlist)
    u_path = os.path.join(out_dir, f"{netlist.module}.u")
    pin_count = sum(len(pins) for _, pins in hg.hyperedges)
    with open(u_path, "w", encoding="utf-8") as handle:
        handle.write(f"1 {len(hg.cell_names)} {len(hg.hyperedges)} {pin_count}\n")
        for _, pins in hg.hyperedges:
            handle.write(" ".join(str(pin + 1) for pin in pins) + "\n")
    with open(os.path.join(out_dir, "cells.tsv"), "w", encoding="utf-8") as handle:
        handle.write("vertex_id\tcell\n")
        for i, name in enumerate(hg.cell_names, start=1):
            handle.write(f"{i}\t{name}\n")
    return u_path


def run_patoh(
    netlist: base.Netlist,
    k: int,
    out_dir: str,
    objective: str,
) -> Tuple[Dict[str, int], Dict[str, object]]:
    if not netlist.cells:
        return {}, {}
    backend_dir = os.path.join(out_dir, "patoh")
    u_path = os.path.abspath(write_patoh_hypergraph(backend_dir, netlist))
    patoh = find_patoh_exe()
    if not patoh:
        raise RuntimeError("PaToH executable not found on PATH, PATOH_EXE, or .tooling/patoh_extracted")

    effective_k = min(k, len(netlist.cells))
    solution_file = f"{u_path}.part.{effective_k}"
    if os.path.exists(solution_file):
        os.remove(solution_file)
    metric_option = "UM=O" if objective == "km1" else "UM=U"
    command = [patoh, u_path, str(effective_k), metric_option, "PQ=D", "WI=1"]
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=backend_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    log_path = os.path.join(backend_dir, "patoh.log")
    with open(log_path, "w", encoding="utf-8") as handle:
        handle.write(proc.stdout)
    if proc.returncode != 0:
        raise RuntimeError(f"PaToH failed with exit code {proc.returncode}; see {log_path}")
    if not os.path.exists(solution_file):
        raise FileNotFoundError(f"PaToH did not produce expected solution file: {solution_file}")

    parts = read_partition_vector(solution_file, netlist.cell_names, "PaToH")
    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "patoh",
        parts,
        elapsed_ms,
        {
            "tool": "PaToH standalone CLI",
            "patoh_exe": patoh,
            "patoh_file": u_path,
            "solution_file": solution_file,
            "command": command,
            "objective": "connectivity-1" if objective == "km1" else "net-cut",
            "license_note": "Official PaToH binary is free for non-commercial research use; commercial use requires a license.",
            "log_tail": proc.stdout[-2000:],
        },
    )
    return parts, metrics


def graph_edges(netlist: base.Netlist) -> List[Tuple[int, int, float]]:
    names = netlist.cell_names
    cell_to_id = {name: i for i, name in enumerate(names)}
    edges: Dict[Tuple[int, int], float] = {}
    for cells in netlist.net_to_cells().values():
        ids = sorted(cell_to_id[cell] for cell in cells if cell in cell_to_id)
        for i, left in enumerate(ids):
            for right in ids[i + 1 :]:
                key = (left, right)
                edges[key] = edges.get(key, 0.0) + 1.0
    return [(left, right, weight) for (left, right), weight in sorted(edges.items())]


def repair_balance(parts: Dict[str, int], k: int) -> Dict[str, int]:
    names = sorted(parts)
    min_size = len(names) // k
    max_size = math.ceil(len(names) / k)
    counts = collections.Counter(parts.values())
    while any(counts[p] > max_size for p in range(k)) or any(counts[p] < min_size for p in range(k)):
        src = max(range(k), key=lambda p: counts[p])
        dst = min(range(k), key=lambda p: counts[p])
        if counts[src] <= max_size and counts[dst] >= min_size:
            break
        for name in names:
            if parts[name] == src:
                parts[name] = dst
                counts[src] -= 1
                counts[dst] += 1
                break
    return parts


def run_gnn_partition(netlist: base.Netlist, k: int, out_dir: str, seed: int, epochs: int) -> Tuple[Dict[str, int], Dict[str, object]]:
    import torch
    import torch.nn.functional as functional

    torch.manual_seed(seed)
    names = netlist.cell_names
    n = len(names)
    effective_k = min(k, max(1, n))
    if n == 0:
        return {}, {}

    edges = graph_edges(netlist)
    adjacency = torch.eye(n)
    for left, right, weight in edges:
        adjacency[left, right] += weight
        adjacency[right, left] += weight
    degree = adjacency.sum(dim=1)
    norm = torch.diag(torch.pow(degree.clamp_min(1.0), -0.5))
    adjacency_norm = norm @ adjacency @ norm

    max_degree = float(max(degree).item()) if n else 1.0
    features = []
    for cell in netlist.cells:
        is_seq = 1.0 if cell.kind.upper().startswith("DFF") else 0.0
        features.append([float(degree[names.index(cell.name)].item()) / max_degree, is_seq, 1.0])
    x = torch.tensor(features, dtype=torch.float32)

    w1 = torch.nn.Parameter(torch.randn((x.shape[1], 16)) * 0.1)
    w2 = torch.nn.Parameter(torch.randn((16, effective_k)) * 0.1)
    optimizer = torch.optim.Adam([w1, w2], lr=0.08)

    edge_index = torch.tensor([(l, r) for l, r, _ in edges], dtype=torch.long)
    edge_weight = torch.tensor([w for _, _, w in edges], dtype=torch.float32)

    started = time.perf_counter()
    final_loss = 0.0
    for _ in range(epochs):
        hidden = torch.relu(adjacency_norm @ x @ w1)
        logits = adjacency_norm @ hidden @ w2
        prob = functional.softmax(logits, dim=1)
        balance = ((prob.mean(dim=0) - (1.0 / effective_k)) ** 2).sum()
        if len(edges):
            same = (prob[edge_index[:, 0]] * prob[edge_index[:, 1]]).sum(dim=1)
            cut_loss = (edge_weight * (1.0 - same)).sum() / edge_weight.sum()
        else:
            cut_loss = torch.tensor(0.0)
        entropy = -(prob * torch.log(prob.clamp_min(1e-8))).sum(dim=1).mean()
        loss = cut_loss + 5.0 * balance + 0.02 * entropy
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        final_loss = float(loss.detach().item())
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    with torch.no_grad():
        hidden = torch.relu(adjacency_norm @ x @ w1)
        logits = adjacency_norm @ hidden @ w2
        assignment = functional.softmax(logits, dim=1).argmax(dim=1).tolist()

    parts = repair_balance({name: int(assignment[i]) for i, name in enumerate(names)}, effective_k)
    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "circuit_gnn_style",
        parts,
        elapsed_ms,
        {
            "tool": "PyTorch GCN-style reproduction of CircuitPartitioning-GNN idea",
            "epochs": epochs,
            "final_loss": final_loss,
            "note": "Uses graph neural message passing and differentiable cut/balance loss; not the upstream repository code.",
        },
    )
    return parts, metrics


def net_drivers(netlist: base.Netlist) -> Dict[str, str]:
    drivers: Dict[str, str] = {}
    for cell in netlist.cells:
        for pin, net in cell.pins.items():
            if pin.upper() in DRIVER_PINS and not base.is_constant(net):
                drivers[net] = cell.name
    return drivers


def fanin_cone(root_net: str, drivers: Dict[str, str], cells: Dict[str, base.Cell], seen: Optional[Set[str]] = None) -> Set[str]:
    seen = seen or set()
    driver = drivers.get(root_net)
    if not driver or driver in seen:
        return set()
    seen.add(driver)
    cone = {driver}
    for pin, net in cells[driver].pins.items():
        if pin.upper() not in DRIVER_PINS and not base.is_constant(net):
            cone.update(fanin_cone(net, drivers, cells, seen))
    return cone


def run_gl0am_cones(netlist: base.Netlist, k: int, out_dir: str) -> Tuple[Dict[str, int], Dict[str, object]]:
    cells = {cell.name: cell for cell in netlist.cells}
    drivers = net_drivers(netlist)
    roots: List[Tuple[str, str]] = []
    for cell in netlist.cells:
        if cell.kind.upper().startswith("DFF"):
            data_net = cell.pins.get("D")
            if data_net:
                roots.append((cell.name, data_net))
    for output in sorted(netlist.outputs):
        roots.append((f"output:{output}", output))

    cones: List[Tuple[str, Set[str]]] = []
    for root_name, root_net in roots:
        cone = fanin_cone(root_net, drivers, cells)
        if cone:
            cones.append((root_name, cone))

    effective_k = min(k, max(1, len(netlist.cells)))
    part_loads = [0] * effective_k
    parts: Dict[str, int] = {}
    started = time.perf_counter()
    for _, cone in sorted(cones, key=lambda item: (-len(item[1]), item[0])):
        dst = min(range(effective_k), key=lambda p: part_loads[p])
        for cell in sorted(cone):
            if cell not in parts:
                parts[cell] = dst
                part_loads[dst] += 1

    # Sequential elements and any overlap leftovers are assigned after cone packing.
    for cell in sorted(netlist.cell_names):
        if cell not in parts:
            dst = min(range(effective_k), key=lambda p: part_loads[p])
            parts[cell] = dst
            part_loads[dst] += 1
    parts = repair_balance(parts, effective_k)
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "gl0am_cone_style",
        parts,
        elapsed_ms,
        {
            "tool": "GL0AM-inspired logic-cone block partitioning",
            "cones": [{"root": root, "cells": sorted(cone)} for root, cone in cones],
            "note": "GL0AM itself is a GPU simulator; this reproduces the logic-cone grouping strategy described by the project.",
        },
    )
    return parts, metrics


def run_networkx_louvain(netlist: base.Netlist, k: int, out_dir: str, seed: int) -> Tuple[Dict[str, int], Dict[str, object]]:
    import networkx as nx

    graph = nx.Graph()
    for name in netlist.cell_names:
        graph.add_node(name)
    for left, right, weight in graph_edges(netlist):
        graph.add_edge(netlist.cell_names[left], netlist.cell_names[right], weight=weight)

    started = time.perf_counter()
    communities = nx.algorithms.community.louvain_communities(graph, seed=seed, weight="weight")
    ordered = sorted([sorted(comm) for comm in communities], key=lambda c: (-len(c), c[0] if c else ""))
    parts: Dict[str, int] = {}
    loads = [0] * min(k, max(1, len(netlist.cells)))
    for comm in ordered:
        dst = min(range(len(loads)), key=lambda p: loads[p])
        for cell in comm:
            parts[cell] = dst
            loads[dst] += 1
    parts = repair_balance(parts, len(loads))
    elapsed_ms = (time.perf_counter() - started) * 1000.0

    metrics = write_partition_artifacts(
        out_dir,
        netlist,
        "louvain_precluster",
        parts,
        elapsed_ms,
        {
            "tool": "NetworkX Louvain community pre-clustering",
            "communities": ordered,
            "note": "Included as a community-detection baseline often used before constrained partitioning.",
        },
    )
    return parts, metrics


def print_metric_row(name: str, metrics: Dict[str, object]) -> None:
    if not metrics:
        print(f"{name:24s} skipped")
        return
    print(
        f"{name:24s} cut={metrics.get('cut_count')} "
        f"lambda-1={metrics.get('lambda_minus_one')} "
        f"sizes={metrics.get('sizes')} "
        f"imb={float(metrics.get('imbalance', 0.0)):.2f} "
        f"runtime_ms={float(metrics.get('runtime_ms', 0.0)):.3f}"
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run demos for researched netlist partitioning tools/algorithms.")
    parser.add_argument("--input", required=True, help="simplified Verilog netlist path")
    parser.add_argument("--k", type=int, default=4, help="number of partitions")
    parser.add_argument("--out", default="classic_results", help="output directory")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--epsilon", type=float, default=0.03, help="KaHyPar imbalance tolerance")
    parser.add_argument("--objective", choices=["km1", "cut"], default="km1", help="KaHyPar objective")
    parser.add_argument("--mtkahypar-threads", type=int, default=2, help="Mt-KaHyPar worker threads")
    parser.add_argument("--gnn-epochs", type=int, default=250)
    parser.add_argument("--run-openroad", action="store_true", help="run generated Tcl if openroad exists")
    parser.add_argument(
        "--backend",
        choices=[
            "all",
            "kahypar",
            "openroad",
            "metis",
            "gpmetis",
            "mtkahypar",
            "mt_kahypar",
            "patoh",
            "gnn",
            "gl0am",
            "louvain",
        ],
        default="all",
    )
    args = parser.parse_args(argv)

    netlist = base.load_netlist(args.input)
    os.makedirs(args.out, exist_ok=True)
    write_hmetis_files(args.out, netlist)

    status = {
        "input": args.input,
        "module": netlist.module,
        "cells": len(netlist.cells),
        "nets": len(netlist.net_to_cells()),
        "requested_k": args.k,
        "tools": {
            "kahypar_python": False,
            "openroad": bool(find_openroad_exe()),
            "gpmetis": bool(find_metis_exe()),
            "mtkahypar": bool(find_mtkahypar_exe()),
            "patoh": bool(find_patoh_exe()),
            "torch": False,
            "networkx": False,
        },
    }

    print(f"module={netlist.module} cells={len(netlist.cells)} nets={len(netlist.net_to_cells())} k={args.k}")

    if args.backend in {"all", "kahypar"}:
        try:
            ensure_local_python_tools()
            import kahypar  # noqa: F401

            status["tools"]["kahypar_python"] = True
            _, metrics = run_kahypar(netlist, args.k, args.out, args.seed, args.epsilon, args.objective)
            print_metric_row("KaHyPar(real)", metrics)
        except Exception as exc:
            status["kahypar_error"] = repr(exc)
            print(f"KaHyPar(real) skipped: {exc}")

    if args.backend in {"all", "openroad"}:
        openroad_status = write_openroad_tritonpart_demo(netlist, args.k, args.out, args.run_openroad)
        status["openroad_tritonpart"] = openroad_status
        print(f"OpenROAD/TritonPart script: {openroad_status['tcl']} available={openroad_status['available']}")

    if args.backend in {"all", "metis", "gpmetis"}:
        try:
            _, metrics = run_metis(netlist, args.k, args.out, args.seed)
            status["metis"] = {"run_status": "executed", "metrics": metrics}
            print_metric_row("METIS(gpmetis)", metrics)
        except Exception as exc:
            status["metis_error"] = repr(exc)
            print(f"METIS(gpmetis) skipped: {exc}")

    if args.backend in {"all", "mtkahypar", "mt_kahypar"}:
        try:
            _, metrics = run_mtkahypar(
                netlist,
                args.k,
                args.out,
                args.seed,
                args.epsilon,
                args.objective,
                args.mtkahypar_threads,
            )
            status["mtkahypar"] = {"run_status": "executed", "metrics": metrics}
            print_metric_row("Mt-KaHyPar(real)", metrics)
        except Exception as exc:
            status["mtkahypar_error"] = repr(exc)
            print(f"Mt-KaHyPar(real) skipped: {exc}")

    if args.backend in {"all", "patoh"}:
        try:
            _, metrics = run_patoh(netlist, args.k, args.out, args.objective)
            status["patoh"] = {"run_status": "executed", "metrics": metrics}
            print_metric_row("PaToH(real)", metrics)
        except Exception as exc:
            status["patoh_error"] = repr(exc)
            print(f"PaToH(real) skipped: {exc}")

    if args.backend in {"all", "gnn"}:
        try:
            import torch  # noqa: F401

            status["tools"]["torch"] = True
            _, metrics = run_gnn_partition(netlist, args.k, args.out, args.seed, args.gnn_epochs)
            print_metric_row("CircuitGNN-style", metrics)
        except Exception as exc:
            status["gnn_error"] = repr(exc)
            print(f"CircuitGNN-style skipped: {exc}")

    if args.backend in {"all", "gl0am"}:
        _, metrics = run_gl0am_cones(netlist, args.k, args.out)
        print_metric_row("GL0AM-cone-style", metrics)

    if args.backend in {"all", "louvain"}:
        try:
            import networkx  # noqa: F401

            status["tools"]["networkx"] = True
            _, metrics = run_networkx_louvain(netlist, args.k, args.out, args.seed)
            print_metric_row("Louvain-precluster", metrics)
        except Exception as exc:
            status["louvain_error"] = repr(exc)
            print(f"Louvain-precluster skipped: {exc}")

    with open(os.path.join(args.out, "run_status.json"), "w", encoding="utf-8") as handle:
        json.dump(status, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(f"wrote output directory: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
