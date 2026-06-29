// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: n2, n4, n5, n6, n7, q1, q2, q4
module demo_top_greedy_p0();
  wire clk, n2, n4, n5, n6, n7, n8, q1, q2, q3, q4, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
