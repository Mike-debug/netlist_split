import os
import json
import shutil
import tempfile
import unittest

import classic_partition_demo as classic
import netlist_split_demo as base


class ClassicPartitionDemoTest(unittest.TestCase):
    def setUp(self):
        self.netlist = base.load_netlist("sample_netlist.v")
        self.tmpdir = tempfile.mkdtemp(prefix="classic_partition_test_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def assert_metrics_match_partitions(self, backend):
        backend_dir = os.path.join(self.tmpdir, backend)
        metrics_path = os.path.join(backend_dir, "metrics.json")
        partitions_path = os.path.join(backend_dir, "partitions.tsv")
        self.assertTrue(os.path.exists(metrics_path), metrics_path)
        self.assertTrue(os.path.exists(partitions_path), partitions_path)
        with open(metrics_path, "r", encoding="utf-8") as handle:
            metrics = json.load(handle)
        parts = {}
        with open(partitions_path, "r", encoding="utf-8") as handle:
            next(handle)
            for line in handle:
                cell, part = line.rstrip("\n").split("\t")
                parts[cell] = int(part)
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        recomputed = base.estimate_metrics(self.netlist, parts, max(parts.values()) + 1)
        self.assertEqual(metrics["cut_count"], recomputed["cut_count"], "cut_count")
        self.assertEqual(metrics["lambda_minus_one"], recomputed["cut_cost"], "lambda_minus_one")
        self.assertEqual(metrics["sizes"], recomputed["sizes"], "sizes")
        self.assertAlmostEqual(metrics["imbalance"], recomputed["imbalance"])

    def test_hmetis_export(self):
        files = classic.write_hmetis_files(self.tmpdir, self.netlist)
        for path in files.values():
            self.assertTrue(os.path.exists(path), path)
        with open(files["hgr"], "r", encoding="utf-8") as handle:
            header = handle.readline().strip().split()
        self.assertEqual(int(header[1]), len(self.netlist.cells))

    def test_metis_graph_export(self):
        graph_path = classic.write_metis_graph(self.tmpdir, self.netlist)
        self.assertTrue(os.path.exists(graph_path), graph_path)
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "cells.tsv")))
        with open(graph_path, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        header = lines[0].strip().split()
        self.assertEqual(int(header[0]), len(self.netlist.cells))
        self.assertEqual(header[2], "001")
        self.assertEqual(len(lines) - 1, len(self.netlist.cells))

    def test_metis_if_available(self):
        if not classic.find_metis_exe():
            self.skipTest("gpmetis CLI is not available")
        parts, metrics = classic.run_metis(self.netlist, 4, self.tmpdir, seed=7)
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        self.assertEqual(metrics["tool"], "METIS gpmetis")
        self.assertTrue(os.path.exists(metrics["solution_file"]))
        self.assert_metrics_match_partitions("metis")

    def test_mtkahypar_if_available(self):
        if not classic.find_mtkahypar_exe():
            self.skipTest("MtKaHyPar CLI is not available")
        parts, metrics = classic.run_mtkahypar(
            self.netlist,
            4,
            self.tmpdir,
            seed=7,
            epsilon=0.03,
            objective="km1",
            threads=2,
        )
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        self.assertEqual(metrics["tool"], "Mt-KaHyPar CLI")
        self.assertTrue(os.path.exists(metrics["solution_file"]))
        self.assert_metrics_match_partitions("mt_kahypar")

    def test_patoh_if_available(self):
        if not classic.find_patoh_exe():
            self.skipTest("PaToH CLI is not available")
        parts, metrics = classic.run_patoh(self.netlist, 4, self.tmpdir, objective="km1")
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        self.assertEqual(metrics["tool"], "PaToH standalone CLI")
        self.assertTrue(os.path.exists(metrics["solution_file"]))
        self.assert_metrics_match_partitions("patoh")

    def test_cli_run_status_records_external_tool_successes(self):
        if not (classic.find_metis_exe() and classic.find_mtkahypar_exe() and classic.find_patoh_exe()):
            self.skipTest("METIS, Mt-KaHyPar, and PaToH CLIs are not all available")
        rc = classic.main(
            [
                "--input",
                "sample_netlist.v",
                "--k",
                "4",
                "--backend",
                "all",
                "--out",
                self.tmpdir,
                "--gnn-epochs",
                "2",
            ]
        )
        self.assertEqual(rc, 0)
        with open(os.path.join(self.tmpdir, "run_status.json"), "r", encoding="utf-8") as handle:
            status = json.load(handle)
        for key in ("metis", "mtkahypar", "patoh"):
            self.assertEqual(status[key]["run_status"], "executed", key)
            self.assertIn("metrics", status[key])
            self.assertIn("solution_file", status[key]["metrics"])

    def test_gl0am_cone_style_partition(self):
        parts, metrics = classic.run_gl0am_cones(self.netlist, 4, self.tmpdir)
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        self.assertGreaterEqual(metrics["cut_count"], 0)
        self.assertTrue(os.path.exists(os.path.join(self.tmpdir, "gl0am_cone_style", "metrics.json")))

    def test_kahypar_if_available(self):
        try:
            classic.ensure_local_python_tools()
            __import__("kahypar")
        except Exception:
            self.skipTest("KaHyPar Python binding is not available")
        parts, metrics = classic.run_kahypar(self.netlist, 4, self.tmpdir, seed=7, epsilon=0.03, objective="km1")
        self.assertEqual(set(parts), set(self.netlist.cell_names))
        self.assertEqual(metrics["tool"], "KaHyPar Python binding")

if __name__ == "__main__":
    unittest.main()
