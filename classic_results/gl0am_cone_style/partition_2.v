// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: clk, n4, n7, n8, q1
module demo_top_gl0am_cone_style_p2();
  wire clk, n4, n7, n8, q1, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
endmodule
