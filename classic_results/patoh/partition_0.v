// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: n2, n4
module demo_top_patoh_p0();
  wire a, b, c, d, n1, n2, n3, n4;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  INV u_inv0 (.A(n3), .Y(n4));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
