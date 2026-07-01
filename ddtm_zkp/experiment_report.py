#!/usr/bin/env python3
"""
DDTM ZKP Experiment Analysis Report Generator
Generates LaTeX tables for the DDTM research paper from real benchmark data.
"""

import math

# =============================================================================
# 0. Hardware / Software Context
# =============================================================================
HARDWARE = "QEMU Virtual CPU 2.5+, 2 cores, Linux 6.8.0-124-generic"
SOFTWARE = "gnark v0.x, Groth16 BN254, Go"

# =============================================================================
# 1. REAL BENCHMARK DATA
# =============================================================================
benchmarks = {
    "PiKey v22": {
        "constraints": 331,
        "prove_ms": 31,
        "verify_ms": 1.5,
        "setup_ms": 131,
        "pk_kb": 67,
        "attack_tests": None,
    },
    "PiKey Full": {
        "constraints": 1322,
        "prove_ms": 103,
        "verify_ms": 1.7,
        "setup_ms": 497,
        "pk_kb": 266,
        "attack_tests": "5/5",
    },
    "PiDeliverFull": {
        "constraints": 2517,
        "prove_ms": 99,
        "verify_ms": 1.7,
        "setup_ms": 735,
        "pk_kb": 421,
        "attack_tests": None,
    },
    "PiDeliver Byte (4 blocks)": {
        "constraints": 8456,
        "prove_ms": 327,
        "verify_ms": 1.7,
        "setup_ms": 2937,
        "pk_kb": 1714,
        "attack_tests": "4/4",
    },
}

# =============================================================================
# 2. SCALING PROJECTION
# =============================================================================
CONSTRAINTS_PER_BLOCK = 2114  # estimated from PiDeliver Byte 4-block measurement

scaling_blocks = [10, 50, 100, 500, 1000]
# PiDeliver Byte (4 blocks): 8456 constraints, 327ms prove, 1714KB PK
# Base overhead (non-block constraints): 8456 - 4*2114 = 8456 - 8456 = 0  (fits well)
# Actually let's compute overhead from the 4-block measurement
# 4 blocks → 8456 constraints, so base_overhead = 8456 - 4*CONSTRAINTS_PER_BLOCK
base_overhead = benchmarks["PiDeliver Byte (4 blocks)"]["constraints"] - 4 * CONSTRAINTS_PER_BLOCK
# Prove time per constraint: 327ms / 8456 ≈ 0.03867 ms/constraint
prove_per_constraint = benchmarks["PiDeliver Byte (4 blocks)"]["prove_ms"] / benchmarks["PiDeliver Byte (4 blocks)"]["constraints"]
# PK size per constraint: 1714KB / 8456 ≈ 0.2027 KB/constraint
pk_per_constraint = benchmarks["PiDeliver Byte (4 blocks)"]["pk_kb"] / benchmarks["PiDeliver Byte (4 blocks)"]["constraints"]

def project(n_blocks):
    constraints = n_blocks * CONSTRAINTS_PER_BLOCK + base_overhead
    prove_ms = constraints * prove_per_constraint
    pk_kb = constraints * pk_per_constraint
    return constraints, prove_ms, pk_kb

# =============================================================================
# 3. STATE MACHINE TEST DATA
# =============================================================================
state_machine_tests = [
    ("Normal trade",              "CONFIRMED",            "PASS"),
    ("Buyer refuses payment",     "REFUNDED",             "PASS"),
    ("Seller refuses delivery",   "REFUNDED",             "PASS"),
    ("Wrong key",                 "DISPUTED$\\rightarrow$REFUNDED", "PASS"),
    ("Quality proof fails",       "ABORTED",              "PASS"),
    ("Data tampering",            "DISPUTED$\\rightarrow$REFUNDED", "PASS"),
    ("Buyer malicious dispute",   "CONFIRMED",            "PASS"),
    ("Arbitration timeout",       "REFUNDED",             "PASS"),
]

# =============================================================================
# 4. ATTACK DEFENSE TABLE
# =============================================================================
# Defense categories: auto-block, economic-mitigation, governance-mitigation, not-covered
attack_defenses = [
    # --- Auto-block (7 attacks) ---
    ("Invalid ZKP proof submission",          "Auto-block",       "Proof verification fails on-chain; transaction rejected",   "None"),
    ("Replay attack (duplicate proof)",       "Auto-block",       "Nullifier/session nonce enforced in circuit",                "None"),
    ("Forged delivery confirmation",          "Auto-block",       "Signature verification inside ZKP circuit",                  "None"),
    ("Key mismatch (wrong decryption key)",   "Auto-block",       "Key commitment opened inside circuit; mismatch detected",     "None"),
    ("Double-claim attack",                   "Auto-block",       "State commitment prevents duplicate settlement",             "None"),
    ("Premature refund claim",                "Auto-block",       "State machine enforces phase ordering via constraints",      "None"),
    ("Malformed state transition",            "Auto-block",       "Circuit enforces valid DDTM state-machine transitions only", "None"),

    # --- Economic mitigation (2 attacks) ---
    ("Front-running proof submission",        "Economic-mitigation", "MEV-resistant ordering + commit-reveal; attacker loses gas", "Low"),
    ("Griefing via repeated disputes",        "Economic-mitigation", "Escalating dispute bond with slashing for frivolous claims",  "Medium"),

    # --- Governance mitigation (3 attacks) ---
    ("Arbiter collusion with buyer",          "Governance-mitigation", "Multi-arbiter threshold + stake-weighted voting",          "Medium"),
    ("Arbiter collusion with seller",         "Governance-mitigation", "Rotation of arbiter pool + reputation staking",            "Medium"),
    ("Sybil arbiter registration",            "Governance-mitigation", "Bonded registration with stake-slashing for malfeasance",  "Low"),
]

# =============================================================================
# 5. LATEX TABLE GENERATION
# =============================================================================

def escape_latex(text):
    """Escape special LaTeX characters."""
    return str(text).replace("\\", "\\textbackslash ").replace("&", "\\&").replace("%", "\\%").replace("$", "\\$").replace("#", "\\#").replace("_", "\\_").replace("{", "\\{").replace("}", "\\}").replace("~", "\\textasciitilde ").replace("^", "\\textasciicircum ")


def table_benchmark():
    """Table 1: Benchmark Results."""
    lines = []
    lines.append("% --- Benchmark Results ---")
    lines.append("\\begin{table}[ht]")
    lines.append("\\centering")
    lines.append("\\caption{DDTM ZKP Benchmark Results (Groth16, BN254)}")
    lines.append("\\label{tab:benchmarks}")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lrrrrrc}")
    lines.append("\\toprule")
    lines.append("\\textbf{Circuit} & \\textbf{Constraints} & \\textbf{Prove} & \\textbf{Verify} & \\textbf{Setup} & \\textbf{PK Size} & \\textbf{Attack} \\\\")
    lines.append(" & & \\textbf{(ms)} & \\textbf{(ms)} & \\textbf{(ms)} & \\textbf{(KB)} & \\textbf{Tests} \\\\")
    lines.append("\\midrule")
    for name, d in benchmarks.items():
        atk = d["attack_tests"] if d["attack_tests"] else "---"
        lines.append(
            f"{escape_latex(name)} & {d['constraints']:,} & {d['prove_ms']} & {d['verify_ms']} & {d['setup_ms']} & {d['pk_kb']:,} & {atk} \\\\"
        )
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\vspace{4pt}")
    lines.append("\\footnotesize Hardware: " + escape_latex(HARDWARE) + ". Software: " + escape_latex(SOFTWARE) + ".")
    lines.append("\\end{table}")
    return "\n".join(lines)


def table_scaling():
    """Table 2: Scaling Projections."""
    lines = []
    lines.append("% --- Scaling Projections ---")
    lines.append("\\begin{table}[ht]")
    lines.append("\\centering")
    lines.append("\\caption{Scaling Projection for Multi-Block Data Delivery ($\\sim$" + f"{CONSTRAINTS_PER_BLOCK:,}" + " constraints/block)}")
    lines.append("\\label{tab:scaling}")
    lines.append("\\begin{tabular}{rrrr}")
    lines.append("\\toprule")
    lines.append("\\textbf{Blocks} & \\textbf{Est. Constraints} & \\textbf{Est. Prove (ms)} & \\textbf{Est. PK (KB)} \\\\")
    lines.append("\\midrule")
    for n in scaling_blocks:
        c, p, pk = project(n)
        lines.append(f"{n} & {int(c):,} & {p:.0f} & {pk:.0f} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\vspace{4pt}")
    lines.append("\\footnotesize Extrapolated from 4-block PiDeliver Byte measurement. Linear scaling assumed for constraint count and PK size; prove time scales near-linearly with constraints in Groth16. Verify time is constant ($\\sim$1.7\\,ms).")
    lines.append("\\end{table}")
    return "\n".join(lines)


def table_state_machine():
    """Table 3: State Machine Functional Tests."""
    lines = []
    lines.append("% --- State Machine Functional Tests ---")
    lines.append("\\begin{table}[ht]")
    lines.append("\\centering")
    lines.append("\\caption{DDTM State Machine Functional Test Results}")
    lines.append("\\label{tab:state-machine}")
    lines.append("\\begin{tabular}{lp{4.5cm}c}")
    lines.append("\\toprule")
    lines.append("\\textbf{Scenario} & \\textbf{Expected Final State} & \\textbf{Result} \\\\")
    lines.append("\\midrule")
    for scenario, expected, result in state_machine_tests:
        r = "\\checkmark" if result == "PASS" else "\\texttimes"
        lines.append(f"{escape_latex(scenario)} & {expected} & {r} \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


def table_attack_defense():
    """Table 4: Attack Defense Matrix."""
    lines = []
    lines.append("% --- Attack Defense Matrix ---")
    lines.append("\\begin{table}[ht]")
    lines.append("\\centering")
    lines.append("\\caption{Attack Surface and Defense-in-Depth Matrix}")
    lines.append("\\label{tab:attack-defense}")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lp{5cm}p{5.5cm}p{2cm}}")
    lines.append("\\toprule")
    lines.append("\\textbf{Attack Vector} & \\textbf{Defense Type} & \\textbf{Mechanism} & \\textbf{Residual Risk} \\\\")
    lines.append("\\midrule")

    current_category = None
    for i, (attack, defense_type, mechanism, residual) in enumerate(attack_defenses):
        if defense_type != current_category:
            current_category = defense_type
            if i > 0:
                lines.append("\\midrule")
            # Category header
            cat_label = {
                "Auto-block": "\\textbf{Automatic (ZKP + Smart Contract)}",
                "Economic-mitigation": "\\textbf{Economic Mitigation}",
                "Governance-mitigation": "\\textbf{Governance Mitigation}",
            }.get(defense_type, defense_type)
            lines.append("\\multicolumn{4}{l}{\\textit{" + cat_label + "}} \\\\")
            lines.append("\\cmidrule{2-4}")

        hspace = "\\hspace{8pt}"
        lines.append(
            f"{hspace}{escape_latex(attack)} & {escape_latex(defense_type)} & {escape_latex(mechanism)} & {escape_latex(residual)} \\\\"
        )

    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append("\\end{table}")
    return "\n".join(lines)


# =============================================================================
# 6. PRINT ALL TABLES
# =============================================================================
if __name__ == "__main__":
    print("=" * 72)
    print("  DDTM ZKP EXPERIMENT ANALYSIS REPORT — LaTeX Tables")
    print("=" * 72)
    print()
    print(f"Hardware: {HARDWARE}")
    print(f"Software: {SOFTWARE}")
    print(f"Constraints per block (estimated): {CONSTRAINTS_PER_BLOCK:,}")
    print()

    print(table_benchmark())
    print()
    print(table_scaling())
    print()
    print(table_state_machine())
    print()
    print(table_attack_defense())

    # Also print a plain-text summary for quick reading
    print()
    print("=" * 72)
    print("  PLAIN-TEXT SUMMARY")
    print("=" * 72)
    print()
    print("--- Benchmark Summary ---")
    print(f"{'Circuit':<28} {'Constr':>8} {'Prove':>8} {'Verify':>8} {'Setup':>8} {'PK':>8}  {'Attacks'}")
    print("-" * 85)
    for name, d in benchmarks.items():
        atk = d["attack_tests"] if d["attack_tests"] else "---"
        print(f"{name:<28} {d['constraints']:>8,} {d['prove_ms']:>7}ms {d['verify_ms']:>7}ms {d['setup_ms']:>7}ms {d['pk_kb']:>7,}KB  {atk}")

    print()
    print("--- Scaling Projections ---")
    print(f"{'Blocks':>8} {'Est. Constraints':>18} {'Est. Prove':>12} {'Est. PK':>12}")
    print("-" * 55)
    for n in scaling_blocks:
        c, p, pk = project(n)
        print(f"{n:>8} {int(c):>18,} {p:>11.0f}ms {pk:>11.0f}KB")

    print()
    print("--- State Machine Tests: 8/8 PASS ---")
    print()
    print("--- Attack Defenses: 12 attack vectors classified ---")
    cats = {}
    for _, dt, _, _ in attack_defenses:
        cats[dt] = cats.get(dt, 0) + 1
    for cat, count in cats.items():
        print(f"  {cat}: {count}")
