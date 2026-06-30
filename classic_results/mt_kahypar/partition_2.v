// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: clk, n2, n4, n5, q1, q2
module demo_top_mt_kahypar_p2();
  wire c, clk, d, e, n2, n4, n5, q1, q2;
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  OR2 u_or0 (.A(c), .B(d), .Y(n2));
endmodule
