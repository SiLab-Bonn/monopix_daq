/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University 
 * ------------------------------------------------------------
 */

`timescale 1ps / 1ps


`include "utils/bus_to_ip.v"
 
`include "gpio/gpio.v"

`include "pulse_gen/pulse_gen.v"
`include "pulse_gen/pulse_gen_core.v"
   
`include "bram_fifo/bram_fifo_core.v"
`include "bram_fifo/bram_fifo.v"
//TODO fix me!
`include "/home/user/workspace/monopix/monopix_daq/firmware/src/mono_data_rx/mono_data_rx.v"
`include "/home/user/workspace/monopix/monopix_daq/firmware/src/mono_data_rx/mono_data_rx_core.v"

`include "utils/cdc_syncfifo.v"
`include "utils/generic_fifo.v"
`include "utils/cdc_pulse_sync.v"
`include "utils/CG_MOD_pos.v"
`include "utils/clock_divider.v"
`include "utils/cdc_reset_sync.v"

`include "utils/RAMB16_S1_S9_sim.v"

module tb (
    input wire          BUS_CLK,
    input wire          BUS_RST,
    input wire  [31:0]  BUS_ADD,
    inout wire  [31:0]  BUS_DATA,
    input wire          BUS_RD,
    input wire          BUS_WR,
    output wire         BUS_BYTE_ACCESS
);
    
    // MODULE ADREESSES //
    localparam GPIO_BASEADDR = 32'h0000;
    localparam GPIO_HIGHADDR = 32'h1000-1;
    
    localparam BASEADDR = 32'h1000; //0x1000
    localparam HIGHADDR = 32'h2000-1;   //0x300f
    
    
    localparam PULSE_BASEADDR = 32'h3000;
    localparam PULSE_HIGHADDR = PULSE_BASEADDR + 15;

    localparam PULSE_READ_BASEADDR = 32'h4000;
    localparam PULSE_READ_HIGHADDR = PULSE_READ_BASEADDR + 15;
    
    localparam FIFO_BASEADDR = 32'h8000;
    localparam FIFO_HIGHADDR = 32'h9000-1;
    
    localparam FIFO_BASEADDR_DATA = 32'h8000_0000;
    localparam FIFO_HIGHADDR_DATA = 32'h9000_0000;
    
    localparam ABUSWIDTH = 32;
    assign BUS_BYTE_ACCESS = BUS_ADD < 32'h8000_0000 ? 1'b1 : 1'b0;
    
    // MODULES //

    wire SPI_CLK;
    wire [63:0] TIMESTAMP;
    wire [3:0] IO;
    gpio
    #(
        .BASEADDR(GPIO_BASEADDR),
        .HIGHADDR(GPIO_HIGHADDR),
        .ABUSWIDTH(ABUSWIDTH),
        .IO_WIDTH(64),
        .IO_DIRECTION(64'hF)
    ) i_gpio
    (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA[7:0]),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
        .IO({TIMESTAMP[63:4],IO})
    );

    reg [63:0] curr_timestamp;
    always@(posedge SPI_CLK) begin
    if(BUS_RST) // TODO sync reset
        curr_timestamp <= 0;
    else
        curr_timestamp <= curr_timestamp + 1;
    end
    assign TIMESTAMP = curr_timestamp;
    
    
    wire PULSE;
    pulse_gen
    #(
        .BASEADDR(PULSE_BASEADDR),
        .HIGHADDR(PULSE_HIGHADDR),
        .ABUSWIDTH(ABUSWIDTH)
    ) i_pulse_gen
    (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA[7:0]),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
    
        .PULSE_CLK(SPI_CLK),
        .EXT_START(IO[0]),
        .PULSE(PULSE)
    );
    
    wire PULSE_READ;
    pulse_gen
    #(
        .BASEADDR(PULSE_READ_BASEADDR),
        .HIGHADDR(PULSE_READ_HIGHADDR),
        .ABUSWIDTH(ABUSWIDTH)
    ) i_pulse_gen_read
    (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA[7:0]),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
    
        .PULSE_CLK(SPI_CLK),
        .EXT_START(IO[0]),
        .PULSE(PULSE_READ)
    );
    
    clock_divider #(
    .DIVISOR(4) 
    ) i_clock_divisor_spi (
        .CLK(BUS_CLK),
        .RESET(1'b0),
        .CE(),
        .CLOCK(SPI_CLK)
    ); 
    
    wire DATA_LVDS;
    assign DATA_LVDS = 1'b1;
    
    reg TOKEN;
    assign TOKEN = PULSE;
    
    wire FIFO_READ, FIFO_EMPTY;
    assign FIFO_READ = ~PULSE_READ;
    wire [31:0] FIFO_DATA;
    mono_data_rx #(
       .BASEADDR(BASEADDR),
       .HIGHADDR(HIGHADDR),
       .IDENTYFIER(2'b00)
    ) mono_data_rx (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
        
        .CLK_BX(SPI_CLK),
        .RX_TOKEN(TOKEN), 
        .RX_DATA(DATA_LVDS), 
        .RX_CLK(SPI_CLK),
        .RX_READ(), 
        .RX_FREEZE(), 
        .TIMESTAMP(TIMESTAMP),
        
        .FIFO_READ(FIFO_READ),
        .FIFO_EMPTY(FIFO_EMPTY),
        .FIFO_DATA(FIFO_DATA),
        
        .LOST_ERROR()
        
    ); 



    bram_fifo
    #(
        .BASEADDR(FIFO_BASEADDR),
        .HIGHADDR(FIFO_HIGHADDR),
        .BASEADDR_DATA(FIFO_BASEADDR_DATA),
        .HIGHADDR_DATA(FIFO_HIGHADDR_DATA),
        .ABUSWIDTH(ABUSWIDTH)
    ) i_out_fifo (
        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR),
        
        .FIFO_READ_NEXT_OUT(),
        .FIFO_EMPTY_IN(FIFO_EMPTY),
        .FIFO_DATA(FIFO_DATA),
        
        .FIFO_NOT_EMPTY(),
        .FIFO_FULL(),
        .FIFO_NEAR_FULL(),
        .FIFO_READ_ERROR()
    );
    
    initial begin
        $dumpfile("/tmp/data_rx.vcd");
        $dumpvars(0);
    end
    
endmodule
