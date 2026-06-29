// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: n5, n7, q2, q4
module demo_top_greedy_p2();
  wire f, n5, n6, n7, q2, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
