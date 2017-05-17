
`timescale 1ns / 1ps
`default_nettype none

`include "clk_gen.v"

`include "utils/bus_to_ip.v"

`include "utils/cdc_syncfifo.v"
`include "utils/generic_fifo.v"
`include "utils/cdc_pulse_sync.v"

`include "utils/reset_gen.v"
//`include "utils/pulse_gen_rising.v"
`include "utils/CG_MOD_pos.v"
 
`include "spi/spi_core.v"
`include "spi/spi.v"
`include "spi/blk_mem_gen_8_to_1_2k.v"

`include "gpio/gpio.v"

//`include "utils/cdc_reset_sync.v"
`include "utils/fx2_to_bus.v"

`include "pulse_gen/pulse_gen.v"
`include "pulse_gen/pulse_gen_core.v"

`include "tdc_s3/tdc_s3.v"
`include "tdc_s3/tdc_s3_core.v"

`include "sram_fifo/sram_fifo_core.v"
`include "sram_fifo/sram_fifo.v"

`include "utils/3_stage_synchronizer.v"
`include "rrp_arbiter/rrp_arbiter.v"
`include "utils/ddr_des.v"
`include "utils/flag_domain_crossing.v"

`include "mono_data_rx/mono_data_rx.v"
`include "utils/cdc_reset_sync.v"

`ifdef COCOTB_SIM //for simulation
    `include "utils/ODDR_sim.v"
    `include "utils/IDDR_sim.v"
    `include "utils/DCM_sim.v"
    `include "utils/clock_multiplier.v"
    `include "utils/BUFG_sim.v"

    `include "utils/RAMB16_S1_S9_sim.v"
    //`include "utils/IBUFDS_sim.v"
    //`include "utils/IBUFGDS_sim.v"
    //`include "utils/OBUFDS_sim.v"
`else
    `include "utils/IDDR_s3.v"
    `include "utils/ODDR_s3.v"
`endif 



module monopix_mio (
    
    input wire FCLK_IN, // 48MHz
    
    //full speed 
    inout wire [7:0] BUS_DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,
    
    //high speed
    inout wire [7:0] FDATA,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //LED
    output wire [4:0] LED,
    
    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,


    input wire [2:0] LEMO_RX,
    output wire [2:0] LEMO_TX, 

    input wire SR_OUT,
    output wire SR_IN,
    output wire LDPIX,
    output wire CKCONF,
    output wire LDDAC,
    output wire SR_EN,
    output wire RESET,
    output wire INJECTION,
    input wire MONITOR,
    
    output wire CLK_BX, 
    output wire READ,
    output wire FREEZE,
    output wire nRST,
    output wire EN_TEST_PATTERN,
    output wire RST_GRAY,
    output wire EN_DRIVER,
    output wire EN_DATA_CMOS,
    output wire CLK_OUT,
    input wire TOKEN,
    input wire DATA,
    input wire DATA_LVDS,
    
    // I2C
    inout wire SDA,
    inout wire SCL
);

assign SDA = 1'bz;
assign SCL = 1'bz;


// ------- RESRT/CLOCK  ------- //

wire BUS_RST;

(* KEEP = "{TRUE}" *) 
wire CLK320;  
(* KEEP = "{TRUE}" *) 
wire CLK160;
(* KEEP = "{TRUE}" *) 
wire CLK40;
(* KEEP = "{TRUE}" *) 
wire CLK16;
(* KEEP = "{TRUE}" *) 
wire BUS_CLK;
(* KEEP = "{TRUE}" *) 
wire CLK8;

reset_gen reset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

wire CLK_LOCKED;

clk_gen clk_gen(
    .CLKIN(FCLK_IN),
    .BUS_CLK(BUS_CLK),
    .U1_CLK8(CLK8),
    .U2_CLK40(CLK40),
    .U2_CLK16(CLK16),
    .U2_CLK160(CLK160),
    .U2_CLK320(CLK320),
    .U2_LOCKED(CLK_LOCKED)
);

// -------  MODULE ADREESSES  ------- //
localparam GPIO_BASEADDR = 16'h0000;
localparam GPIO_HIGHADDR = 16'h0100-1;

localparam SPI_BASEADDR = 16'h1000;
localparam SPI_HIGHADDR = 16'h2000-1;

localparam PULSE_INJ_BASEADDR = 16'h0100;
localparam PULSE_INJ_HIGHADDR = 16'h0200-1;
    
localparam TDC_BASEADDR = 16'h0300;
localparam TDC_HIGHADDR = 16'h0400-1;
    
localparam PULSE_GATE_TDC_BASEADDR = 16'h0400;
localparam PULSE_GATE_TDC_HIGHADDR = 16'h0500-1;

localparam DATA_RX_BASEADDR = 16'h0500;
localparam DATA_RX_HIGHADDR = 16'h0600-1;
    
localparam FIFO_BASEADDR = 16'h8000;
localparam FIFO_HIGHADDR = 16'h9000-1;


// -------  BUS SYGNALING  ------- //
wire [15:0] BUS_ADD;
wire BUS_RD, BUS_WR;

// -------  BUS SYGNALING  ------- //
fx2_to_bus fx2_to_bus (
    .ADD(ADD),
    .RD_B(RD_B),
    .WR_B(WR_B),

    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .CS_FPGA()
);

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
    .EXT_START(SLD | GATE_TDC),
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

wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;

wire FE_FIFO_READ;
wire FE_FIFO_EMPTY;
wire [31:0] FE_FIFO_DATA;
    
wire TDC_FIFO_READ;
wire TDC_FIFO_EMPTY;
wire [31:0] TDC_FIFO_DATA;

wire SPI_FIFO_READ;
wire SPI_FIFO_EMPTY;
wire [31:0] SPI_FIFO_DATA;
assign SPI_FIFO_EMPTY = 1;

rrp_arbiter 
#( 
    .WIDTH(3)
) rrp_arbiter
(
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~FE_FIFO_EMPTY, ~TDC_FIFO_EMPTY, ~SPI_FIFO_EMPTY}),
    .HOLD_REQ({3'b0}),
    .DATA_IN({FE_FIFO_DATA, TDC_FIFO_DATA,SPI_FIFO_DATA}),
    .READ_GRANT({FE_FIFO_READ, TDC_FIFO_READ, SPI_FIFO_READ}),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
    );
    

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
    .TDC_OUT(LEMO_TX[0]),
    .TRIG_IN(LEMO_RX[0]),
    .TRIG_OUT(),

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
    
    .TIMESTAMP(16'b0)
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
    
    .FIFO_READ(FE_FIFO_READ),
    .FIFO_EMPTY(FE_FIFO_EMPTY),
    .FIFO_DATA(FE_FIFO_DATA),
    
    .LOST_ERROR()
    
); 
 
wire USB_READ;
assign USB_READ = FREAD & FSTROBE;
    
wire FIFO_FULL;
sram_fifo #(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR)
) sram_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR), 

    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),

    .USB_READ(USB_READ),
    .USB_DATA(FDATA),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),

    .FIFO_NOT_EMPTY(),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(),
    .FIFO_READ_ERROR()
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
assign LED[0] = 0;
assign LED[1] = 0;
assign LED[2] = 0;
assign LED[3] = 0;
assign LED[4] = 0;

assign LEMO_TX[1] = INJECTION;
assign LEMO_TX[2] = 0;

endmodule
