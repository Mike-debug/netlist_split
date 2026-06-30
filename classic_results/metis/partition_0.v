// Auto-generated demo sub-netlist for partition 0
// Boundary/cut nets: clk, n4, n5, n8, q3
module demo_top_metis_p0();
  wire clk, e, n4, n5, n8, q1, q3;
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
  XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
endmodule
