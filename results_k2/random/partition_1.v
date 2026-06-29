// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n1, n2, n4, n7, n8, q1, q2, q4
module demo_top_random_p1();
  wire a, b, clk, e, f, n1, n2, n4, n5, n6, n7, n8, q1, q2, q4;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
  OR2 u_or1 (.A(n5), .B(n6), .Y(n7));
endmodule
