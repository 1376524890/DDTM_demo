"""CapstoneScenario —— 冻结的完整交易场景配置（P3）。

一次 MNIST 完整交易的全部冻结输入：数据集/训练器/买方任务/权利/审计市场/
安全参数/校准与认证 artifact 引用/seed。编排器只读此场景，禁止从 run.py
手填中间量。

所有字段显式给出；可选字段为 None 时显式声明 not_applicable（fail closed，
禁止隐式默认）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from valor.core.hashing import content_hash


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
        "n_nodes": 7, "f": 2, "family": "quality",
        "min_stake": 0.0, "timeout_s": 10.0, "rho": 0.0,
        "eta_b": 0.1, "eta_o": 0.0, "seed": 0,
        "cost": 2.0,
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
        }

    @property
    def scenario_hash(self) -> str:
        return content_hash(self.to_plain())


__all__ = ["CapstoneScenario"]
