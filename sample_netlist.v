module demo_top (
    input clk,
    input rst_n,
    input a,
    input b,
    input c,
    input d,
    input e,
    input f,
    output y,
    output z
);

wire n1, n2, n3, n4, n5, n6, n7, n8;
wire q1, q2, q3, q4;

AND2 u_and0 (.A(a), .B(b), .Y(n1));
OR2  u_or0  (.A(c), .B(d), .Y(n2));
NAND2 u_nand0 (.A(n1), .B(n2), .Y(n3));
INV  u_inv0 (.A(n3), .Y(n4));

DFF u_ff0 (.CLK(clk), .D(n4), .Q(q1));
DFF u_ff1 (.CLK(clk), .D(n2), .Q(q2));

AND2 u_and1 (.A(q1), .B(e), .Y(n5));
NOR2 u_nor0 (.A(q2), .B(f), .Y(n6));
OR2  u_or1  (.A(n5), .B(n6), .Y(n7));

DFF u_ff2 (.CLK(clk), .D(n7), .Q(q3));
XOR2 u_xor0 (.A(q3), .B(q1), .Y(n8));
DFF u_ff3 (.CLK(clk), .D(n8), .Q(q4));

assign y = q4 & n7;
assign z = q2 | q3;

endmodule
