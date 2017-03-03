/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University 
 * ------------------------------------------------------------
 */

`timescale 1ns / 1ps

module mono_pixel 
#(
    parameter ADDR = 0
)(
    input ANA_HIT,
    input Injection,
    
    input logic SR_CLK, SR_DATA_IN, SR_EN,
    output logic SR_DATA_OUT,
    
    input logic [0:3] TRIM_EN,
    input logic INJECT_EN,
    input logic MONITOR_EN,
    input logic PREAMP_EN,
    
    output logic OUT_MONITOR,
    
    input logic nRST, TOK_IN, READ, FREEZE,
    input logic [7:0] Time,
    
    output logic TOK_OUT,
    inout logic [7:0] LE_RAM, TE_RAM, ROW_SW
);

logic [3:0] trim_en_ld;
logic injection_en_ld;
logic preamp_en_ld;
logic monitor_en_ld;
    
logic int_inj;
initial begin
  int_inj = 0;
  forever begin
    @(negedge Injection)
        int_inj = 1;
        #(25*trim_en_ld) int_inj = 0;
  end
end

logic HIT;
assign HIT = ((ANA_HIT | (int_inj & injection_en_ld)) & preamp_en_ld);

logic CDN;
assign CDN = !(HIT & SR_EN);

always@(posedge SR_CLK or negedge CDN)
    if(!CDN)
        SR_DATA_OUT <= 0;
    else
        SR_DATA_OUT <= SR_DATA_IN;

always@(*) if(TRIM_EN[0]) trim_en_ld[0] = SR_DATA_OUT;
always@(*) if(TRIM_EN[1]) trim_en_ld[1] = SR_DATA_OUT;
always@(*) if(TRIM_EN[2]) trim_en_ld[2] = SR_DATA_OUT;
always@(*) if(TRIM_EN[3]) trim_en_ld[3] = SR_DATA_OUT;

always@(*) if(INJECT_EN) injection_en_ld = SR_DATA_OUT;
always@(*) if(MONITOR_EN) monitor_en_ld = SR_DATA_OUT;
always@(*) if(PREAMP_EN) preamp_en_ld = SR_DATA_OUT;

assign OUT_MONITOR = HIT & monitor_en_ld;



// ------ DIGITAL ---------
reg latched_TE;
wire RstInt;
always@(negedge HIT or posedge RstInt)
    if(RstInt)
        latched_TE <= 0;
    else
        latched_TE <= 1;

reg HIT_FLAG;
always@(*)
    if(RstInt)
        HIT_FLAG = 0;
    else if(latched_TE & FREEZE==0)  
        HIT_FLAG = 1;

wire ReadPix;        
assign TOK_OUT = TOK_IN | HIT_FLAG;
assign ReadPix = (TOK_IN==0 & HIT_FLAG==1);

reg ReadLatch;
always@(*)
    if(!READ)
        ReadLatch = ReadPix;

assign READ_INT = ReadLatch & READ;
assign RstInt = (nRST == 0 | READ==1);
 

reg [7:0] LeTime, TeTime;
always@(posedge HIT)
    LeTime <= Time;
    
always@(negedge HIT)
    TeTime <= Time;

assign LE_RAM = READ_INT ? LeTime :8'bz;
assign TE_RAM = READ_INT ? TeTime :8'bz;
assign ROW_SW = READ_INT ? ADDR[7:0] :8'bz; 
    
endmodule

module mono_eoc(
            input wire TokInChip, TokInCol, Read,
            output wire  TokOutChip, ReadCol,

            output wire [5:0] ColAddrOut,
            input wire [5:0] ColAddrIn,
            input wire [5:0] ColAddr,

            output wire [23:0] ColDataOut,
            input wire [23:0] ColDataIn,
            input wire [23:0] ColData,

            input wire [7:0] Bcid,
            output wire [7:0] BcidCol,

            input wire Enable
          );


wire TokInColEn;
assign TokInColEn = TokInCol & Enable;

assign TokOutChip = TokInColEn | TokInChip;

reg beeze_prev_int;
always@(Read or TokInChip)
if(!Read)
   beeze_prev_int = TokInChip;
   
reg beeze_col_int;
always@(Read or TokInColEn)
if(!Read)
   beeze_col_int = TokInColEn;
   
wire this_col_read;
assign this_col_read = (beeze_prev_int==0 && beeze_col_int==1);

assign ReadCol = this_col_read & Read; 

reg this_token_save;
always@(posedge Read) 
    this_token_save <= TokInColEn & !TokInChip;

wire [5:0] addr_this;
assign addr_this = this_token_save ? ColAddr : 0;
assign ColAddrOut = addr_this | ColAddrIn;

wire [23:0] data_this;
assign data_this = this_token_save ? ColData : 0;
assign ColDataOut = data_this | ColDataIn;

assign BcidCol = Bcid & {8{Enable}};

endmodule 

module mono_serializer (
            input wire clk_bx, clk_out, read, en_test_pattern,
            input wire [29:0] data_in,
            output wire out
          );

reg [1:0] read_dly;
always@(posedge clk_bx)
    read_dly[1:0] <= {read_dly[0], read};
    
reg [1:0] read_out_dly;
always@(posedge clk_out)
    read_out_dly <= {read_out_dly[0], read_dly[1]};
    
reg load;
always@(posedge clk_out)
    load <= read_out_dly[0] & !read_out_dly[1];

reg [29:0] ser;
always@(posedge clk_out)
    if(load)
        if(en_test_pattern)
            ser <= 30'b100000_10101010_11001100_00001111;
        else
            ser <= data_in;
    else
        ser <= {ser[28:0], 1'b0};
        
assign out = ser[29];
          
endmodule

module monopix (
    input wire [0:4643] ANA_HIT,
    input wire Injection,
    output wire Monitor,
    
    input wire Clk_BX, 
    input wire READ,
    input wire FREEZE,
    input wire nRST,
    input wire EN_Test_Pattern,
    input wire RST_Gray,
    input wire EN_Driver,
    input wire EN_Data_CMOS,
    input wire Clk_Out,
    output wire Token_Out,
    output wire Data_Out,
    
    input wire Clk_Conf,
    input wire SR_In,
    input wire LdDAC,
    input wire SR_EN,
    input wire SR_RST,
    input wire LdPix,
    output wire SR_out
);
    

struct packed{
    logic [0:5] BLRes;
    logic [0:5] VAmp;
    logic [0:5] VPFB;
    logic [0:5] VFoll;
    logic [0:5] VLoad;
    logic [0:5] IComp;
    logic [0:5] Vbias_CS;
    logic [0:5] IBOTA;
    logic [0:5] ILVDS;
    logic [0:5] Vsf;
    logic [0:5] LSBdacL;
    logic [0:5] Vsf_dis1;
    logic [0:5] Vsf_dis2;
    logic [0:35] ColRO_En;
    logic [0:5] Vsf_dis3;
    logic [0:3] TRIM_EN;
    logic [0:0] INJECT_EN;
    logic [0:0] MONITOR_EN;
    logic [0:0] PREAMP_EN;
    logic [0:13] NotUsed;
    logic [0:35] MON_EN;
    logic [0:17] INJ_EN;
    logic [0:0] BUFFER_EN;
    logic [0:0] REGULATOR_EN;
} mopnopix_globar_sr, mopnopix_globar_ld;


always@(posedge Clk_Conf or posedge SR_RST)
    if(SR_RST)
        mopnopix_globar_sr <= 0;
    else
        mopnopix_globar_sr <= {SR_In, mopnopix_globar_sr[$bits(mopnopix_globar_sr)-1:1]};

always@(*) 
    if(LdDAC)
        mopnopix_globar_ld = mopnopix_globar_sr;

`ifndef TEST_DC
    localparam DCOLS = 36/2; 
`else
    localparam DCOLS = `TEST_DC;
`endif

logic [0:18*129*2] pix_sr;
logic [0:35] pix_mon;

assign Monitor = !(|(pix_mon & mopnopix_globar_ld.MON_EN));
assign pix_sr[0] = mopnopix_globar_sr[0];
assign SR_out = pix_sr[DCOLS*129*2];

logic [7:0] Time;
logic [7:0] TimeGray;
always@(posedge Clk_BX)
    if(RST_Gray)
        Time <= 0;
    else
        Time <= Time +1;
        
assign TimeGray = (Time >> 1) ^ Time;
        
logic [36/2:0] tok_chip_int;
assign tok_chip_int[0] = 0;
logic [5:0] col_addr_int [36/2:0];
assign col_addr_int[0] = 0;
logic [23:0] col_data_int [36/2:0];
assign col_data_int[0] = 0;

generate
    genvar col_i;
    genvar row_i;
    for (col_i=0; col_i<36/2; col_i=col_i+1) begin: col_gen
        wire [129-1:0] dc_mon_L;
        wire [129-1:0] dc_mon_R;
        assign pix_mon[2*col_i] = |dc_mon_L;
        assign pix_mon[2*col_i+1] = |dc_mon_R;
        wire [129:0] tok_int_l, tok_int_r;
        assign tok_int_l[0] = 0;
        assign tok_int_r[0] = 0;
        
        wire READ_L, READ_R;
        wire [7:0] LE_RAM_L, TE_RAM_L, ROW_SW_L, LE_RAM_R, TE_RAM_R, ROW_SW_R;
        
        wire [7:0] Bcid_L, Bcid_R;
        
        if(col_i < DCOLS) begin
        
            for (row_i = 0; row_i <129; row_i = row_i + 1) begin: row_gen
                
                mono_pixel #(.ADDR(row_i)) mono_pixel_L (
                                .ANA_HIT(ANA_HIT[col_i*(129*2)+row_i]),
                                .Injection(Injection & mopnopix_globar_ld.INJ_EN[col_i]),
                                
                                .SR_CLK(Clk_Conf), 
                                .SR_DATA_IN(pix_sr[col_i*(129*2)+row_i]), 
                                .SR_EN(SR_EN),
                                .SR_DATA_OUT(pix_sr[col_i*(129*2)+row_i+1]),
                                
                                .TRIM_EN(mopnopix_globar_sr.TRIM_EN & {4{LdPix}}),
                                .INJECT_EN(mopnopix_globar_sr.INJECT_EN & LdPix),
                                .MONITOR_EN(mopnopix_globar_sr.MONITOR_EN & LdPix),
                                .PREAMP_EN(mopnopix_globar_sr.PREAMP_EN & LdPix),
                                
                                .OUT_MONITOR(dc_mon_L[row_i]),
                                
                                .nRST(nRST), .TOK_IN(tok_int_l[row_i]), .READ(READ_L), .FREEZE(FREEZE),
                                .Time(Bcid_L),
                                .TOK_OUT(tok_int_l[row_i+1]),
                                .LE_RAM(LE_RAM_L), .TE_RAM(TE_RAM_L), .ROW_SW(ROW_SW_L)
    
                    );
            
          
                 mono_pixel #(.ADDR(row_i)) mono_pixel_R (
                                .ANA_HIT(ANA_HIT[col_i*(129*2)+129+row_i]),
                                .Injection(Injection & mopnopix_globar_ld.INJ_EN[col_i]),
                                
                                .SR_CLK(Clk_Conf),
                                .SR_DATA_IN(pix_sr[col_i*(129*2)+129+row_i]),
                                .SR_EN(SR_EN),
                                .SR_DATA_OUT(pix_sr[col_i*(129*2)+129+row_i+1]),
                                
                                .TRIM_EN(mopnopix_globar_sr.TRIM_EN & {4{LdPix}}),
                                .INJECT_EN(mopnopix_globar_sr.INJECT_EN & LdPix),
                                .MONITOR_EN(mopnopix_globar_sr.MONITOR_EN & LdPix),
                                .PREAMP_EN(mopnopix_globar_sr.PREAMP_EN & LdPix),
                                
                                .OUT_MONITOR(dc_mon_R[row_i]),
                                
                                .nRST(nRST), .TOK_IN(tok_int_r[row_i]), .READ(READ_R), .FREEZE(FREEZE),
                                .Time(Bcid_R),
                                .TOK_OUT(tok_int_r[row_i+1]),
                                .LE_RAM(LE_RAM_R), .TE_RAM(TE_RAM_R), .ROW_SW(ROW_SW_R)
                                
                     );
            end
                            
        end
        else begin
            assign dc_mon_L = 0;
            assign dc_mon_R = 0;
            assign tok_int_l = 0;
            assign tok_int_r = 0;
        end
        
        logic tok_lr;
        logic [5:0] col_addr_lr;
        logic [23:0] col_data_lr;
        
        logic [5:0] col_add_l;
        assign col_add_l = col_i*2;
        
        logic [5:0] col_add_r;
        assign col_add_r = col_i*2+1;
        
        
        mono_eoc mono_eoc_l (
            .TokInChip(tok_chip_int[col_i]), 
            .TokInCol(tok_int_l[129]), 
            .Read(READ),
            .TokOutChip(tok_lr), 
            .ReadCol(READ_L),

            .ColAddrOut(col_addr_lr),
            .ColAddrIn(col_addr_int[col_i]),
            .ColAddr(col_add_l),

            .ColDataOut(col_data_lr),
            .ColDataIn(col_data_int[col_i]),
            .ColData({LE_RAM_L, TE_RAM_L, ROW_SW_L}),

            .Bcid(TimeGray),
            .BcidCol(Bcid_L),

            .Enable(mopnopix_globar_ld.ColRO_En[col_i*2])
        );
    
        mono_eoc mono_eoc_r (
            .TokInChip(tok_lr), 
            .TokInCol(tok_int_r[129]), 
            .Read(READ),
            .TokOutChip(tok_chip_int[col_i+1]), 
            .ReadCol(READ_R),

            .ColAddrOut(col_addr_int[col_i+1]),
            .ColAddrIn(col_addr_lr),
            .ColAddr(col_add_r),

            .ColDataOut(col_data_int[col_i+1]),
            .ColDataIn(col_data_lr),
            .ColData({LE_RAM_R, TE_RAM_R, ROW_SW_R}),

            .Bcid(TimeGray),
            .BcidCol(Bcid_R),

            .Enable(mopnopix_globar_ld.ColRO_En[col_i*2+1])
        );

    end
endgenerate

mono_serializer mono_serializer(
    .clk_bx(Clk_BX), 
    .clk_out(Clk_Out), 
    .read(READ), 
    .en_test_pattern(EN_Test_Pattern),
    .data_in({col_data_int[36/2], col_addr_int[36/2]}),
    .out(Data_Out)
);

assign Token_Out = tok_chip_int[36/2];

endmodule
