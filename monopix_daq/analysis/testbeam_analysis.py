''' This example investigates the efficiency of a radiation hard DMAP sensor.

    It is a prototype called Monopix.
    A Mimosa26 + ATLAS-FE-I4 telescope (named Anemone) is used that is read out
    with pyBAR.
'''

import os
import logging
import numpy as np
import tables as tb
from numba import njit

from testbeam_analysis import hit_analysis
from testbeam_analysis import dut_alignment
from testbeam_analysis import track_analysis
from testbeam_analysis import result_analysis
from testbeam_analysis.tools import data_selection


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - [%(levelname)-8s] (%(threadName)-10s) %(message)s")


def run_analysis(mono_fname,m26_fnames):

  # Pixel dimesions and matrix size of the DUTs (hori,vert)
  pixel_size = [(18.4, 18.4), (18.4, 18.4),(18.4, 18.4),
                (18.4, 18.4), (18.4, 18.4),(18.4, 18.4),
                (50, 250), (250, 50)] 

  n_pixels = [(1152,576),(1152,576),(1152,576),
              (1152,576),(1152,576),(1152,576),
              (336,80),(36,129)]

  z_positions = np.array([0.,38300.,77550.,212550.,249800.,285800.,291500.,135250.])

  dut_names = ("Tel 6", "Tel 5", "Tel 4",
        "Tel 3", "Tel 2", "Tel 1",
        "FEI4","Mono") # Friendly names for plotting

  # Generate filenames
  output_folder = os.path.dirname(mono_fname)

  data_files = [m26_fnames[0][:-3]+'_ev6.h5',
        m26_fnames[0][:-3]+'_ev5.h5',
        m26_fnames[0][:-3]+'_ev4.h5',
        m26_fnames[0][:-3]+'_ev3.h5',
        m26_fnames[0][:-3]+'_ev2.h5',
        m26_fnames[0][:-3]+'_ev1.h5',
        m26_fnames[0][:-3]+'_ev.h5',
        mono_fname[:-3]+"_ev.h5"] 
  input_cluster_files = [os.path.splitext(data_file)[0] + '_clustered.h5'
                         for data_file in data_files]

  ##################
  ## Interprete and build_event by TLU 
  if True:
    import monopix_daq.analysis.fei4_interpreter
    for f in m26_fnames:
        monopix_daq.analysis.fei4_interpreter.analyze_raw_data(f,f[:-3] + "_interpreted.h5")
    import monopix_daq.analysis.interpreter
    monopix_daq.analysis.interpreter.interpret_h5(mono_fname,mono_fname[:-3]+"_hit.h5",debug=3)
    import monopix_daq.analysis.event_builder
    monopix_daq.analysis.event_builder.build_h5(mono_fname[:-3]+"_hit.h5",mono_fname[:-3]+"_tlu.h5")

    import monopix_daq.analysis.veto_ref
    m26_inters=[]
    for f in m26_fnames:
        m26_inters.append(f[:-3]+"_interpreted.h5")
    monopix_daq.analysis.veto_ref.find_veto_h5(mono_fname,mono_fname[:-3]+"_hit.h5",mono_fname[:-3]+"_ref.h5")
    monopix_daq.analysis.veto_ref.veto_event_h5(m26_inters,mono_fname[:-3]+"_ref.h5",m26_fnames[0][:-3]+"_vetoed.h5")

  ##################
  ## Convert
  if True:
    import monopix_daq.analysis.converter
    monopix_daq.analysis.converter.convert_h5(mono_fname[:-3]+"_tlu.h5",m26_fnames[0][:-3]+"_vetoed.h5",mono_fname[:-3]+"_ev.h5",
            col_offset=36,col_factor=-1,debug=0)

    import pyBAR_mimosa26_interpreter.simple_converter
    pyBAR_mimosa26_interpreter.simple_converter.convert_fe_h5(m26_fnames[0][:-3]+"_vetoed.h5",m26_fnames[0][:-3]+"_ev.h5",
            col_offset=81,col_factor=-1,tr=True,debug=0)

    for i, hit_file in enumerate(data_files):
          hit_analysis.check_file(input_hits_file=hit_file, n_pixel=n_pixels[i])

  ##################################
  ## Find noisy pixel
  if True:
    # Generate noisy pixel mask for all DUTs
    threshold = [2, 2, 2, 2, 2, 2,10,1000]
    for i, data_file in enumerate(data_files):
        hit_analysis.generate_pixel_mask(
            input_hits_file=data_file,
            n_pixel=n_pixels[i],
            pixel_mask_name='NoisyPixelMask',
            pixel_size=pixel_size[i],
            threshold=threshold[i],
            dut_name=dut_names[i])

  ##################################
  ## Clusterize and merge files
  if True:
    # Cluster hits from all DUTs
    column_cluster_distance = [3, 3, 3, 3, 3, 3, 2, 2]
    row_cluster_distance = [3, 3, 3, 3, 3, 3, 1, 2]
    frame_cluster_distance = [1, 1, 1, 1, 1, 1, 3, 255]
    for i, data_file in enumerate(data_files):
        hit_analysis.cluster_hits(
            input_hits_file=data_file,
            input_noisy_pixel_mask_file=data_file[:-3]+'_noisy_pixel_mask.h5',
            #min_hit_charge=0,
            #max_hit_charge=0xFFFF,
            column_cluster_distance=column_cluster_distance[i],
            row_cluster_distance=row_cluster_distance[i],
            frame_cluster_distance=frame_cluster_distance[i],
            dut_name=dut_names[i])
    # Merge the cluster tables to one merged table aligned at the event number
    dut_alignment.merge_cluster_data(
        input_cluster_files=input_cluster_files,
        output_merged_file=os.path.join(output_folder,
                                        'Merged.h5'),
        n_pixels=n_pixels,
        pixel_size=pixel_size)

  ####################################
  ## Pre alignment
  if True:
    # Correlate the row / column of each DUT
    dut_alignment.correlate_cluster(
        input_cluster_files=input_cluster_files,
        output_correlation_file=os.path.join(output_folder,
                                             'Correlation.h5'),
        n_pixels=n_pixels,
        pixel_size=pixel_size,
        dut_names=dut_names)

    # Create prealignment relative to the first DUT from the correlation data
    dut_alignment.prealignment(
        input_correlation_file=os.path.join(output_folder,
                                            'Correlation.h5'),
        output_alignment_file=os.path.join(output_folder,
                                           'Alignment.h5'),
        z_positions=z_positions,
        pixel_size=pixel_size,
        dut_names=dut_names,
        fit_background=True,
        non_interactive=True,
        iterations=5)
    dut_alignment.apply_alignment(
        input_hit_file=os.path.join(output_folder,
                                    'Merged.h5'),
        input_alignment_file=os.path.join(output_folder,
                                          'Alignment.h5'),
        output_hit_file=os.path.join(output_folder,
                                     'Tracklets_prealigned.h5'),
        force_prealignment=True)
    track_analysis.find_tracks(
        input_tracklets_file=os.path.join(output_folder,
                                          'Tracklets_prealigned.h5'),
        input_alignment_file=os.path.join(output_folder,
                                          'Alignment.h5'),
        output_track_candidates_file=os.path.join(
            output_folder,
            'TrackCandidates_prealignment.h5'))


  ##############################
  ## Alignment
  if True:
    data_selection.select_hits(
        hit_file=os.path.join(output_folder,
                              'TrackCandidates_prealignment.h5'),
        track_quality=0b00111111,
        track_quality_mask=0b00111111)

    # Do an alignment step with the track candidates, corrects rotations and is therefore much more precise than simple prealignment
    dut_alignment.alignment(
        input_track_candidates_file=os.path.join(
            output_folder, 'TrackCandidates_prealignment_reduced.h5'),
        input_alignment_file=os.path.join(
            output_folder, 'Alignment.h5'),
        # Order of combinaions of planes to align, one should start with high resoultion planes (here: telescope planes)
        align_duts=[[0,1,2,3,4,5],  # align the telescope planes first
                    [6],  # align the time reference after the telescope alignment
                    [7]],  # align the DUT last and not with the reference since it is rather small and would make the time reference alinmnt worse
        # The DUTs to be used in the fit, always just the high resolution Mimosa26 planes used
        selection_fit_duts=[0, 1, 2, 3, 4, 5],
        # The DUTs to be required to have a hit for the alignment
        selection_hit_duts=[[0, 1, 2, 3, 4, 5, 6],  # Take tracks with time reference hit
                            [0, 1, 2, 3, 4, 5, 6],
                            [0, 1, 2, 3, 4, 5, 6, 7]],
        # The required track quality per alignment step and DUT
        selection_track_quality=[[1, 1, 1, 1, 1, 1, 0],  # Do not require a good hit in the time refernce
                                 [1, 1, 1, 1, 1, 1, 1],
                                 [1, 1, 1, 1, 1, 1, 1, 0]],  # Do not require a good hit in the small DUT
        initial_rotation=[[0., 0., 0.],
                          [0., 0., 0.],
                          [0., 0., 0.],
                          [0., 0., 0.],
                          [0., 0, 0.],
                          [0., 0, 0.],
                          [0., 0, 0.],
                          [0., 0, 0.]],
        initial_translation=[[0., 0, 0.],
                             [0., 0, 0.],
                             [0., 0, 0.],
                             [0., 0, 0.],
                             [0., 0., 0.],
                             [0., 0, 0.],
                             [0., 0, 0.],
                             [0., 0, 0.]],
        n_pixels=n_pixels,
        # Do the alignment only on a subset of data, for reasonable run time
        use_n_tracks=200000,
        pixel_size=pixel_size,
        plot=True)  # Show result residuals after alignment
    dut_alignment.apply_alignment(
        input_hit_file=os.path.join(output_folder, 'Merged.h5'),
        input_alignment_file=os.path.join(output_folder, 'Alignment.h5'),
        output_hit_file=os.path.join(output_folder, 'Tracklets.h5'))
    track_analysis.find_tracks(
        input_tracklets_file=os.path.join(output_folder,'Tracklets.h5'),
        input_alignment_file=os.path.join(output_folder, 'Alignment.h5'),
        output_track_candidates_file=os.path.join( output_folder,'TrackCandidates.h5'),
        chunk_size=10000) 

  if False:  ## faster
    dut_alignment.apply_alignment(
        input_hit_file=os.path.join(output_folder, 'TrackCandidates_prealignment_reduced.h5'),
        input_alignment_file=os.path.join(output_folder, 'Alignment.h5'),
        # This is the new not aligned but preselected merged data file to apply (pre-) alignment on
        output_hit_file=os.path.join(output_folder, 'Merged_small.h5'),
        inverse=True,
        force_prealignment=True)
    dut_alignment.apply_alignment(
        input_hit_file=os.path.join(output_folder, 'Merged_small.h5'),
        input_alignment_file=os.path.join(output_folder, 'Alignment.h5'),
        output_hit_file=os.path.join(output_folder, 'TrackCandidates_small.h5'))

  ##############################
  ## Fit tracks and caluculate efficinecy
  if True: ## more data
    # Fit track using alignment
    track_analysis.fit_tracks(
        input_track_candidates_file=os.path.join(output_folder,
                                                 'TrackCandidates.h5'),
        input_alignment_file=os.path.join(output_folder,
                                          'Alignment.h5'),
        output_tracks_file=os.path.join(output_folder,
                                        'Tracks.h5'),
        fit_duts=[3,6,7],
        selection_hit_duts=[0, 1, 2, 3, 4, 5, 6, 7],
        selection_fit_duts=[0, 1, 2, 3, 4, 5],
        # Take all tracks with any hits, but good time reference hits
        selection_track_quality=0, #[1,1,1,1,1,1,0,0],
        min_track_distance=True)

    # Create unconstrained residuals with aligned data
    result_analysis.calculate_residuals(
        input_tracks_file=os.path.join(output_folder, 'Tracks.h5'),
        input_alignment_file=os.path.join(output_folder, 'Alignment.h5'),
        output_residuals_file=os.path.join(output_folder, 'Residuals.h5'),
        n_pixels=n_pixels,
        pixel_size=pixel_size)

    # Calculate efficiency with aligned data
    result_analysis.calculate_efficiency(
        input_tracks_file=os.path.join(output_folder,
                                       'Tracks.h5'),
        input_alignment_file=os.path.join(output_folder,
                                          'Alignment.h5'),
        output_efficiency_file=os.path.join(output_folder,
                                            'Efficiency.h5'),
        bin_size=[(50, 50)] * 8,
        pixel_size=pixel_size,
        n_pixels=n_pixels,
        minimum_track_density=1,
        max_chi2=1000.,
        sensor_size=[(pixel_size[i][0] * n_pixels[i][0],
                      pixel_size[i][1] * n_pixels[i][1]) for i in range(8)])

if __name__ == '__main__':  # Main entry point is needed for multiprocessing under windows
    import sys
    if len(sys.argv) > 2:
        mono_fname=sys.argv[1]
        m26_fnames=sys.argv[2:]
    else:
        mono_fname="/sirrush/thirono/testbeam/2017-09-20/run151/m2_151_170926-205321.h5"
        m26_fnames=["/sirrush/thirono/testbeam/2017-09-20/run151/151_20170920_sps_m26_telescope_scan.h5",
                "/sirrush/thirono/testbeam/2017-09-20/run151/151_20170920_sps_m26_telescope_scan_1.h5"]
    run_analysis(mono_fname,m26_fnames)
