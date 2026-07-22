#!/usr/bin/env python3
"""DDTM-QAS G1 Cross-Language Test Vector Generator (v5).

Generates 20 test vectors. Binary data in .bin files; SHA-256 in JSON.
"""
from __future__ import annotations
import hashlib, json, struct, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = ROOT / "experiments" / "vectors"
ROW_BYTES = 548
FC = 128


def enc(buf, off, rid, valid, label, ts, feats, mask):
    struct.pack_into('<HQBbQ16s', buf, off, 1, rid, valid, label, ts, mask)
    o = off + 36
    for i in range(FC):
        v = max(-2147483648, min(2147483647, feats[i]))
        struct.pack_into('<i', buf, o, v); o += 4
    return o

def fv(v): return [v]*FC

def h(b): return hashlib.sha256(b).hexdigest()

def main():
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)
    out = {"version":5,"description":"G1 cross-language test vectors (20 cases)",
           "schema_hash":"feedc0de00000000000000000000000000000000000000000000000000beef",
           "dataset_version":"1","feature_count":FC,"total_cases":20,"test_cases":[]}
    m0 = bytes(16); t0 = time.time()

    def add(nm, nr, blob):
        out["test_cases"].append({"name":nm,"row_count":nr,"blob_size":len(blob),"blob_sha256":h(blob)})
        (VECTORS_DIR / f"{nm}.bin").write_bytes(blob)

    b = bytearray(ROW_BYTES)
    enc(b,0,0,1,1,1700000000,fv(0),m0); add("tc01_all_zeros",1,bytes(b))
    enc(b,0,0,1,-1,1700000000,[65536]+[0]*127,m0); add("tc02_negative_label",1,bytes(b))
    m3=bytearray(16);m3[0]|=1;m3[5]|=4
    enc(b,0,0,1,1,1700000000,[131072]+[0]*127,bytes(m3)); add("tc03_missing_features",1,bytes(b))
    enc(b,0,131071,0,0,0,fv(0),m0); add("tc04_padding_row",1,bytes(b))

    b5=bytearray(ROW_BYTES*4)
    for i in range(4):
        enc(b5,i*ROW_BYTES,i,1,1 if i%2==0 else -1,1700000000+i,[65536*(i+1)]+[0]*127,m0)
    add("tc05_four_row_tree",4,bytes(b5))

    b6=bytearray(ROW_BYTES*2)
    enc(b6,0,0,1,1,1700000000,[65536]+[0]*127,m0)
    enc(b6,ROW_BYTES,1,1,-1,1700000001,[131072]+[0]*127,m0)
    add("tc06_row_order",2,bytes(b6))

    enc(b,0,42,1,1,1700000000,[(i-64)*100 for i in range(FC)],m0)
    add("tc07_audit_test",1,bytes(b))
    enc(b,0,0,1,1,1700000000,fv(2147483647),m0); add("tc08_int32_max",1,bytes(b))
    enc(b,0,0,1,-1,1700000000,fv(-2147483648),m0); add("tc09_int32_min",1,bytes(b))
    enc(b,0,0,1,1,1700000000,[65536]+[65535]*127,m0); add("tc10_q16_pos_boundary",1,bytes(b))
    enc(b,0,0,1,-1,1700000000,[-65536]+[-65535]*127,m0); add("tc11_q16_neg_boundary",1,bytes(b))
    enc(b,0,0,1,1,1700000000,fv(2147483647),m0); add("tc12_nan_sentinel",1,bytes(b))
    enc(b,0,0,1,1,1700000000,[2147483647,-2147483648]*64,m0); add("tc13_infinity_clamp",1,bytes(b))

    b14=bytearray(ROW_BYTES*2); f14=[100000]+[0]*127
    enc(b14,0,0,1,1,1700000000,f14,m0); enc(b14,ROW_BYTES,99999,1,1,1700000000,f14,m0)
    add("tc14_same_data_diff_rowid",2,bytes(b14))

    b15=bytearray(ROW_BYTES*2); f15=fv(42)
    enc(b15,0,0,1,1,1700000000,f15,m0); enc(b15,ROW_BYTES,0,1,1,1700000000,f15,m0)
    add("tc15_identical_rows",2,bytes(b15))

    b16=bytearray(ROW_BYTES*2)
    enc(b16,0,0,1,1,1700000000,fv(0),m0)
    enc(b16,ROW_BYTES,1,1,1,1700000000,[0]*63+[1]+[0]*64,m0)
    add("tc16_single_bit_mutation",2,bytes(b16))

    b17=bytearray(ROW_BYTES*2); f17=fv(65536)
    enc(b17,0,0,1,1,1700000000,f17,m0); enc(b17,ROW_BYTES,1,1,-1,1700000000,f17,m0)
    add("tc17_label_mutation",2,bytes(b17))

    print("TC18 (100K)...",flush=True)
    n18=100000;b18=bytearray(ROW_BYTES*n18)
    for i in range(n18):
        enc(b18,i*ROW_BYTES,i,1,1 if i%2==0 else -1,1700000000+i,[65536*(i+1)]+[0]*127,m0)
    add("tc18_large_100k",n18,bytes(b18))

    print("TC19 (131K)...",flush=True)
    n19=131072;b19=bytearray(ROW_BYTES*n19)
    for i in range(1000):
        enc(b19,i*ROW_BYTES,i,1,1,1700000000+i,[65536*(i+1)]+[0]*127,m0)
    for i in range(1000,n19):
        enc(b19,i*ROW_BYTES,i,0,0,0,[0]*FC,m0)
    add("tc19_capacity_padding",n19,bytes(b19))

    b20=bytearray(ROW_BYTES*2); m20=bytearray(16);m20[0]|=1
    enc(b20,0,0,1,1,1700000000,fv(0),m0)
    enc(b20,ROW_BYTES,1,1,1,1700000000,fv(0),bytes(m20))
    add("tc20_missing_vs_zero",2,bytes(b20))

    json.dump(out,(VECTORS_DIR/"g1_vectors.json").open("w"),indent=2)
    e=time.time()-t0
    tr=sum(c["row_count"] for c in out["test_cases"])
    tb=sum(c["blob_size"] for c in out["test_cases"])
    print(f"\n{len(out['test_cases'])} cases, {tr:,} rows, {tb:,} bytes in {e:.1f}s")
    for c in out["test_cases"]:
        print(f"  {c['name']}: {c['row_count']} rows, {c['blob_size']:,}B, SHA256={c['blob_sha256'][:16]}...")

if __name__=="__main__":main()
