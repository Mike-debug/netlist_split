// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n5, n6, n8, q3
module demo_top_metis_p1();
  wire clk, n5, n6, n7, n8, q3, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
