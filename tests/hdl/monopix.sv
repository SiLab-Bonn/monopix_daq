/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University 
 * ------------------------------------------------------------
 */

`timescale 1ns / 1ps

module mono_pixel(
    input ANA_HIT,
    input Injection,
    
    input logic SR_CLK, SR_DATA_IN, SR_EN,
    output logic SR_DATA_OUT,
    
    input logic [0:3] TRIM_EN,
    input logic INJECT_EN,
    input logic MONITOR_EN,
    input logic PREAMP_EN,
    
    output logic OUT_MONITOR
    
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

generate
    genvar col_i;
    genvar row_i;
    for (col_i=0; col_i<36/2; col_i=col_i+1) begin: col_gen
        wire [129-1:0] dc_mon_L;
        wire [129-1:0] dc_mon_R;
        assign pix_mon[2*col_i] = |dc_mon_L;
        assign pix_mon[2*col_i+1] = |dc_mon_R;
        
        if(col_i < DCOLS) begin
            for (row_i = 0; row_i <129; row_i = row_i + 1) begin: row_gen
                
                mono_pixel mono_pixel_L(
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
                                
                                .OUT_MONITOR(dc_mon_L[row_i])
                    );
                                
                 mono_pixel mono_pixel_R(
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
                                
                                .OUT_MONITOR(dc_mon_R[row_i])
                     );
            end
        end
        else begin
            assign dc_mon_L = 0;
            assign dc_mon_R = 0;
        end
    
    end
endgenerate

endmodule
