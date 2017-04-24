/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps
`default_nettype none

module bin_to_gray7 (
    input wire [7:0] gray_input,
    output reg [7:0] bin_out
);

always@(*) begin
    bin_out[7] <= gray_input[7];
    bin_out[6] <= bin_out[7] ^ gray_input[6];
    bin_out[5] <= bin_out[6] ^ gray_input[5];
    bin_out[4] <= bin_out[5] ^ gray_input[4];
    bin_out[3] <= bin_out[4] ^ gray_input[3];
    bin_out[2] <= bin_out[3] ^ gray_input[2];
    bin_out[1] <= bin_out[2] ^ gray_input[1];
    bin_out[0] <= bin_out[1] ^ gray_input[0];
end

endmodule

module mono_data_rx_core
#(
    parameter ABUSWIDTH = 16,
    parameter IDENTYFIER = 0
)(
    input wire CLK_BX,
    input wire RX_TOKEN, RX_DATA, RX_CLK,
    output reg RX_READ, RX_FREEZE,  
    
    input wire FIFO_READ,
    output wire FIFO_EMPTY,
    output wire [31:0] FIFO_DATA,

    input wire BUS_CLK,
    input wire [ABUSWIDTH-1:0] BUS_ADD,
    input wire [7:0] BUS_DATA_IN,
    output reg [7:0] BUS_DATA_OUT,
    input wire BUS_RST,
    input wire BUS_WR,
    input wire BUS_RD,

    output wire LOST_ERROR
);

localparam VERSION = 1;

wire SOFT_RST;
assign SOFT_RST = (BUS_ADD==0 && BUS_WR);

wire RST;
assign RST = BUS_RST | SOFT_RST;

reg CONF_EN;
reg CONF_DISSABLE_GRAY_DEC;

always @(posedge BUS_CLK) begin
    if(RST) begin
        CONF_EN <= 0;
        CONF_DISSABLE_GRAY_DEC <= 0;
    end
    else if(BUS_WR) begin
        if(BUS_ADD == 2)
            CONF_EN <= BUS_DATA_IN[0];
            CONF_DISSABLE_GRAY_DEC <= BUS_DATA_IN[1];
    end
end

reg [7:0] LOST_DATA_CNT;

always @(posedge BUS_CLK) begin
    if(BUS_RD) begin
        if(BUS_ADD == 0)
            BUS_DATA_OUT <= VERSION;
        else if(BUS_ADD == 2)
            BUS_DATA_OUT <= {6'b0, CONF_DISSABLE_GRAY_DEC, CONF_EN};
        else if(BUS_ADD == 3)
            BUS_DATA_OUT <= LOST_DATA_CNT;
        else
            BUS_DATA_OUT <= 8'b0;
    end
end

wire RST_SYNC;
wire RST_SOFT_SYNC;
cdc_reset_sync rst_pulse_sync (.clk_in(BUS_CLK), .pulse_in(RST), .clk_out(RX_CLK), .pulse_out(RST_SOFT_SYNC));
assign RST_SYNC = RST_SOFT_SYNC;

wire CONF_EN_SYNC;
assign CONF_EN_SYNC  = CONF_EN;

//
parameter NOP  = 4'b0001, TOKEN_WAIT = 4'b0010, READ_STATE = 4'b0100, DATA = 4'b1000;
reg [3:0] state, next_state;

always@(posedge CLK_BX)
 if(RST_SYNC)
     state <= NOP;
  else
     state <= next_state;
     
reg [7:0] DelayCnt;

always@(*) begin : set_next_state
    next_state = state; //default
    case (state)
        NOP:
            if(RX_TOKEN & CONF_EN)
                next_state = TOKEN_WAIT;   
        TOKEN_WAIT: 
            if(DelayCnt == 2)
                next_state = READ_STATE;
        READ_STATE:
            if(DelayCnt == 10) ///1)
                next_state = DATA;  
        DATA: 
            if(DelayCnt == 32) //2)
                next_state = NOP;
    endcase
end
     
always@(posedge CLK_BX)
if(RST_SYNC || state == NOP )
    DelayCnt <= 0;
else if(DelayCnt != 8'hff)
    DelayCnt <= DelayCnt + 1;

always@(posedge CLK_BX)
    RX_READ <= (state == READ_STATE); 

always@(posedge CLK_BX)
    RX_FREEZE <= (state == TOKEN_WAIT || next_state == READ_STATE );

reg [1:0] read_dly;
always@(posedge CLK_BX)
    read_dly[1:0] <= {read_dly[0], RX_READ};
    
reg [1:0] read_out_dly;
always@(posedge RX_CLK)
    read_out_dly <= {read_out_dly[0], read_dly[1]};
    
reg load;
always@(posedge RX_CLK)
    load <= read_out_dly[0] & !read_out_dly[1];
    
reg [6:0] cnt;
always@(posedge RX_CLK)
    if(RST_SYNC)
        cnt <= -1;
    else if(load)
        cnt <= 0;
    else if(cnt != 7'hff)
        cnt <= cnt + 1;

reg [29:0] ser;
always@(posedge RX_CLK)
    ser <= {ser[28:0], RX_DATA};

wire store_data;
assign store_data = (cnt == 29);

reg [29:0] data_out;
wire [29:0] data_to_cdc;

always@(posedge RX_CLK)
    if(RST_SYNC)
        data_out <= 0;
    else if(store_data)
        data_out <= ser;

reg data_out_strobe;        
always@(posedge RX_CLK)
    if(store_data)
        data_out_strobe <= 1;
    else 
        data_out_strobe <= 0; 
        
//
wire cdc_fifo_write;
assign cdc_fifo_write = data_out_strobe;

wire wfull;
always@(posedge RX_CLK) begin
    if(RST_SYNC)
        LOST_DATA_CNT <= 0;
    else if (wfull && cdc_fifo_write && LOST_DATA_CNT != -1)
        LOST_DATA_CNT <= LOST_DATA_CNT +1;
end

wire [5:0] col;
wire [7:0] row, te_gray, le_gray, te, le;
assign {le_gray, te_gray, row, col} = data_out;
    
bin_to_gray7 bin_to_gray_te(.gray_input(te_gray), .bin_out(te) );
bin_to_gray7 bin_to_gray_le(.gray_input(le_gray), .bin_out(le) );

assign data_to_cdc = CONF_DISSABLE_GRAY_DEC ? data_out : {le, te, row, col};

wire [29:0] cdc_data_out;
wire cdc_fifo_empty, fifo_full;
cdc_syncfifo #(.DSIZE(30), .ASIZE(3)) cdc_syncfifo_i
(
    .rdata(cdc_data_out),
    .wfull(wfull),
    .rempty(cdc_fifo_empty),
    .wdata(data_to_cdc),
    .winc(cdc_fifo_write), .wclk(RX_CLK), .wrst(RST_SYNC),
    .rinc(!fifo_full), .rclk(BUS_CLK), .rrst(RST)
);

gerneric_fifo #(.DATA_SIZE(30), .DEPTH(1024))  fifo_i
( .clk(BUS_CLK), .reset(RST), 
    .write(!cdc_fifo_empty),
    .read(FIFO_READ), 
    .data_in(cdc_data_out), 
    .full(fifo_full), 
    .empty(FIFO_EMPTY), 
    .data_out(FIFO_DATA[29:0]), .size() 
);

assign FIFO_DATA[31:30]  =  IDENTYFIER[1:0]; 

assign LOST_ERROR = LOST_DATA_CNT != 0;

endmodule
