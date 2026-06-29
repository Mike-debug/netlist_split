// Auto-generated demo sub-netlist for partition 3
// Boundary/cut nets: clk, n1, n2, n3, n4, q2
module demo_top_circuit_gnn_style_p3();
  wire a, b, clk, n1, n2, n3, n4, q2;
  AND2 u_and0 (.A(a), .B(b), .Y(n1));
  DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));
  INV u_inv0 (.A(n3), .Y(n4));
endmodule
