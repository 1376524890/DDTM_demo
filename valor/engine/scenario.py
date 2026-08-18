"""CapstoneScenario —— 冻结的完整交易场景配置（P3）。

一次 MNIST 完整交易的全部冻结输入：数据集/训练器/买方任务/权利/审计市场/
安全参数/校准与认证 artifact 引用/seed。编排器只读此场景，禁止从 config
手填中间量。

所有字段显式给出；可选字段为 None 时显式声明 not_applicable（fail closed，
禁止隐式默认）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash

# MNIST 主链默认 10x10 payoff（买方任务，规范 §14）
_MNIST_PAYOFF = [
    [1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0],
    [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0],
]


@dataclass
class CapstoneScenario:
    """一次完整交易的冻结场景。"""

    # 标识
    scenario_id: str
    seller_id: str
    buyer_id: str
    # 数据集 + 划分（五角色）
    dataset_name: str = "mnist"
    split_seed: int = 0
    role_fracs: dict[str, float] = field(default_factory=lambda: {
        "historical": 0.25, "buyer_base": 0.20,
        "seller_candidate": 0.05, "transaction_eval": 0.10,
    })
    # 训练器
    trainer: dict[str, Any] = field(default_factory=lambda: {
        "type": "MNISTMLP", "epochs": 5, "batch_size": 256, "lr": 1e-3,
    })
    # 买方任务上下文（N_b + payoff）
    buyer_task: dict[str, Any] = field(default_factory=lambda: {
        "task_id": "digit-classification",
        "deployment_scale": 100000,  # N_b
        "application_context": "check-digit-recognition",
    })
    payoff_matrix: list[list[float]] = field(default_factory=lambda: [
        [1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0, -3.0],
        [-3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, -3.0, 1.0],
    ])
    # 权利束（P2）
    rights: dict[str, Any] = field(default_factory=lambda: {
        "r_class": "data", "access_mode": "COMPUTE_ONLY",
        "t0": "2026-01-01T00:00:00Z", "t1": "2026-12-31T00:00:00Z",
        "q": 3, "purposes": ["digit-classification"],
        "scope": "buyer_org_A", "exclusivity": False,
        "redistribution": False, "derivative": True,
        "not_applicable_reason": "retention/delete via ODRL policy",
    })
    # 审计市场（P4）
    audit: dict[str, Any] = field(default_factory=lambda: {
        # n_nodes 必须 > m=3f+1，使 VCG 反事实（删除 winner 后仍有替补委员会）可行
        "n_nodes": 10, "f": 2, "family": "quality",
        "min_stake": 0.0, "timeout_s": 10.0, "rho": 0.0,
        "eta_b": 0.1, "eta_o": 0.0, "seed": 0,
        "cost": 2.0,
        "alpha_shift": 0.01, "label_error_threshold": 0.28,
        # 审计报价成本项（P0-B，显式配置，禁止默认）
        "chain_fee": 0.0, "challenge_cost": 0.0, "dispute_cost": 0.0,
        "max_audit_steps": 10,
        # AuditDisclosureBudget（P0-H）：显式 rows/fraction/bytes，禁止 DP ε 映射
        "privacy_budget": {
            "max_unique_rows": 200,
            "max_fraction": 0.3,
            "max_bytes": 200 * 784,
        },
        # 审计市场快照（P0-B）：由 ExperimentWorld / 上游注入，禁止 executor
        # 内部人工生成 bids。qualified_nodes + bids 显式给出（TEST_FIXTURE 默认）。
        "market": {
            "snapshot_id": "mnist-market-v1",
            "family": "quality",
            "min_stake": 0.0,
            "qualified_nodes": [f"node-{i}" for i in range(10)],
            "bids": {f"node-{i}": round(10.0 + i * 1.5, 2) for i in range(10)},
            "source_kind": "THREAT_SCENARIO",
            "source_ref": "scenario.audit.market (TEST_FIXTURE)",
        },
    })
    # 安全/先验/似然校准 artifact 引用（P6 离线冻结）
    audit_prior: dict[str, Any] = field(default_factory=lambda: {
        "pi_b": 0.25, "q_l": 0.2,
    })
    likelihood: dict[str, Any] = field(default_factory=lambda: {
        "PASS": {"G": 0.85, "L": 0.75, "B": 0.10},
        "QUALITY_FAIL": {"G": 0.12, "L": 0.22, "B": 0.40},
        "BREACH_EVIDENCE": {"G": 0.03, "L": 0.03, "B": 0.50},
    })
    loss_matrix: dict[str, Any] = field(default_factory=lambda: {
        "ACCEPT": {"G": 0.0, "L": 5.0, "B": 50.0},
        "REJECT": {"G": 10.0, "L": 1.0, "B": 0.0},
        "TERMINATE": {"G": 10.0, "L": 1.0, "B": 1.0},
    })
    # 认证 artifact 引用（P6）
    certificate: dict[str, Any] = field(default_factory=lambda: {
        "a_D": 1.0, "b_D": 1.0, "alpha_D": 0.05, "tp": 12, "fn": 2,
    })
    # 责任/定价参数
    bond: dict[str, Any] = field(default_factory=lambda: {
        "g_dev": 60.0, "eps_s": 1.0, "p_e_bond": 1.0, "p_e_f": 0.3,
        "lambda_s": 0.5, "f_s": 10.0, "kappa_s": 0.1, "t_pre": 1.0, "t_post": 1.0,
    })
    buyer: dict[str, Any] = field(default_factory=lambda: {
        "w_b_rem": 500.0, "c_i": 20.0, "c_r_pay": 5.0,
        "c_b_use_cap": 2.0, "r_b_post": 5.0,
    })
    seller: dict[str, Any] = field(default_factory=lambda: {
        "c_marg": 5.0, "c_r_s_pay": 3.0, "r_s_post": 4.0,
        "oc_s": 6.0, "pi_s0": 10.0,
        # 卖方可动用资金（B_S^pre 硬门槛：seller_funds < B_S^pre → NO_TRADE_HARD_GATE）
        # 显式给出；缺失时跳过硬门槛（测试便捷），生产 config 必须提供。
        "funds": None,
    })
    pricing: dict[str, Any] = field(default_factory=lambda: {"beta_bar": 0.5})
    exposure: dict[str, Any] = field(default_factory=lambda: {
        "l_comp": 2.0, "exclusivity": False, "competition_sensitivity": 1.0,
    })
    # 交易后使用序列（P9）
    # 交易后使用环境（P9）
    usage: dict[str, Any] = field(default_factory=lambda: {
        "authorized_actors": ["buyer_org_A"],
        "allowed_environments": ["approved_compute"],
    })
    usage_requests: list[dict[str, Any]] = field(default_factory=lambda: [
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "environment": "approved_compute", "timestamp": "2026-03-01T00:00:00Z",
         "action": "compute", "expect": "ALLOW"},
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "environment": "approved_compute", "timestamp": "2026-03-02T00:00:00Z",
         "action": "compute", "expect": "ALLOW"},
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "environment": "approved_compute", "timestamp": "2026-03-03T00:00:00Z",
         "action": "compute", "expect": "ALLOW"},
        {"actor": "buyer_org_A", "purpose": "digit-classification",
         "environment": "approved_compute", "timestamp": "2026-03-04T00:00:00Z",
         "action": "compute", "expect": "DENY"},
        {"actor": "buyer_org_B", "purpose": "digit-classification",
         "environment": "approved_compute", "timestamp": "2026-03-01T00:00:00Z",
         "action": "compute", "expect": "DENY"},
        {"actor": "buyer_org_A", "purpose": "marketing",
         "environment": "approved_compute", "timestamp": "2026-03-01T00:00:00Z",
         "action": "compute", "expect": "DENY"},
    ])
    # 反馈（P10）
    feedback: dict[str, Any] = field(default_factory=lambda: {
        "event_type": "CONTROLLED_CANARY", "theta_s_a": 1.0, "theta_s_b": 1.0,
    })
    # 场景分支控制（P12 五场景 C0-C4）
    #   seller_breach: 审计阶段发现卖方违约（→ SELLER_BREACH）
    #   buyer_misuse:  交易后买方违规使用（→ BUYER_BREACH）
    #   entitlement_pass: 资格/合规门（False → NO_TRADE_HARD_GATE）
    seller_breach: bool = False
    buyer_misuse: bool = False
    entitlement_pass: bool = True
    # P0-I：Entitlement / Compliance 输入状态（机制判定，不读标准答案）。
    #   grant_authority=False / version_revoked=True → Entitled 失败
    #   buyer_eligible=False / menu_conflict=True    → Compliant 失败
    entitlement: dict[str, Any] = field(default_factory=dict)

    def to_plain(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "seller_id": self.seller_id,
            "buyer_id": self.buyer_id,
            "dataset_name": self.dataset_name,
            "split_seed": self.split_seed,
            "role_fracs": self.role_fracs,
            "trainer": self.trainer,
            "buyer_task": self.buyer_task,
            "payoff_matrix": self.payoff_matrix,
            "rights": self.rights,
            "audit": self.audit,
            "audit_prior": self.audit_prior,
            "likelihood": self.likelihood,
            "loss_matrix": self.loss_matrix,
            "certificate": self.certificate,
            "bond": self.bond,
            "buyer": self.buyer,
            "seller": self.seller,
            "pricing": self.pricing,
            "exposure": self.exposure,
            "usage": self.usage,
            "usage_requests": self.usage_requests,
            "feedback": self.feedback,
            "seller_breach": self.seller_breach,
            "buyer_misuse": self.buyer_misuse,
            "entitlement_pass": self.entitlement_pass,
            "entitlement": self.entitlement,
        }

    @property
    def scenario_hash(self) -> str:
        return content_hash(self.to_plain())


def scenario_from_config(cfg: dict) -> CapstoneScenario:
    """从正式交易 config（transaction run 的 JSON）构造冻结场景。

    正式交易唯一入口 `python -m valor transaction run --config` 经此把 config
    桥接到 TransactionOrchestrator。业务参数必须显式给出（fail closed），
    禁止无来源默认值。
    """
    ds = cfg["dataset"]
    payoff = cfg.get("payoff")
    # MNIST 主链为 10 分类；payoff 必须是完整矩阵（list[list]）。
    # 二分类 r_tn/r_fp/r_fn/r_tp 与 MNIST 10 类不匹配，禁止用作 H(D) 主链 payoff。
    if isinstance(payoff, list) and payoff and isinstance(payoff[0], list):
        payoff_matrix = payoff
    elif isinstance(payoff, dict) and {"r_tn", "r_fp", "r_fn", "r_tp"} <= set(payoff):
        # 二分类场景仅当 dataset 为二分类时允许；MNIST 主链不接受
        raise ValueError(
            "二分类 payoff (r_tn/r_fp/r_fn/r_tp) 不适用于 MNIST 主链；"
            "请提供 10x10 payoff 矩阵"
        )
    else:
        payoff_matrix = _MNIST_PAYOFF  # MNIST 默认 10x10

    def _req(key: str) -> Any:
        if key not in cfg or cfg[key] is None:
            raise ValueError(f"[scenario_from_config] 正式交易 config 缺失必需字段: {key!r}")
        return cfg[key]

    # P0-Q：正式交易 config 的 rights 必须显式给出（fail closed，禁止业务默认）。
    rights = _req("rights")
    if not isinstance(rights, dict) or "access_mode" not in rights:
        raise ValueError(
            "[scenario_from_config] 正式交易 config 必须显式提供 rights（含 access_mode），"
            "禁止业务默认")

    ent = cfg.get("entitlement") or {}
    sc = CapstoneScenario(
        scenario_id=_req("scenario_id"),
        seller_id=_req("seller_id"),
        buyer_id=_req("buyer_id"),
        split_seed=ds.get("seed", 0),
        payoff_matrix=payoff_matrix,
        rights=rights,
        entitlement_pass=ent.get("grant_authority", True),
        entitlement=ent,
        seller_breach=cfg.get("seller_breach") or False,
        buyer_misuse=cfg.get("buyer_misuse") or False,
    )
    # 覆盖审计/责任/买方/卖方/定价参数（显式提供才覆盖）
    if "audit" in cfg:
        sc.audit.update(cfg["audit"])
    if "prior" in cfg:
        sc.audit_prior.update(cfg["prior"])
    if "loss_matrix" in cfg:
        sc.loss_matrix.update(cfg["loss_matrix"])
    if "cert" in cfg:
        sc.certificate.update(cfg["cert"])
    if "bond" in cfg:
        sc.bond.update(cfg["bond"])
    if "buyer" in cfg:
        sc.buyer.update(cfg["buyer"])
    if "seller" in cfg:
        sc.seller.update(cfg["seller"])
    if "pricing" in cfg:
        sc.pricing.update(cfg["pricing"])
    return sc


__all__ = ["CapstoneScenario", "scenario_from_config"]
