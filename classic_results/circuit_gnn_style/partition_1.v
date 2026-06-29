// Auto-generated demo sub-netlist for partition 1
// Boundary/cut nets: clk, n1, n2, n3, n5, n7, q1, q3, q4
module demo_top_circuit_gnn_style_p1();
  wire clk, e, n1, n2, n3, n5, n7, q1, q3, q4, y;
  ASSIGN assign_1 (.A1(q4), .A2(n7), .Y(y));
  AND2 u_and1 (.A(q1), .B(e), .Y(n5));
  DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
  NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
endmodule
