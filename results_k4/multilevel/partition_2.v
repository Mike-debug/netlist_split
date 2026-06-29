// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: clk, n3, n5, n8, q3
module demo_top_multilevel_p2();
  wire clk, e, n3, n4, n5, n8, q1, q3;
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  INV u_inv0 (.A(n3), .Y(n4));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
