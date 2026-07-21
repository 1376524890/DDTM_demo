#!/usr/bin/env python3
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--rate",type=float,required=True); ap.add_argument("--type",choices=["label-flip","gaussian","missing","duplicate"],required=True); ap.add_argument("--seed",type=int,default=20260721); args=ap.parse_args()
    z=np.load(args.input); x=z["x"].copy(); y=z["y"].copy(); idx=np.arange(len(x)); rng=np.random.default_rng(args.seed); chosen=rng.choice(idx,max(1,round(len(idx)*args.rate)),replace=False)
    if args.type=="label-flip": y[chosen]*=-1
    elif args.type=="gaussian": x[chosen]+=rng.normal(0,2.0,size=x[chosen].shape).astype(np.float32)
    elif args.type=="missing":
        mask=rng.random(x[chosen].shape)<0.25; block=x[chosen]; block[mask]=0; x[chosen]=block
    else:
        source=rng.choice(idx,len(chosen),replace=True); x[chosen]=x[source]; y[chosen]=y[source]
    np.savez_compressed(args.output,x=x,y=y,original_index=z["original_index"],contaminated_indices=chosen)
if __name__=="__main__":main()
