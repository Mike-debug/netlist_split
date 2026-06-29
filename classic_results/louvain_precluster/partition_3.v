// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: clk, n4, n5, n7, q1, q4
module demo_top_louvain_precluster_p3();
  wire clk, e, n4, n5, n7, q1, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
endmodule
