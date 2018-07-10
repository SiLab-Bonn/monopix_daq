
`timescale 1ns / 1ps
`default_nettype none

module monopix_mio_core (
    
    //local bus
    input wire BUS_CLK,
    inout wire [7:0] BUS_DATA,
    input wire [15:0] BUS_ADD,
    input wire BUS_RD,
    input wire BUS_WR,
    input wire BUS_RST,
    
    //clocks
    input wire CLK8,
    input wire CLK40,
    input wire CLK16,
    input wire CLK160,
    input wire CLK320,
    
    //fifo
    input wire ARB_READY_OUT,
    output wire ARB_WRITE_OUT,
    output wire [31:0] ARB_DATA_OUT,
    input wire FIFO_FULL,
    input wire FIFO_NEAR_FULL,

    //LED
    output wire [4:0] LED,
    
    input wire [2:0] LEMO_RX,
    output wire [2:0] LEMO_TX, // TX[0] == RJ45 trigger clock output, TX[1] == RJ45 busy output
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,

    input wire SR_OUT,    //DIN4
    output wire SR_IN,    //DOUT11
    output wire LDPIX,    //DOUT15
    output wire CKCONF,   //DOUT10
    output wire LDDAC,    //DOUT12
    output wire SR_EN,    //DOUT13
    output wire RESET,    //DOUT14
    output wire INJECTION,
    input wire MONITOR,   //DIN1
    
    output wire CLK_BX,   //DOUT1
    output wire READ,     //DOUT2
    output wire FREEZE,   //DOUT3
    output wire nRST,     //DOUT4
    output wire EN_TEST_PATTERN,  //DOUT5
    output wire RST_GRAY,         //DOUT6
    output wire EN_DRIVER,        //DOUT7
    output wire EN_DATA_CMOS,     //DOUT8
    output wire CLK_OUT,          //DOUT9
    input wire TOKEN,             //DIN2
    input wire DATA,              //DIN0
    input wire DATA_LVDS,         //DIN8_LVDS0
 
    output wire DEBUG //DOUT0

);

// -------  MODULE ADREESSES  ------- //
localparam GPIO_BASEADDR = 16'h0000;
localparam GPIO_HIGHADDR = 16'h0100-1;

localparam PULSE_INJ_BASEADDR = 16'h0100;
localparam PULSE_INJ_HIGHADDR = 16'h0200-1;

localparam TDC_BASEADDR = 16'h0300;
localparam TDC_HIGHADDR = 16'h0400-1;

localparam PULSE_GATE_TDC_BASEADDR = 16'h0400;
localparam PULSE_GATE_TDC_HIGHADDR = 16'h0500-1;

localparam DATA_RX_BASEADDR = 16'h0500;
localparam DATA_RX_HIGHADDR = 16'h0600-1;

localparam TLU_BASEADDR = 16'h0600;
localparam TLU_HIGHADDR = 16'h0700-1;

localparam TS_BASEADDR = 16'h0700;
localparam TS_HIGHADDR = 16'h0800-1;

localparam TS2_BASEADDR = 16'h0800;
localparam TS2_HIGHADDR = 16'h0900-1;

localparam SPI_BASEADDR = 16'h1000;
localparam SPI_HIGHADDR = 16'h2000-1;

localparam FIFO_BASEADDR = 16'h8000;
localparam FIFO_HIGHADDR = 16'h9000-1;



// -------  USER MODULES  ------- //
wire [15:0] GPIO_OUT;
gpio 
#( 
    .BASEADDR(GPIO_BASEADDR), 
    .HIGHADDR(GPIO_HIGHADDR),
    .IO_WIDTH(16),
    .IO_DIRECTION(16'hffff)
) gpio
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(GPIO_OUT)
    );    

wire RESET_CONF, LDDAC_CONF, LDPIX_CONF, SREN_CONF, EN_BX_CLK_CONF, EN_OUT_CLK_CONF, RESET_GRAY_CONF;
wire EN_TEST_PATTERN_CONF, EN_DRIVER_CONF, EN_DATA_CMOS_CONF, EN_GRAY_RESET_WITH_TDC_PULSE;
wire EN_GATE_TIMESTAMP,EN_DEBUG_TIMESTAMP;
wire EN_NEG_TIMESTAMP2;

assign RESET_CONF = GPIO_OUT[0];
assign LDDAC_CONF = GPIO_OUT[1];
assign LDPIX_CONF = GPIO_OUT[2];
assign SREN_CONF = GPIO_OUT[3];

assign EN_BX_CLK_CONF = GPIO_OUT[4];
assign EN_OUT_CLK_CONF = GPIO_OUT[5];
assign RESET_GRAY_CONF = GPIO_OUT[6];

assign EN_TEST_PATTERN_CONF = GPIO_OUT[7];
assign EN_DRIVER_CONF = GPIO_OUT[8];
assign EN_DATA_CMOS_CONF = GPIO_OUT[9];
assign EN_GRAY_RESET_WITH_TDC_PULSE = GPIO_OUT[10];
assign EN_GATE_TIMESTAMP = GPIO_OUT[11];
assign EN_DEBUG_TIMESTAMP= GPIO_OUT[12];
assign EN_NEG_TIMESTAMP2 = GPIO_OUT[13];


wire CONF_CLK;
assign CONF_CLK = CLK8;
    
wire SCLK, SDI, SDO, SEN, SLD;
spi 
#( 
    .BASEADDR(SPI_BASEADDR), 
    .HIGHADDR(SPI_HIGHADDR),
    .MEM_BYTES(1024) 
    )  spi_conf
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SPI_CLK(CONF_CLK),

    .SCLK(SCLK),
    .SDI(SDI),
    .SDO(SDO),
    .SEN(SEN),
    .SLD(SLD)
);

assign CKCONF = SCLK;
assign SR_IN = SDI;
assign SDO = SR_OUT;    

assign LDPIX = SLD & LDPIX_CONF;
assign LDDAC = SLD & LDDAC_CONF;

reg [3:0] delay_cnt;
always@(posedge CONF_CLK)
    if(BUS_RST)
        delay_cnt <= 0;
    else if(SEN)
        delay_cnt <= 4'b1111;
    else if(delay_cnt != 0)
        delay_cnt <= delay_cnt - 1;
        
assign SR_EN = SREN_CONF ? !((SEN | (|delay_cnt))) : 0;

wire GATE_TDC;
    
pulse_gen
#( 
    .BASEADDR(PULSE_INJ_BASEADDR), 
    .HIGHADDR(PULSE_INJ_HIGHADDR)
) pulse_gen_inj
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40), //~CLK40),
    .EXT_START(GATE_TDC),
    .PULSE(INJECTION) //DUT_INJ
);

    
pulse_gen
#( 
    .BASEADDR(PULSE_GATE_TDC_BASEADDR), 
    .HIGHADDR(PULSE_GATE_TDC_HIGHADDR)
    ) pulse_gen_gate_tdc
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40),
    .EXT_START(1'b0),
    .PULSE(GATE_TDC) 
);    

wire FE_FIFO_READ, FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA;
    
wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;


wire SPI_FIFO_READ;
wire SPI_FIFO_EMPTY;
wire [31:0] SPI_FIFO_DATA;
assign SPI_FIFO_EMPTY = 1;

wire TLU_FIFO_READ,TLU_FIFO_EMPTY,TLU_FIFO_PEEMPT_REQ;
wire [31:0] TLU_FIFO_DATA;

wire TS_FIFO_READ,TS_FIFO_EMPTY;
wire [31:0] TS_FIFO_DATA;

wire TS2_FIFO_READ,TS2_FIFO_EMPTY;
wire [31:0] TS2_FIFO_DATA;


rrp_arbiter 
#( 
    .WIDTH(5)
) rrp_arbiter
(
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TS2_FIFO_EMPTY,~TS_FIFO_EMPTY, ~FE_FIFO_EMPTY, ~TDC_FIFO_EMPTY, ~TLU_FIFO_EMPTY}),
    .HOLD_REQ({5'b0}),
    .DATA_IN({TS2_FIFO_DATA, TS_FIFO_DATA, FE_FIFO_DATA, TDC_FIFO_DATA, TLU_FIFO_DATA}),
    .READ_GRANT({TS2_FIFO_READ, TS_FIFO_READ, FE_FIFO_READ, TDC_FIFO_READ, TLU_FIFO_READ}),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
    );
    

wire TDC_TRIG_OUT,TDC_TDC_OUT;
wire [64:0] TIMESTAMP;

tdc_s3 #(
    .BASEADDR(TDC_BASEADDR),
    .HIGHADDR(TDC_HIGHADDR),
    .CLKDV(4),
    .DATA_IDENTIFIER(4'b0100), 
    .FAST_TDC(1),
    .FAST_TRIGGER(1)
) tdc (
    .CLK320(CLK320),
    .CLK160(CLK160),
    .DV_CLK(CLK40),
    .TDC_IN(MONITOR),
    .TDC_OUT(TDC_TDC_OUT),
    //.TRIG_IN(1'b0),
    .TRIG_IN(LEMO_RX[0]),
    .TRIG_OUT(TDC_TRIG_OUT),

    .FIFO_READ(TDC_FIFO_READ),
    .FIFO_EMPTY(TDC_FIFO_EMPTY),
    .FIFO_DATA(TDC_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(1'b0),
    .EXT_EN(GATE_TDC),
    
    .TIMESTAMP(TIMESTAMP[15:0])
);


//// TLU
wire TLU_BUSY,TLU_CLOCK;
wire TRIGGER_ACKNOWLEDGE_FLAG,TRIGGER_ACCEPTED_FLAG;
assign TRIGGER_ACKNOWLEDGE_FLAG = TRIGGER_ACCEPTED_FLAG;

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
	.TIMESTAMP_N_OF_BIT(64)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .TRIGGER_CLK(CLK40),
    
    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),
    
    .FIFO_PREEMPT_REQ(),   //.FIFO_PREEMPT_REQ(TLU_FIFO_PEEMPT_REQ),
    
    .TRIGGER({7'b0,TDC_TRIG_OUT}),
    .TRIGGER_VETO({7'b0,FIFO_FULL}),
	 
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),
	 //.EXT_TRIGGER_ENABLE(TLU_EXT_TRIGGER_ENABLE)
	 
    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .TIMESTAMP(TIMESTAMP)
);

wire DI;
assign DI = EN_DEBUG_TIMESTAMP? (EN_GATE_TIMESTAMP? INJECTION:TOKEN) : (EN_GATE_TIMESTAMP? GATE_TDC:LEMO_RX[1]);

timestamp
#(
    .BASEADDR(TS_BASEADDR),
    .HIGHADDR(TS_HIGHADDR),
    .IDENTIFIER(4'b0101)
)i_timestamp(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK(CLK40),
	 .DI(DI),
	 .EXT_ENABLE(1'b0),
	 .EXT_TIMESTAMP(TIMESTAMP),

    .FIFO_READ(TS_FIFO_READ),
    .FIFO_EMPTY(TS_FIFO_EMPTY),
    .FIFO_DATA(TS_FIFO_DATA)
    
);

wire DI2;
//assign DI2 = EN_NEG_TIMESTAMP2? ~LEMO_RX[0]:LEMO_RX[0];
assign DI2 = EN_NEG_TIMESTAMP2? ~TDC_TRIG_OUT:TDC_TRIG_OUT;

timestamp
#(
    .BASEADDR(TS2_BASEADDR),
    .HIGHADDR(TS2_HIGHADDR),
    .IDENTIFIER(4'b0110)
)i_timestamp2(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK(CLK40),
    .DI(DI2),
    .EXT_ENABLE(1'b0),
    .EXT_TIMESTAMP(TIMESTAMP),

    .FIFO_READ(TS2_FIFO_READ),
    .FIFO_EMPTY(TS2_FIFO_EMPTY),
    .FIFO_DATA(TS2_FIFO_DATA)
);

mono_data_rx #(
   .BASEADDR(DATA_RX_BASEADDR),
   .HIGHADDR(DATA_RX_HIGHADDR),
   .IDENTYFIER(2'b00)
) mono_data_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CLK_BX(CLK40),
    .RX_TOKEN(TOKEN), 
    .RX_DATA(DATA_LVDS), 
    .RX_CLK(CLK40),
    .RX_READ(READ), 
    .RX_FREEZE(FREEZE), 
    .TIMESTAMP(TIMESTAMP),
    
    .FIFO_READ(FE_FIFO_READ),
    .FIFO_EMPTY(FE_FIFO_EMPTY),
    .FIFO_DATA(FE_FIFO_DATA),
    
    .LOST_ERROR()
); 



ODDR clk_bx_gate(.D1(EN_BX_CLK_CONF), .D2(1'b0), .C(CLK40), .CE(1'b1), .R(1'b0), .S(1'b0), .Q(CLK_BX) );
//ODDR clk_out_gate(.D1(EN_OUT_CLK_CONF), .D2(1'b0), .C(CLK40), .CE(1'b1), .R(1'b0), .S(1'b0), .Q(CLK_OUT) );
assign CLK_OUT = EN_OUT_CLK_CONF ? CLK40 : 1'b0;

reg nRST_reg;
assign nRST = nRST_reg;
always@(negedge CLK40)
    nRST_reg <= !RESET_CONF;
   
reg RST_GRAY_reg;
assign RST_GRAY = RST_GRAY_reg;
always@(negedge CLK40)
    RST_GRAY_reg <= RESET_GRAY_CONF | (GATE_TDC & EN_GRAY_RESET_WITH_TDC_PULSE);

assign EN_TEST_PATTERN = EN_TEST_PATTERN_CONF;
assign EN_DRIVER = EN_DRIVER_CONF;
assign EN_DATA_CMOS = EN_DATA_CMOS_CONF;

//TODO: readout
assign RESET = 0;

// LED assignments
assign LED[0] = 1;
assign LED[1] = 0;
assign LED[2] = 0;
assign LED[3] = 0;
assign LED[4] = 0;

assign LEMO_TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign LEMO_TX[1] = TLU_BUSY;  // TLU_BUSY signal; also connected to RJ45 output. Asserted when TLU FSM has 
assign LEMO_TX[2] = INJECTION; // Do not use this port (no TX2 in MIO3)
assign DEBUG = GATE_TDC;
endmodule
