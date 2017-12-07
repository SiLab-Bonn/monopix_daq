''' This example investigates the efficiency of a radiation hard DMAP sensor.
  
      It is a prototype called Monopix.
      A Mimosa26 + ATLAS-FE-I4 telescope (named Anemone) is used that is read out
      with pyBAR.
  '''
  
import os
import logging
import numpy as np
  
from testbeam_analysis import hit_analysis
from testbeam_analysis import dut_alignment
from testbeam_analysis import track_analysis
from testbeam_analysis import result_analysis
from testbeam_analysis.tools import data_selection
  
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-1s] (%(threadName)-10s) %(message)s")
  
def is_updated(fout,over_write=False,fins=[]):
   if over_write:
       return False
   if not os.path.exists(fout):
       return False
   tout=os.path.getmtime(fout)
   for f in fins:
       if os.path.getmtime(f) >tout:
           return False
   print "already updated",fout
   return True
  
def run_analysis(m26_fnames,mono_fname,mono2_fname,corr_only=True,over_write=True):
    ##################
    ## initialize parameters
    data_files = [m26_fnames[0][:-3]+'_mframe6.h5',
          m26_fnames[0][:-3]+'_mframe5.h5',
          m26_fnames[0][:-3]+'_mframe4.h5',
          m26_fnames[0][:-3]+'_mframe3.h5',
          m26_fnames[0][:-3]+'_mframe2.h5',
          m26_fnames[0][:-3]+'_mframe1.h5',
          m26_fnames[0][:-3]+'_1_ev.h5',
          m26_fnames[0][:-3]+'_2_ev.h5',
          mono_fname[:-3]+"_ev.h5", 
          mono2_fname[:-3]+"_ev.h5"]
              
    # Pixel dimesions and matrix size of the DUTs (hori,vert)
    pixel_size = [(18.4, 18.4), (18.4, 18.4),(18.4, 18.4),
                  (18.4, 18.4), (18.4, 18.4),(18.4, 18.4),
                  (50, 250),(50, 250), (250, 50), (250,50)] 
  
    n_pixels = [(1152,576),(1152,576),(1152,576),
                (1152,576),(1152,576),(1152,576),
                #(336,80),(336,80),#(36,129),
                (336,80),(336,80),(36,129),
                (36,129)]
  
    #z_positions = np.array([0.,38300.,77550.,212550.,249800.,285800.,291500.,135250.])
    z_positions = np.array([0.,38250.,77750.,214450.,251250.,285800.,311500.,311500.,120000.,
                           161500.])
  
    dut_names = ("Tel 6", "Tel 5", "Tel 4",
          "Tel 3", "Tel 2", "Tel 1",
          "FEI4","FEI4","Mono1","Mono2") # Friendly names for plotting
  
    # Generate filenames
    output_folder = os.path.dirname(mono_fname)
            
    ## noise threshold in sigma
    threshold = [2, 2, 2, 2, 2, 2,10,10,100,100]
    
    ## cluster distance in pix or frame
    column_cluster_distance = [3, 3, 3, 3, 3, 3, 2, 2, 2, 2]
    row_cluster_distance = [3, 3, 3, 3, 3, 3, 2, 2, 2, 2]
    frame_cluster_distance = [1, 1, 1, 1, 1, 1, 3, 3, 255, 255]
  
    ##################
    ## Interprete and build_event by TLU 
    import pyBAR_mimosa26_interpreter.simple_interpreter
    print "Interprete M26 data raw-->hit"
    fout=m26_fnames[0][:-3]+'_hit.h5'
    if not is_updated(fout,over_write):        
       pyBAR_mimosa26_interpreter.simple_interpreter.m26_interpreter(m26_fnames,fout,debug=0x8|0x2|0x1)
  
    print "Interprete MONOPIX data raw-->hit"
    fout=mono_fname[:-3]+"_hit.h5"
    if not is_updated(fout,over_write):      
        import monopix_daq.analysis.interpreter
        monopix_daq.analysis.interpreter.interpret_h5(mono_fname,fout,debug=3)
    fout=mono2_fname[:-3]+"_hit.h5"
    if not is_updated(fout,over_write):
        import monopix_daq.analysis.interpreter        
        monopix_daq.analysis.interpreter.interpret_h5(mono2_fname,fout,debug=3+0x20)
  
    ##################
    ## build_event by TLU
    print "Align FEI4 with tlu hit-->tlu"
    fout=m26_fnames[0][:-3]+"_tlu.h5"
    fins=[m26_fnames[0][:-3]+'_hit.h5']
    if not is_updated(fout,over_write,fins=fins):
        import pyBAR_mimosa26_interpreter.simple_fe_builder
        pyBAR_mimosa26_interpreter.simple_fe_builder.build_fe2_h5(fins[0],fout,debug=0x1)
  
    print "Align MONOPIX data with TLU hit-->tlu"
    import monopix_daq.analysis.event_builder2
    fout=mono_fname[:-3]+"_tlu.h5"
    fins=[mono_fname[:-3]+"_hit.h5",
          os.path.abspath(monopix_daq.analysis.event_builder2.__file__)]
    if not is_updated(fout,over_write,fins): 
      monopix_daq.analysis.event_builder2.build_h5(fins[0],fout,debug=4)
    fout=mono2_fname[:-3]+"_tlu.h5"
    fins=[mono2_fname[:-3]+"_hit.h5",
          os.path.abspath(monopix_daq.analysis.event_builder2.__file__)]
    if not is_updated(fout,over_write,fins): 
      monopix_daq.analysis.event_builder2.build_h5(fins[0],fout,debug=4)
    
    print "VETO FEI4 data when MONOPIX is not ready tlu-->vetoed" 
    ## TODO del also from monopix_tlu! 
    ## TODO change order of calculation. make veto_list first then assign TLU
    import monopix_daq.analysis.veto_ref
    fout=m26_fnames[0][:-3]+"_vetoed1.h5"
    fins=[mono_fname[:-3]+"_hit.h5",mono_fname,
          m26_fnames[0][:-3]+"_tlu.h5",
          os.path.abspath(monopix_daq.analysis.veto_ref.__file__)]
    if not is_updated(fout,over_write,fins=fins): 
        fout_tmp=mono2_fname[:-3]+"_ref.h5"
        monopix_daq.analysis.veto_ref.find_veto_h5(fin=fins[0],fout=fout_tmp,fparam=fins[1],fref=fins[2])
        monopix_daq.analysis.veto_ref.veto_event_h5(fins[2],fout_tmp,fout)
    fout=m26_fnames[0][:-3]+"_vetoed2.h5"
    fins=[mono2_fname[:-3]+"_hit.h5",mono2_fname,
          m26_fnames[0][:-3]+"_tlu.h5",
          os.path.abspath(monopix_daq.analysis.veto_ref.__file__)]
    if not is_updated(fout,over_write,fins=fins): 
        fout_tmp=mono2_fname[:-3]+"_ref.h5"
        monopix_daq.analysis.veto_ref.find_veto_h5(fin=fins[0],fout=fout_tmp,fparam=fins[1],fref=fins[2])
        monopix_daq.analysis.veto_ref.veto_event_h5(fins[2],fout_tmp,fout)
      
    ##################
    ## Convert
    print "Converte MONOPIX data for clusterizer tlu-->ev"
    fout=data_files[8]
    fins=[mono_fname[:-3]+"_tlu.h5",m26_fnames[0][:-3]+"_tlu.h5"]
    if not is_updated(fout,over_write):
        import monopix_daq.analysis.converter
        monopix_daq.analysis.converter.convert_h5(fins[0],fins[1],fout,
              col_offset=36,col_factor=-1,debug=0)
    fout=data_files[9]
    fins=[mono2_fname[:-3]+"_tlu.h5",m26_fnames[0][:-3]+"_tlu.h5"]
    if not is_updated(fout,over_write): 
        import monopix_daq.analysis.converter
        monopix_daq.analysis.converter.convert_h5(fins[0],fins[1],fout,
              col_offset=36,col_factor=-1,debug=0)
              
    print "Converte FEI4 data for clusterizer vetoed-->ev"
    fout=data_files[6]
    fins=[m26_fnames[0][:-3]+"_vetoed1.h5"]
    if not is_updated(fout,over_write,fins=fins):            
      import pyBAR_mimosa26_interpreter.simple_converter
      pyBAR_mimosa26_interpreter.simple_converter.convert_fe_h5(fins[0],fout,
              col_offset=81,col_factor=-1,tr=True,debug=0)
    fout=data_files[7]
    fins=[m26_fnames[0][:-3]+"_vetoed2.h5"]
    if not is_updated(fout,over_write,fins=fins):            
      import pyBAR_mimosa26_interpreter.simple_converter
      pyBAR_mimosa26_interpreter.simple_converter.convert_fe_h5(fins[0],fout,
              col_offset=81,col_factor=-1,tr=True,debug=0)
                  
    print "Align M26 data with mframe and convert hit-->mframe"
    import pyBAR_mimosa26_interpreter.simple_converter_mframe
    fins=[m26_fnames[0][:-3]+'_hit.h5',
          os.path.abspath(pyBAR_mimosa26_interpreter.simple_converter_mframe.__file__)]
    for i in range(1,7):
        fout=m26_fnames[0][:-3]+'_mframe%d.h5'%i
        if not is_updated(fout,over_write,fins=fins):                
            pyBAR_mimosa26_interpreter.simple_converter_mframe.convert_mframe_m26_h5(fins[0],fout,plane=i,debug=0)
                        
    ##################################
    ## Find noisy pixel
    for i, data_file in enumerate(data_files):
        fins=[data_file]
        fout=data_file[:-3]+'_noisy_pixel_mask.h5'
        if not is_updated(fout,over_write,fins): 
            hit_analysis.generate_pixel_mask(input_hits_file=fins[0],
                n_pixel=n_pixels[i],
                pixel_mask_name='NoisyPixelMask',
                pixel_size=pixel_size[i],
                threshold=threshold[i],
                dut_name=dut_names[i],
                chunk_size=499999)
  
    ##################################
    ## Clusterize and merge files
    for i, data_file in enumerate(data_files[:]):
        fins=[data_file, data_file[:-3]+'_noisy_pixel_mask.h5']
        fout=os.path.splitext(input_cluster_files[i])[0] + '_clustered.h5'
        if not is_updated(fout,over_write,fins):
            hit_analysis.cluster_hits(input_hits_file=fins[0],input_noisy_pixel_mask_file=fins[1],
                #min_hit_charge=0,
                #max_hit_charge=0xFFFF,
                column_cluster_distance=column_cluster_distance[i],
                row_cluster_distance=row_cluster_distance[i],
                frame_cluster_distance=frame_cluster_distance[i],
                dut_name=dut_names[i])
  
    ## make Correlation plots (FEI4-MONO)
    fout=os.path.join(output_folder,'Correlation_duts.h5')
    fins=[input_cluster_files[7],input_cluster_files[8],input_cluster_files[9]]
    if not is_updated(fout,over_write,fins=fins):
        dut_alignment.correlate_cluster(input_cluster_files=fins,output_correlation_file=fout,
            n_pixels=[n_pixels[7],n_pixels[8],n_pixels[9]],
            pixel_size=[pixel_size[7],pixel_size[8],pixel_size[9]],
            dut_names=[dut_names[7],dut_names[8],dut_names[9]])
  
    ## Merge files
    fout=os.path.join(output_folder,'Merged6.h5')
    fins=[m26_fnames[0][:-3]+'_mframe%d_clustered.h5'%i for i in [6,5,4,3,2,1]]
    if not is_updated(fout,over_write,fins=fins):                 
        dut_alignment.merge_cluster_data(input_cluster_files=fins,output_merged_file=fout,
            n_pixels=n_pixels[:6],
            pixel_size=pixel_size[:6],
            chunk_size=499999)
    import monopix_daq.analysis.data_reducer    
    fout=os.path.join(output_folder,'Merged6_small.h5')
    fins=[os.path.join(output_folder,'Merged6.h5'),
          os.path.abspath(monopix_daq.analysis.data_reducer.__file__)]
    if not is_updated(fout,over_write,fins=fins):
        monopix_daq.analysis.data_reducer.reduce_merge(fin=fins[0],fout=fout)
              
    fout=os.path.join(output_folder,'Merged_dut1.h5')
    fins=[input_cluster_files[6],input_cluster_files[8]]
    if not is_updated(fout,over_write,fins=fins):         
        dut_alignment.merge_cluster_data(input_cluster_files=fins,output_merged_file=fout,
          n_pixels=[n_pixels[6],n_pixels[8]],
          pixel_size=[pixel_size[6],pixel_size[9]],
          chunk_size=499999)
          
    fout=os.path.join(output_folder,'Merged_dut2.h5')
    fins=[input_cluster_files[7],input_cluster_files[9]]
    if not is_updated(fout,over_write,fins=fins):          
        dut_alignment.merge_cluster_data(input_cluster_files=fins,output_merged_file=fout,
          n_pixels=[n_pixels[7],n_pixels[9]],
          pixel_size=[pixel_size[7],pixel_size[9]],
          chunk_size=499999)
                   
    ##################################
    ## Align telescope planes
    import monopix_daq.analysis.alignment_tel
    fout=os.path.join(output_folder,"MyAlignment6.npy")
    fins=[os.path.join(output_folder,'Merged6_small.h5'),
          os.path.abspath(monopix_daq.analysis.alignment_tel.__file__)] 
    if not is_updated(fout,over_write,fins=fins):
        fout_tmp=os.path.join(output_folder,"MySingleTrack6.h5")
        monopix_daq.analysis.alignment_tel.search_track(fin=fins[0],fout=fout_tmp)
        monopix_daq.analysis.alignment_tel.alignment(fin=fout_tmp,fout=fout,
            z_positions=z_positions[:6])

    import monopix_daq.analysis.apply_alignment
    fout=os.path.join(output_folder,"MyAligned6.h5")
    fins=[os.path.join(output_folder,'Merged6_small.h5'),
          os.path.join(output_folder,"MyAlignment6.npy"),
          os.path.abspath(monopix_daq.analysis.alignment_tel.__file__)] 
    if not is_updated(fout,over_write,fins=fins):
        monopix_daq.analysis.apply_alignment.apply_alignment(fin=fins[0],fparam=fins[1],fout=fout)
              
    ##################################
    ## Find track and assign a new event_number based on TLU
    import monopix_daq.analysis.find_track_tel
    fout=os.path.join(output_folder,"MyTrackCandidates6.h5")
    fins=[os.path.join(output_folder,"MyAligned6.h5")]
    if not os.path.exists(fout):
        monopix_daq.analysis.find_track_tel.find_track(fin=fins[0],fout=fout)
        
    fout=os.path.join(output_folder,"MyTrack6.h5")
    fins=[os.path.join(output_folder,"MyTrackCandidates6.h5"), 
          os.path.abspath(monopix_daq.analysis.find_track_tel.__file__)]      
    if not is_updated(fout,over_write,fins=fins):
        monopix_daq.analysis.find_track_tel.find_good_track2(fin=fins[0],fout=fout)

    import monopix_daq.analysis.merge_track_and_dut    
    fout=os.path.join(output_folder,'MyTrack6_ev.h5')
    fins=[os.path.join(output_folder,'MyTrack6.h5'), 
          m26_fnames[0][:-3]+"_hit.h5",
          os.path.abspath(monopix_daq.analysis.track_event_builder.__file__)]      
    if not is_updated(fout,over_write,fins=fins): 
        monopix_daq.analysis.track_event_builder.build_h5(
            fin=fins[0],frefs=fins[2],fout=fout)
          
    import monopix_daq.analysis.merge_track_and_dut    
    fout=os.path.join(output_folder,'Merged_track1.h5')
    fins=[os.path.join(output_folder,'Merged_dut1.h5'), 
          os.path.join(output_folder,"MyTrack6_ev.h5"),
          os.path.abspath(monopix_daq.analysis.merge_track_and_dut.__file__)]      
    if not is_updated(fout,over_write,fins=fins):   
        monopix_daq.analysis.merge_track_and_dut.merge(fin=fins[0],fref=fins[1],fout=fout)
   
    fout=os.path.join(output_folder,'Merged_track2.h5')
    fins=[os.path.join(output_folder,'Merged_dut2.h5'), 
          os.path.join(output_folder,"MyTrack6_ev.h5"),
          os.path.abspath(monopix_daq.analysis.merge_track_and_dut.__file__)]      
    if not is_updated(fout,over_write,fins=fins):   
        monopix_daq.analysis.merge_track_and_dut.merge(fin=fins[0],fref=fins[1],fout=fout)
          
    ##################################
    ## Align DUT and find track
    import monopix_daq.analysis.alignment_dut    
    fout=os.path.join(output_folder,"MyAlignment_dut1.npy")
    fins=[os.path.join(output_folder,"Merged_track1.h5"), 
          os.path.abspath(monopix_daq.analysis.alignment_dut.__file__)]
    if not is_updated(fout,over_write,fins=fins):               
        monopix_daq.analysis.alignment_dut .align_dut(fin=fins[0],fout=fout,
            z_positions=[z_positions[6],z_positions[8]])
     
    fout=os.path.join(output_folder,"MyAlignment_dut2.npy")
    fins=[os.path.join(output_folder,"Merged_track2.h5"), 
          os.path.abspath(monopix_daq.analysis.alignment_dut.__file__)]
    if not is_updated(fout,over_write,fins=fins):   
        monopix_daq.analysis.alignment_dut.align_dut(fin=fins[0],fout=fout,
            z_positions=[z_positions[7],z_positions[9]])
    
    import monopix_daq.analysis.find_track_dut      
    fout=os.path.join(output_folder,"MyTrack_dut1.h5")
    fins=[os.path.join(output_folder,"Merged_track1.h5"), 
          os.path.join(output_folder,"MyAlignment_dut1.npy"),
          os.path.abspath(monopix_daq.analysis.find_track_dut.__file__)]
    if not is_updated(fout,over_write,fins=fins):                     
        monopix_daq.analysis.find_track_dut.find_track_dut(fin=fins[0],fparam=fins[1],fout=fout)
        
    fout=os.path.join(output_folder,"MyTrack_dut2.h5")
    fins=[os.path.join(output_folder,"Merged_track2.h5"), 
          os.path.join(output_folder,"MyAlignment_dut2.npy"),
          os.path.abspath(monopix_daq.analysis.find_track_dut.__file__)]
    if not is_updated(fout,over_write,fins=fins):        
        monopix_daq.analysis.find_track_dut.find_track_dut(fin=fins[0],fparam=fins[1],fout=fout)
        
if __name__ == '__main__':  # Main entry point is needed for multiprocessing under windows
      import sys
      if len(sys.argv) > 2:
          mono1_fname=sys.argv[1]
          mono2_fname=sys.argv[2]
          m26_fnames=sys.argv[3:]
      elif len(sys.argv)==1:
          print "testbeam.py <mono1> <mono2> <m26> [m26_1]"
          print "testbeam.py <run>"
      elif len(sys.argv)==2:
          run=sys.argv[1]
          datdir="/sirrush/thirono/testbeam/2017-11-08/run%s"%run      
          m26_fnames=[]
          for f in np.sort(os.listdir(datdir)):
              if "monopix_mio3_2" in f and "_simple_scan.h5" in f:
                  mono2_fname=os.path.join(datdir,f)
              elif "monopix_mio3_1" in f and "_simple_scan.h5" in f:
                  mono1_fname=os.path.join(datdir,f)
              elif "%s_elsa_20171108_m26_telescope_scan.h5"%run == f \
                or "%s_elsa_20171108_m26_telescope_scan_1.h5"%run == f \
                or "%s_elsa_20171108_m26_telescope_scan_2.h5"%run == f \
                or "%s_elsa_20171108_m26_telescope_scan_3.h5"%run == f \
                or "%s_elsa_20171108_m26_telescope_scan_4.h5"%run == f: ##TODO be better _elsa_20171108
                  m26_fnames.append(os.path.join(datdir,f))
                  
      run_analysis(m26_fnames,mono1_fname,mono2_fname,over_write=False)
