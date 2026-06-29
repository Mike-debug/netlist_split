// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n5, n7, n8, q2
module demo_top_multilevel_p1();
  wire clk, f, n5, n6, n7, n8, q2, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
