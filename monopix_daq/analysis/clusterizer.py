''' Example how to use the clusterizer'''
import numpy as np
import sys,time,os
import tables

import pixel_clusterizer.clusterizer

hit_dtype=np.dtype([("event_number","<i8"),("column","<u2"),("row","<u2"),("charge","<u1"),("frame","<u1")])
cluster_dtype=np.dtype([('event_number', '<i8'), ('ID', '<u2'), ('n_hits', '<u2'), ('charge', '<f4'), 
                        ('seed_column', '<u2'), ('seed_row', '<u2'),('mean_column', '<f4'), ('mean_row', '<f4')])
hit_clustered_dtype=np.dtype([('event_number', '<i8'),('frame', '<u1'),('column', '<u2'),('row', '<u2'),
                        ('charge', '<u2'),('cluster_ID', '<i2'),('is_seed', '<u1'),('cluster_size', '<u2'),
                        ('n_cluster', '<u2')])

def clusterize_h5(fin,fout,n=1000000,debug=0):
    cl = pixel_clusterizer.clusterizer.HitClusterizer()
    cl.set_column_cluster_distance(2)  # cluster distance in columns
    cl.set_row_cluster_distance(2)  # cluster distance in rows
    cl.set_frame_cluster_distance(10)   # cluster distance in time frames
    cl.set_max_hit_charge(13)  # only add hits with charge <= 29
    cl.ignore_same_hits(True)  # Ignore same hits in an event for clustering
    cl.set_hit_dtype(hit_dtype)  # Set the data type of the hits (parameter data types and names)
    hit=np.empty(0,dtype=hit_dtype)
    with tables.open_file(fout, "w") as f_o:
        description=np.zeros((1,),dtype=cluster_dtype).dtype
        hit_table=f_o.create_table(f_o.root,name="Clusters",description=description,title='cluster_data')
        description2=np.zeros((1,),dtype=hit_clustered_dtype).dtype
        hit_table2=f_o.create_table(f_o.root,name="Hits",description=description2,title='hit_data')
        with tables.open_file(fin) as f:
            end=len(f.root.Hits)
            t0=time.time()
            hit_total=0
            start=0
            while start<end:
                tmpend=min(end,start+n)
                hit=np.append(hit,f.root.Hits[start:tmpend])
                if tmpend!=end:
                    last_event=hit[-1]["event_number"]
                    for i in range(1,len(hit)):
                        if hit[len(hit)-i]["event_number"]!=last_event:
                            break
                else:
                    i=0
                buf_out2, buf_out = cl.cluster_hits(hit[:-i])
                hit=hit[len(hit)-1:]
                hit_table.append(buf_out)
                hit_table.flush()
                hit_table2.append(buf_out2)
                hit_table2.flush()
                start=tmpend

if __name__ == "__main__":
    import sys

    fin=sys.argv[1]
    fout=fin[:-5]+"cl.h5"

    clusterize_h5(fin,fout,debug=0,n=1000000)
    print fout
    
