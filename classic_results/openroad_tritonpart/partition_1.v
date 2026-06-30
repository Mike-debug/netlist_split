// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n2, n6, n7, q1, q2, q4
module demo_top_openroad_tritonpart_p1();
  wire clk, e, n2, n5, n6, n7, q1, q2, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
