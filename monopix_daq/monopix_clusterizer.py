from pixel_clusterizer.clusterizer import HitClusterizer
from testbeam_analysis.tools import analysis_utils

import tables as tb
import numpy as np

def end_of_cluster_function(hits, clusters, cluster_size, cluster_hit_indices, cluster_index, cluster_id, charge_correction, noisy_pixels, disabled_pixels, seed_hit_index):
    min_col = hits[cluster_hit_indices[0]].column
    max_col = hits[cluster_hit_indices[0]].column
    min_row = hits[cluster_hit_indices[0]].row
    max_row = hits[cluster_hit_indices[0]].row

    for i in cluster_hit_indices[1:]:
        if i < 0:  # Not used indeces = -1
            break
        if hits[i].column < min_col:
            min_col = hits[i].column
        if hits[i].column > max_col:
            max_col = hits[i].column
        if hits[i].row < min_row:
            min_row = hits[i].row
        if hits[i].row > max_row:
            max_row = hits[i].row

    clusters[cluster_index].seed_charge = hits[seed_hit_index].charge
    clusters[cluster_index].n_cols = int(max_col - min_col + 1)
    clusters[cluster_index].n_rows = int(max_row - min_row + 1)


def order_hits_by_event_number(hit_array, result):
    sel = hit_array["le"] > hit_array["te"]
    result["event_number"][sel] = np.arange(np.count_nonzero(sel))
    mask = ~sel
    result['event_number'][mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), result['event_number'][~mask])
    
    result['frame'][:] = result['le'][:]
    
    result['charge'][:] = result['te'][:] - result['le'][:]
    change = result['charge'] < 0
    result['charge'][change] += 255
    
    return result

def order_hits_by_event_number2(hit_array, resulta):
    
    result = np.copy(resulta)
    time_order = np.array(hit_array["le"][:], dtype = np.uint32)
    
    positions = np.concatenate([np.array([False]),(np.array([time_order[i] < time_order[i-1] for i in range(1, len(time_order))]))])
    
    addi = np.zeros(time_order.shape, dtype=np.uint32)
    addi[positions] = np.arange(1, len(time_order[positions])+1)
    mask = ~positions
    mask[0] = False
    addi[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), addi[~mask])
    
    time_order += addi*255
    
#    positions_new = np.array([time_order[i] > time_order[i-1] for i in range(1, len(time_order))])
    
    result['le'] = np.array(time_order)
    result['te'] += addi*255

    result['frame'][:] = result['le'][:] 
    
    
    event_numbers_new = np.zeros(result['event_number'].shape)
    sel = np.concatenate([np.array([False]), np.array([time_order[i] - time_order[i-1] > 100 for i in range(1, len(time_order))])])
    event_numbers_new[sel] = np.arange(np.count_nonzero(sel))
    mask = ~sel
    event_numbers_new[mask] = np.interp(np.flatnonzero(mask), np.flatnonzero(~mask), event_numbers_new[~mask])
    result['event_number'] = event_numbers_new
    
    charges = np.array(result['te'], dtype = np.int64) - np.array(result['le'], dtype = np.int64)
    change = charges < 0
    charges[change] += 255
    result['charge'] = charges
    
    return result

def monopix_clusterize_from_source (input_hits_file, output_cluster_file, max_le_distance = 10):
    with tb.open_file(input_hits_file, 'r') as input_file_h5:
        hits = input_file_h5.root.hit_data[:]
        lista = list(hits.dtype.descr)
        lista.pop(0)
        lista[1] = ('le', 'uint32')
        lista[2] = ('te', 'uint32')
        new_dtype = np.dtype([("event_number", 'uint32'), ('frame', 'uint32'), ('column', '<u2')] + lista + [('charge', '<u2')])
        results = np.zeros(shape=hits.shape, dtype=new_dtype)
        for field in hits.dtype.names:
            if field == 'col' or field == 'le':
                continue
            results[field] = np.array(hits[field])
        results['column'] = np.array(hits['col'])
            
        result = order_hits_by_event_number2(hits, results)
        
    cluster_table = None
        
    clusterizer = HitClusterizer(column_cluster_distance=1, row_cluster_distance=2, min_hit_charge=0, max_hit_charge=1000, frame_cluster_distance=max_le_distance)
    clusterizer.add_cluster_field(description=('seed_charge', '<u2'))  # Add an additional field to hold the charge of the seed hit
    clusterizer.add_cluster_field(description=('n_cols', '<u2'))  # Add an additional field to hold the cluster size in x
    clusterizer.add_cluster_field(description=('n_rows', '<u2'))  # Add an additional field to hold the cluster size in y
    clusterizer.set_end_of_cluster_function(end_of_cluster_function)  # Set the new function to the clusterizer
    
    #print dict(result.dtype.descr)
    types = {}
    for k in dict(result.dtype.descr):
        types[k] = k
    
    clusterizer.set_hit_fields(types)
    
    clusterizer.set_hit_dtype(result.dtype)

    #clusterizer.set_cluster_fields(types)

    with tb.open_file(output_cluster_file, 'w') as output_file_h5:
        hits_table = output_file_h5.create_table(output_file_h5.root, name='Hits', description=result.dtype, title='Hits table', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
        hits_table.append(result)
        
        for hitsa, _ in analysis_utils.data_aligned_at_events(hits_table, chunk_size=1000000):
            if not np.all(np.diff(result['event_number']) >= 0):
                raise RuntimeError('The event number does not always increase. The hits cannot be used like this!')
            _, clusters = clusterizer.cluster_hits(hitsa)  # Cluster hits
            if not np.all(np.diff(clusters['event_number']) >= 0):
                raise RuntimeError('The event number does not always increase. The cluster cannot be used like this!')
            if cluster_table is None:
                cluster_table = output_file_h5.create_table(output_file_h5.root, name='Cluster', description=clusters.dtype, title='Cluster table', filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                
            cluster_table.append(clusters)
            


   
if __name__ == "__main__":
    infile = r"../data/test_beam_data/20170426_051939_source_scan.h5"
    outfile = r"../data/test_beam_data/20170426_051939_source_scan_clusterized.h5"
    monopix_clusterize_from_source(infile, outfile)