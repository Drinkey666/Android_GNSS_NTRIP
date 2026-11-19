"""Apply the same-issue archived WHU RTS orbit, clock and biases using the validated file entry."""
import concurrent.futures,importlib.util,sys
from pathlib import Path
D=Path(__file__).resolve().parent; tools=D.parent/'vivo_1852_product_comparison_20261119'
def replay(pair):
    label,aligned=pair
    spec=importlib.util.spec_from_file_location('file_entry_'+label+str(aligned),D/'file_entry.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.OUT=D/label;m.WORK=(m.OUT/'file_aligned_build') if aligned else tools/'file_build'
    if aligned:m.build(True)
    p=D/'products';pref='pride_WUM0MGXRTS_20263230000_01D_'
    args=[p/(pref+tail) for tail in ['05M_ORB.SP3','05S_CLK.CLK','05M_OSB.BIA']]
    args += [p/'BRDC00WRD_S_20263230000_01D_MN.rnx', p/'igs20.atx']
    m.run('FILE_same_start' if aligned else 'FILE',*args)
    print(label,aligned,'complete',flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(4) as ex:list(ex.map(replay,[(x,a) for x in ('2221','2236') for a in (False,True)]))
