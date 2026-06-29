// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: clk, n4, n8, q1, q2, q3, q4
module demo_top_circuit_gnn_style_p2();
  wire clk, n4, n8, q1, q2, q3, q4, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
endmodule
