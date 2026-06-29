// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n2, n7, q2, q3
module demo_top_multilevel_p0();
  wire clk, n2, n7, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
endmodule
