/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University 
 * ------------------------------------------------------------
 */

`timescale 1ps / 1ps

`include "tests/hdl/monopix.sv"
`include "firmware/src/monopix_mio.v"
 
module tb (
    input wire FCLK_IN, 

    //full speed 
    inout wire [7:0] BUS_DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FD,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE
);

wire [19:0] SRAM_A;
wire [15:0] SRAM_IO;
wire SRAM_BHE_B;
wire SRAM_BLE_B;
wire SRAM_CE1_B;
wire SRAM_OE_B;
wire SRAM_WE_B;

wire SOUT, SIN, LDPIX, CKCONF, LDDAC, SR_EN, RESET, INJECTION;
wire MONITOR;
wire [2:0] LEMO_RX;
assign LEMO_RX = 0;

wire CLK_BX; 
wire READ;
wire FREEZE;
wire nRST;
wire EN_TEST_PATTERN;
wire RST_GRAY;
wire EN_DRIVER;
wire EN_DATA_CMOS;
wire CLK_OUT;
wire TOKEN;
wire DATA;
    
monopix_mio fpga (
    .FCLK_IN(FCLK_IN),
        
    .BUS_DATA(BUS_DATA), 
    .ADD(ADD), 
    .RD_B(RD_B), 
    .WR_B(WR_B), 
    .FDATA(FD), 
    .FREAD(FREAD), 
    .FSTROBE(FSTROBE), 
    .FMODE(FMODE),

    .SRAM_A(SRAM_A), 
    .SRAM_IO(SRAM_IO), 
    .SRAM_BHE_B(SRAM_BHE_B), 
    .SRAM_BLE_B(SRAM_BLE_B), 
    .SRAM_CE1_B(SRAM_CE1_B), 
    .SRAM_OE_B(SRAM_OE_B), 
    .SRAM_WE_B(SRAM_WE_B),
    
    
    .LEMO_RX(LEMO_RX),
    
    .SR_OUT(SOUT),   
    .SR_IN(SIN),
    .LDPIX(LDPIX),
    .CKCONF(CKCONF),  
    .LDDAC(LDDAC),  
	.SR_EN(SR_EN),
    .RESET(RESET),
    .INJECTION(INJECTION),
    .MONITOR(MONITOR),
    
    .CLK_BX(CLK_BX), 
    .READ(READ),
    .FREEZE(FREEZE),
    .nRST(nRST),
    .EN_TEST_PATTERN(EN_TEST_PATTERN),
    .RST_GRAY(RST_GRAY),
    .EN_DRIVER(EN_DRIVER),
    .EN_DATA_CMOS(EN_DATA_CMOS),
    .CLK_OUT(CLK_OUT),
    .TOKEN(TOKEN),
    .DATA(DATA),
    .DATA_LVDS(DATA)
    
);   

//SRAM Model
reg [15:0] sram [1048576-1:0];
assign SRAM_IO = !SRAM_OE_B ? sram[SRAM_A] : 16'hzzzz;
always@(negedge SRAM_WE_B)
    sram[SRAM_A] <= SRAM_IO;

logic [0:4643] ANA_HIT;
assign ANA_HIT = 0;

monopix dut(
    .ANA_HIT(ANA_HIT),
    .Injection(!INJECTION),
    .Monitor(MONITOR),
    
    .Clk_BX(CLK_BX), 
    .READ(READ),
    .FREEZE(FREEZE),
    .nRST(nRST),
    .EN_Test_Pattern(EN_TEST_PATTERN),
    .RST_Gray(RST_GRAY),
    .EN_Driver(EN_DRIVER),
    .EN_Data_CMOS(EN_DATA_CMOS),
    .Clk_Out(CLK_OUT),
    .Token_Out(TOKEN),
    .Data_Out(DATA),
    
    .Clk_Conf(CKCONF),
    .SR_In(SIN),
    .LdDAC(LDDAC),
    .SR_EN(SR_EN),
    .SR_RST(RESET),
    .LdPix(LDPIX),
    .SR_out(SOUT)
    );

initial begin
    $dumpfile("/tmp/monopix.vcd.gz");
    $dumpvars(1);
end

endmodule
