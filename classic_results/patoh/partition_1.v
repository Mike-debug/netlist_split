// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n2, n4, n5, q1, q2
module demo_top_patoh_p1();
  wire clk, e, n2, n4, n5, q1, q2;
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
endmodule
