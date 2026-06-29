// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: n5, n8, q1, q2, q3
module demo_top_greedy_p1();
  wire e, n5, n8, q1, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
