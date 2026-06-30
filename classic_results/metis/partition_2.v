// Auto-generated demo sub-netlist for partition 2
// Boundary/cut nets: clk, n2, n6, q3
module demo_top_metis_p2();
  wire clk, f, n2, n6, q2, q3, z;
  ASSIGN assign_2 (.A1(q2), .A2(q3), .Y(z));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
endmodule
