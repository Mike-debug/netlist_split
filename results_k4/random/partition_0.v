// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n1, n2, n4, n7, q3
module demo_top_random_p0();
  wire c, clk, d, n1, n2, n3, n4, n7, q3;
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  INV u_inv0 (.A(n3), .Y(n4));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
