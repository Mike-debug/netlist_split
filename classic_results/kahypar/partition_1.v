// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: n7, n8, q1, q2, q3, q4
module demo_top_kahypar_p1();
  wire n7, n8, q1, q2, q3, q4, y, z;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
