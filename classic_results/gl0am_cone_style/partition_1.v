// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n1, n2, n3, n5, n7, q1, q2, q3
module demo_top_gl0am_cone_style_p1();
  wire clk, e, n1, n2, n3, n5, n7, q1, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
endmodule
