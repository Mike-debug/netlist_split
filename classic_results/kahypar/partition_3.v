// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: n7, q1, q2
module demo_top_kahypar_p3();
  wire e, f, n5, n6, n7, q1, q2;
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
