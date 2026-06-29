import unittest

import netlist_split_demo as demo


SAMPLE = """
module tiny(input a, input b, input c, output y);
wire n1, n2;
AND2 u0 (.A(a), .B(b), .Y(n1));
INV u1 (.A(n1), .Y(n2));
assign y = n2 & c;
endmodule
"""


class NetlistSplitDemoTest(unittest.TestCase):
    def test_parse_cells_and_nets(self):
        netlist = demo.parse_verilog(SAMPLE)
        self.assertEqual(netlist.module, "tiny")
        self.assertEqual(netlist.inputs, {"a", "b", "c"})
        self.assertEqual(netlist.outputs, {"y"})
        self.assertEqual(len(netlist.cells), 3)
        self.assertIn("n1", netlist.net_to_cells())
        self.assertEqual(netlist.cells[0].pins["Y"], "n1")

    def test_algorithms_return_balanced_complete_partitions(self):
        netlist = demo.parse_verilog(SAMPLE)
        for algo in ["random", "greedy", "fm", "multilevel"]:
            with self.subTest(algo=algo):
                parts = demo.run_algorithm(netlist, algo, k=2, seed=1)
                self.assertEqual(set(parts), set(netlist.cell_names))
                metrics = demo.estimate_metrics(netlist, parts, k=2)
                self.assertEqual(sum(metrics["sizes"]), len(netlist.cells))
                self.assertGreaterEqual(metrics["cut_count"], 0)
                self.assertGreater(metrics["estimated_speedup"], 0)

    def test_cli_algorithms_list(self):
        self.assertEqual(demo.available_algorithms("all"), ["random", "greedy", "fm", "multilevel"])
        self.assertEqual(demo.available_algorithms("fm"), ["fm"])


if __name__ == "__main__":
    unittest.main()
