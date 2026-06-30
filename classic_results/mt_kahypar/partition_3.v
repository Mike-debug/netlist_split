// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: n2, n4
module demo_top_mt_kahypar_p3();
  wire a, b, n1, n2, n3, n4;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  INV u_inv0 (.A(n3), .Y(n4));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
endmodule
