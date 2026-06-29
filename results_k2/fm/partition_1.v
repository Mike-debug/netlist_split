// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: n2, n4, n5, n6, n7, q1, q2, q4
module demo_top_fm_p1();
  wire a, b, c, d, e, f, n1, n2, n3, n4, n5, n6, n7, q1, q2, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  INV u_inv0 (.A(n3), .Y(n4));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
