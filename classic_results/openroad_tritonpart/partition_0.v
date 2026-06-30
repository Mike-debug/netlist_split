// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n2, n3, n7, q1, q3
module demo_top_openroad_tritonpart_p0();
  wire c, clk, d, n2, n3, n4, n7, q1, q3;
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  INV u_inv0 (.A(n3), .Y(n4));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
