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
    parameter IDENTYFIER = 2'b00
)(
    input wire CLK_BX,
    input wire RX_TOKEN, RX_DATA, RX_CLK,
    output reg RX_READ, RX_FREEZE,
    output reg RX_nRST,
    output wire READY,
    input wire [63:0] TIMESTAMP,
    
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

localparam VERSION = 3;

wire SOFT_RST;
assign SOFT_RST = (BUS_ADD==0 && BUS_WR);

wire RST;
assign RST = BUS_RST | SOFT_RST;

reg CONF_EN;
reg CONF_DISSABLE_GRAY_DEC;
reg CONF_FORCE_RST;

reg [7:0] CONF_START_FREEZE;
reg [7:0] CONF_STOP_FREEZE;
reg [7:0] CONF_START_READ;
reg [7:0] CONF_STOP_READ;
reg [7:0] CONF_STOP;
reg [7:0] CONF_READ_SHIFT;
reg [7:0] CONF_START_RST;
reg [7:0] CONF_STOP_RST;

always @(posedge BUS_CLK) begin
    if(RST) begin
        CONF_EN <= 0;
        CONF_DISSABLE_GRAY_DEC <= 0;
        CONF_FORCE_RST <= 0;
          CONF_START_FREEZE <= 3;
          CONF_START_READ <= 6;
          CONF_STOP_READ <= 7;
          CONF_STOP_FREEZE <= 15;
          CONF_STOP <= 45;
          CONF_READ_SHIFT <=58; // (29<<1)
          CONF_START_RST<= 0;
          CONF_START_RST<= 0;
    end
    else if(BUS_WR) begin
        if(BUS_ADD == 2) begin
            CONF_EN <= BUS_DATA_IN[0];
            CONF_DISSABLE_GRAY_DEC <= BUS_DATA_IN[1];
            CONF_FORCE_RST <= BUS_DATA_IN[2];
          end
          else if(BUS_ADD == 4)
              CONF_START_FREEZE <= BUS_DATA_IN;
          else if(BUS_ADD == 5)
              CONF_STOP_FREEZE <= BUS_DATA_IN;
          else if(BUS_ADD == 6)
              CONF_START_READ <= BUS_DATA_IN;
          else if(BUS_ADD == 7)
              CONF_STOP_READ <= BUS_DATA_IN;
          else if(BUS_ADD == 8)
              CONF_STOP <= BUS_DATA_IN;
          else if(BUS_ADD == 9)
              CONF_READ_SHIFT <= BUS_DATA_IN;
          else if(BUS_ADD == 10)
              CONF_START_RST <= BUS_DATA_IN;
            else if(BUS_ADD == 11)
              CONF_STOP_RST <= BUS_DATA_IN;
    end
end

reg [7:0] LOST_DATA_CNT;
reg[51:0] token_timestamp;
reg[27:0] token_cnt;
always @(posedge BUS_CLK) begin
    if(BUS_RD) begin
        if(BUS_ADD == 0)
            BUS_DATA_OUT <= VERSION;
        else if(BUS_ADD == 2)
            BUS_DATA_OUT <= {5'b0, CONF_FORCE_RST,CONF_DISSABLE_GRAY_DEC, CONF_EN};
        else if(BUS_ADD == 3)
            BUS_DATA_OUT <= LOST_DATA_CNT;
        else if(BUS_ADD == 4)
            BUS_DATA_OUT <= CONF_START_FREEZE;
        else if(BUS_ADD == 5)
            BUS_DATA_OUT <= CONF_STOP_FREEZE;
        else if(BUS_ADD == 6)
            BUS_DATA_OUT <= CONF_START_READ;
        else if(BUS_ADD == 7)
            BUS_DATA_OUT <= CONF_STOP_READ;
        else if(BUS_ADD == 8)
            BUS_DATA_OUT <= CONF_STOP;
		else if(BUS_ADD == 9)
            BUS_DATA_OUT <= CONF_READ_SHIFT[7:0];
        else if(BUS_ADD == 10)
                BUS_DATA_OUT <= CONF_START_RST;
            else if(BUS_ADD == 11)
                BUS_DATA_OUT <= CONF_STOP_RST;
         else if(BUS_ADD == 17)
            BUS_DATA_OUT <= {7'b0,READY};
         else if (BUS_ADD ==18)  ///debug
            BUS_DATA_OUT <= TIMESTAMP[8:0];
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

assign READY = ~RX_FREEZE & CONF_EN;

reg [3:0] TOKEN_FF;
always@(posedge RX_CLK)
    if (RST_SYNC)
	     TOKEN_FF <= 4'b0;
	 else
	     TOKEN_FF <= {TOKEN_FF[2:0],RX_TOKEN};
wire TOKEN_SYNC;
assign TOKEN_SYNC = ~TOKEN_FF[1] & TOKEN_FF[0];
reg TOKEN_NEXT;

always@(posedge RX_CLK)
    if (RST_SYNC) begin
	     token_timestamp <= 52'b0;
	     token_cnt <= 28'b0;
	 end
	 else if ( TOKEN_SYNC ) begin
	     token_timestamp <= TIMESTAMP[51:0];
	     token_cnt <= token_cnt+1;
	 end

parameter NOP=4'd0, WAIT_ONE = 4'd1, NOP_NEXT=4'd2, WAIT_NEXT = 4'd3, 
          WAIT_TWO = 4'd4, WAIT_TWO_NEXT = 4'd5;
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
            if(TOKEN_FF[0] & CONF_EN)
                next_state = WAIT_ONE;   
        WAIT_ONE:
		    if ( (DelayCnt == CONF_STOP_FREEZE - 2 ) & TOKEN_FF[0]) 
				next_state = WAIT_TWO;
            else if (DelayCnt == CONF_STOP) begin
                if(!RX_FREEZE & TOKEN_FF[0])
                    next_state = NOP_NEXT;
                else 
                    next_state = NOP;
            end
        WAIT_TWO:
		      next_state =WAIT_ONE;
        NOP_NEXT:
            if(TOKEN_FF[0] & CONF_EN)
                next_state = WAIT_NEXT;        
        WAIT_NEXT:
            if ( (DelayCnt == CONF_STOP_FREEZE - 2 ) & TOKEN_FF[0])
				next_state = WAIT_TWO_NEXT;
            else if(DelayCnt == CONF_STOP) begin
                if(TOKEN_FF[0])
                    next_state = NOP_NEXT;
            else
                    next_state = NOP;
            end
        WAIT_TWO_NEXT:
              next_state =WAIT_NEXT;
    endcase
end
     
always@(posedge CLK_BX)
if(RST_SYNC || state == NOP || state == NOP_NEXT)
    DelayCnt <= 0;
else if (state == WAIT_TWO || state == WAIT_TWO_NEXT )
    DelayCnt <= CONF_START_READ - 2;
else if(DelayCnt != 8'hff)
    DelayCnt <= DelayCnt + 1;
	 

always@(posedge CLK_BX)
    if(RST_SYNC)
        TOKEN_NEXT <= 1'b0;
	 else if(DelayCnt == CONF_STOP_READ + 4) //should be +1
        TOKEN_NEXT <= TOKEN_FF[0];

always@(posedge CLK_BX)
//always@(negedge CLK_BX)
    RX_READ <= (DelayCnt >= CONF_START_READ && DelayCnt < CONF_STOP_READ); 

always@(posedge CLK_BX) begin
    if(RST_SYNC)
        RX_FREEZE <= 1'b0;
    else if(DelayCnt == CONF_START_FREEZE)
        RX_FREEZE <= 1'b1;
    else if(DelayCnt == CONF_STOP_FREEZE && !TOKEN_FF[0])
        RX_FREEZE <= 1'b0;
end         
    
always@(posedge CLK_BX) begin
    if(RST_SYNC)
        RX_nRST <= 1'b1;
    else if (CONF_START_RST==0)
        RX_nRST <= 1'b1;
    else if( (DelayCnt==CONF_START_RST) && (!TOKEN_FF[0] | CONF_FORCE_RST) )
        RX_nRST <= 1'b0;
    else if(DelayCnt == CONF_STOP_RST)
        RX_nRST <= 1'b1;
end            
    
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

        
reg [29:0] ser_neg;
always@(negedge RX_CLK)
    ser_neg <= {ser_neg[28:0], RX_DATA};
    
reg [29:0] ser;
always@(posedge RX_CLK)
    ser <= {ser[28:0], RX_DATA};

wire store_data;
assign store_data = (cnt == CONF_READ_SHIFT[7:1]);

reg [29:0] data_out;
wire [110:0] data_to_cdc;   // [82:0] data_to_cdc;

always@(posedge RX_CLK) begin
    if(RST_SYNC)
        data_out <= 0;
    else if(store_data) begin
        if (CONF_READ_SHIFT[0]==1)
            data_out <= ser_neg;
        else 
            data_out <= ser;
    end
end
        
reg data_out_strobe;    
always@(posedge RX_CLK) begin
    if(store_data)
        data_out_strobe <= 1;
    else 
        data_out_strobe <= 0; 
end
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

wire posssible_noise;
assign posssible_noise = (state == WAIT_NEXT || state == WAIT_TWO_NEXT);


wire [5:0] col;
wire [7:0] row, te_gray, le_gray, te, le;
assign {le_gray, te_gray, row, col} = data_out;
    
bin_to_gray7 bin_to_gray_te(.gray_input(te_gray), .bin_out(te) );
bin_to_gray7 bin_to_gray_le(.gray_input(le_gray), .bin_out(le) );

assign data_to_cdc = CONF_DISSABLE_GRAY_DEC ? {token_cnt,token_timestamp,posssible_noise, data_out} : {token_cnt,token_timestamp,posssible_noise, le, te, row, col};

wire [110:0] cdc_data_out; //[82:0] cdc_data_out;
wire cdc_fifo_empty, fifo_full, fifo_write;
wire cdc_fifo_read;
//cdc_syncfifo #(.DSIZE(83), .ASIZE(8)) cdc_syncfifo_i
cdc_syncfifo #(.DSIZE(111), .ASIZE(8)) cdc_syncfifo_i
(
    .rdata(cdc_data_out),
    .wfull(wfull),
    .rempty(cdc_fifo_empty),
    .wdata(data_to_cdc),
    .winc(cdc_fifo_write), .wclk(RX_CLK), .wrst(RST_SYNC),
    .rinc(cdc_fifo_read), .rclk(BUS_CLK), .rrst(RST)
);

reg [2:0] byte2_cnt, byte2_cnt_prev;
always@(posedge BUS_CLK)
    byte2_cnt_prev <= byte2_cnt;
assign cdc_fifo_read = (byte2_cnt_prev==0 & byte2_cnt!=0);
assign fifo_write = byte2_cnt_prev != 0;

always@(posedge BUS_CLK)
    if(RST)
        byte2_cnt <= 0;
    else if(!cdc_fifo_empty && !fifo_full && byte2_cnt == 0 ) 
        //byte2_cnt <= 3;
        byte2_cnt <= 4;
    else if (!fifo_full & byte2_cnt != 0)
        byte2_cnt <= byte2_cnt - 1;

//reg [82:0] data_buf;
reg [110:0] data_buf;
always@(posedge BUS_CLK)
    if(cdc_fifo_read)
        data_buf <= cdc_data_out;

wire [29:0] fifo_write_data_byte [4:0];
assign fifo_write_data_byte[4]=29'b0; 
assign fifo_write_data_byte[3]={2'b01,data_buf[42:31],data_buf[13:6],1'b0,data_buf[30],data_buf[5:0]};
assign fifo_write_data_byte[2]={2'b10,data_buf[54:43],data_buf[29:22],data_buf[21:14]};
assign fifo_write_data_byte[1]={2'b11,data_buf[82:55]};
assign fifo_write_data_byte[0]={2'b00,data_buf[110:83]}; //last data is dummy

wire [31:0] fifo_data_in;
assign fifo_data_in = fifo_write_data_byte[byte2_cnt];


gerneric_fifo #(.DATA_SIZE(30), .DEPTH(1023))  fifo_i
( .clk(BUS_CLK), .reset(RST), 
    .write(fifo_write),
    .read(FIFO_READ), 
    .data_in(fifo_data_in), 
    .full(fifo_full), 
    .empty(FIFO_EMPTY), 
    .data_out(FIFO_DATA[29:0]), .size() 
);

assign FIFO_DATA[31:30]  =  IDENTYFIER; 

assign LOST_ERROR = LOST_DATA_CNT != 0;

endmodule
