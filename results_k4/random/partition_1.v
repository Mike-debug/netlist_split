// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n1, n2, n4, n8, q1, q2, q4
module demo_top_random_p1();
  wire a, b, clk, n1, n2, n4, n8, q1, q2, q4;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
endmodule
