// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: n2, n5, n7, n8, q1, q2, q3
module demo_top_circuit_gnn_style_p0();
  wire c, d, f, n2, n5, n6, n7, n8, q1, q2, q3;
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
