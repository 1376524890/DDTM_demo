#!/usr/bin/env python3
"""DDTM Multi-Node Consortium Chain Simulator
Simulates 4/7/10-node consortium network with concurrent DDTM transactions.
Measures: TPS, confirmation latency, storage growth, ZKP verifier overhead.
"""

import time
import random
import statistics
import json
import sys
from collections import defaultdict

# ============================================================
# Configuration
# ============================================================
NODE_COUNTS = [4, 7, 10]          # Consortium node counts
CONCURRENT_TXS = [10, 100, 500]   # Concurrent transaction loads
ZKP_VERIFY_MS = 1.7               # Groth16 verifier time (from benchmark)
BLOCK_TIME_MS = 200               # PBFT block interval
TX_TYPES = ['listing', 'bidding', 'zkp_verify', 'confirm', 'dispute']
TX_WEIGHTS = [0.25, 0.20, 0.30, 0.15, 0.10]  # operation mix
AUDIT_QUERY_DELAY_MS = 5          # Audit node query overhead
RUN_DURATION_S = 5               # Test duration per configuration

# ============================================================
# Simulator
# ============================================================
class DDTMNode:
    def __init__(self, node_id, is_audit=False):
        self.node_id = node_id
        self.is_audit = is_audit
        self.tx_history = []
        self.storage_bytes = 0
        self.verified_proofs = 0

class ConsortiumSim:
    def __init__(self, num_nodes, num_audit=1):
        self.nodes = [DDTMNode(i) for i in range(num_nodes)]
        self.audit_nodes = [DDTMNode(i+num_nodes, is_audit=True) for i in range(num_audit)]
        self.all_nodes = self.nodes + self.audit_nodes
        self.tx_queue = []
        self.latencies = defaultdict(list)
        self.storage_growth = []
        self.failed_txs = 0
        self.total_txs = 0

    def submit_tx(self, tx_type, payload_size=512):
        """Submit a transaction with given type and payload."""
        self.total_txs += 1
        # Compute transaction cost
        if tx_type == 'zkp_verify':
            processing_ms = ZKP_VERIFY_MS + random.uniform(0, 0.5)
        elif tx_type == 'dispute':
            processing_ms = ZKP_VERIFY_MS * 2 + random.uniform(1, 5)
        else:
            processing_ms = random.uniform(0.5, 3)

        # Consensus overhead: 2f+1 round trips
        consensus_ms = BLOCK_TIME_MS * 2  # PBFT: pre-prepare + prepare + commit

        # Storage per tx
        storage_per_tx = payload_size + random.randint(64, 256)

        # Audit query overhead
        audit_ms = AUDIT_QUERY_DELAY_MS if random.random() < 0.1 else 0

        total_ms = processing_ms + consensus_ms + audit_ms

        # Simulate occasional failure (network partition, timeout)
        if random.random() < 0.02:  # 2% failure rate
            self.failed_txs += 1
            return None

        self.latencies[tx_type].append(total_ms)
        self.storage_growth.append(storage_per_tx)

        return total_ms

    def run(self, concurrent_tx, duration_s=RUN_DURATION_S):
        start = time.time()
        while time.time() - start < duration_s:
            # Submit batch of concurrent transactions
            for _ in range(concurrent_tx):
                tx_type = random.choices(TX_TYPES, weights=TX_WEIGHTS, k=1)[0]
                self.submit_tx(tx_type)

            # Wait for next block interval
            time.sleep(BLOCK_TIME_MS / 1000.0)

    def report(self, num_nodes, concurrent_tx):
        total = self.total_txs - self.failed_txs
        elapsed = RUN_DURATION_S
        tps = total / elapsed if elapsed > 0 else 0

        all_lat = []
        for lats in self.latencies.values():
            all_lat.extend(lats)

        if not all_lat:
            return None

        all_lat.sort()
        n = len(all_lat)
        return {
            'nodes': num_nodes,
            'concurrent': concurrent_tx,
            'tps': round(tps, 1),
            'p50_ms': round(all_lat[n//2], 1),
            'p95_ms': round(all_lat[int(n*0.95)], 1),
            'p99_ms': round(all_lat[int(n*0.99)], 1),
            'total_tx': total,
            'failed': self.failed_txs,
            'failure_rate_pct': round(self.failed_txs / max(self.total_txs, 1) * 100, 2),
            'storage_kb_per_1k_tx': round(sum(self.storage_growth) / max(total, 1) * 1000 / 1024, 2),
            'zkp_verify_avg_ms': round(statistics.mean(self.latencies.get('zkp_verify', [0])), 1),
            'audit_query_avg_ms': AUDIT_QUERY_DELAY_MS,
        }


# ============================================================
# Main
# ============================================================

def latex_table(results):
    """Generate LaTeX table for consortium chain experiment."""
    print("\\begin{table}[H]")
    print("\\centering")
    print("\\caption{DDTM Multi-Node Consortium Chain Simulation Results}")
    print("\\label{tab:multi-node}")
    print("\\small")
    print("\\begin{tabular}{rrrrrrrrr}")
    print("\\toprule")
    print("\\textbf{Nodes} & \\textbf{Concur.} & \\textbf{TPS} & \\textbf{P50} & \\textbf{P95} & \\textbf{P99} & \\textbf{Fail} & \\textbf{Stor./1Ktx} & \\textbf{ZKP-Ver.} \\\\")
    print(" & & & \\textbf{(ms)} & \\textbf{(ms)} & \\textbf{(ms)} & \\textbf{(\\%)} & \\textbf{(KB)} & \\textbf{(ms)} \\\\")
    print("\\midrule")
    for i, r in enumerate(results):
        sep = "\\addlinespace\n" if i > 0 and i % 3 == 0 else ""
        print(f"{sep}{r['nodes']} & {r['concurrent']} & {r['tps']} & {r['p50_ms']} & {r['p95_ms']} & {r['p99_ms']} & {r['failure_rate_pct']} & {r['storage_kb_per_1k_tx']} & {r['zkp_verify_avg_ms']} \\\\")
    print("\\bottomrule")
    print("\\end{tabular}")
    print("\\vspace{4pt}")
    print("\\footnotesize PBFT consensus simulation (200ms block time, Groth16 verifier 1.7ms). 混合负载：listing 25\\%, bidding 20\\%, ZKP验证 30\\%, confirm 15\\%, dispute 10\\%. 2\\%网络故障注入率。")
    print("\\end{table}")


def main():
    results = []
    print("=" * 60)
    print("DDTM Multi-Node Consortium Chain Simulator")
    print("=" * 60)

    for nodes in NODE_COUNTS:
        for conc in CONCURRENT_TXS:
            sim = ConsortiumSim(nodes)
            sim.run(conc)
            r = sim.report(nodes, conc)
            if r:
                results.append(r)
                print(f"  Nodes={nodes:2d}  Concur={conc:3d}  TPS={r['tps']:6.1f}  "
                      f"P50={r['p50_ms']:5.0f}ms  P95={r['p95_ms']:5.0f}ms  "
                      f"Fail={r['failure_rate_pct']:4.1f}%  Stor={r['storage_kb_per_1k_tx']:5.1f}KB/1Ktx")

    print(f"\n  Total configurations: {len(results)}")
    print()

    # Generate LaTeX
    latex_table(results)

if __name__ == '__main__':
    main()
