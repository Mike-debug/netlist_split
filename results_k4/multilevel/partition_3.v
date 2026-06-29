// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: n2, n3
module demo_top_multilevel_p3();
  wire a, b, c, d, n1, n2, n3;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
