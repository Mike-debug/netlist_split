// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: n2, n3, n8, q1, q2, q3
module demo_top_openroad_tritonpart_p2();
  wire a, b, n1, n2, n3, n8, q1, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
