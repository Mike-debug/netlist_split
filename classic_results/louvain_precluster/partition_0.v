// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n5, n6, n7, q1, q3, q4
module demo_top_louvain_precluster_p0();
  wire clk, n5, n6, n7, n8, q1, q3, q4;
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
