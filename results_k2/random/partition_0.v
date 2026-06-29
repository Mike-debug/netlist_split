// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n1, n2, n4, n7, n8, q1, q2, q4
module demo_top_random_p0();
  wire c, clk, d, n1, n2, n3, n4, n7, n8, q1, q2, q3, q4, y, z;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  INV u_inv0 (.A(n3), .Y(n4));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
