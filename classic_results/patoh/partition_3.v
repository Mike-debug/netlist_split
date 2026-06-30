// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: n5, n7, q2, q3
module demo_top_patoh_p3();
  wire f, n5, n6, n7, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
