// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: n2, n4, n7, n8, q1, q2, q3, q4
module demo_top_kahypar_p0();
  wire clk, n2, n4, n7, n8, q1, q2, q3, q4;
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
endmodule
