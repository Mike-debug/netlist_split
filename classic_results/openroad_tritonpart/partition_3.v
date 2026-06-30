// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: clk, n6, n8, q2, q4
module demo_top_openroad_tritonpart_p3();
  wire clk, f, n6, n8, q2, q4;
  DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
endmodule
