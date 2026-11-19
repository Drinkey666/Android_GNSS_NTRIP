"""Publish the live solution first, using the separate file-assisted filter only inside a verified OSB gap."""
import argparse
import csv
import os
import tempfile
from contextlib import contextmanager
from decimal import Decimal
from itertools import groupby, zip_longest
from pathlib import Path

def stamp(row):
    return int(row['week']),Decimal(row['tow'])

def same_time(a,b):
    return a[0]==b[0] and abs(a[1]-b[1])<Decimal('0.00000001')

@contextmanager
def new_output(path):
    if path.exists():
        raise FileExistsError(path)
    stream=tempfile.NamedTemporaryFile(mode='w',newline='',dir=path.parent,delete=False)
    temp=Path(stream.name)
    try:
        with stream:
            yield stream
        os.link(temp,path)
    finally:
        temp.unlink(missing_ok=True)

def recover(primary, gap, diagnostics, satellite_log, output):
    with primary.open(newline='') as p, gap.open(newline='') as g, diagnostics.open(newline='') as d, satellite_log.open(newline='') as s, new_output(output) as o:
        live,backup,gate=csv.DictReader(p),csv.DictReader(g),csv.DictReader(d)
        writer=csv.DictWriter(o,fieldnames=live.fieldnames+['solution_source'])
        writer.writeheader()
        pending=iter(groupby(csv.reader(s),key=lambda r:(int(r[0]),Decimal(r[1]))))
        current=next(pending,None)
        previous=None
        for a,b,c in zip_longest(live,backup,gate):
            if any(row is None for row in (a,b,c)):
                raise ValueError('Epoch counts differ')
            k=stamp(a)
            if (previous is not None and k<=previous) or not all(same_time(k,stamp(row)) for row in (b,c)):
                raise ValueError('Epoch order or timestamp mismatch')
            previous=k
            stalled=False
            if current and same_time(k,current[0]):
                stalled=any(row[3]=='WHU_OSB_ESTIMATE_NOT_ADVANCING' for row in current[1])
                current=next(pending,None)
            elif current and current[0]<k:
                raise ValueError('Unmatched satellite audit')
            use_file=(a['Q']!='6' and b['Q']=='6' and c['corrections_ready']=='0' and stalled)
            row=dict(b if use_file else a)
            row['solution_source']='WHU_FILE_CODE_GAP' if use_file else 'LIVE'
            writer.writerow(row)
        if current:raise ValueError('Unmatched trailing satellite audit')
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('primary','gap','diagnostics','satellite_log','output'):ap.add_argument(name,type=Path)
    args=ap.parse_args()
    recover(**vars(args))
