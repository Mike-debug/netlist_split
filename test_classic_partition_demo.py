import os
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

    def test_hmetis_export(self):
        files = classic.write_hmetis_files(self.tmpdir, self.netlist)
        for path in files.values():
            self.assertTrue(os.path.exists(path), path)
        with open(files["hgr"], "r", encoding="utf-8") as handle:
            header = handle.readline().strip().split()
        self.assertEqual(int(header[1]), len(self.netlist.cells))

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
