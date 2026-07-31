"""用整数状态动态规划精确评估 SPRT。

观测 ``samples`` 个样本、其中 ``failures`` 个异常后的对数似然比 LLR，是整数对
``(samples, failures)`` 的确定性函数——所以我们用这对整数作为 DP 的状态键，而
不是用一个带噪声的浮点 LLR。这样一次遍历即可同时得到精确的停止分布、
``E[T]`` 与 ``E[ceil(T / batch_size)]``。
"""
from __future__ import annotations

import math
from collections import defaultdict

from .models import OperatingPoint, SprtPolicy


def sprt_constants(policy: SprtPolicy) -> tuple[float, float, float, float]:
    """返回策略的 (lower, upper, hit_increment, clean_increment)。

    ``lower`` / ``upper`` 是 Wald 接受/拒绝的对数边界；两个 increment 分别是一个
    异常样本与一个干净样本对 LLR 的贡献。
    """
    policy.validate()

    lower = math.log(policy.beta / (1.0 - policy.alpha))
    upper = math.log((1.0 - policy.beta) / policy.alpha)
    hit_increment = math.log(policy.tau_bad / policy.tau_good)
    clean_increment = math.log((1.0 - policy.tau_bad) / (1.0 - policy.tau_good))
    return lower, upper, hit_increment, clean_increment


def state_llr(
    samples: int,
    failures: int,
    hit_increment: float,
    clean_increment: float,
) -> float:
    """状态 ``(samples, failures)`` 在 H1 对 H0 下的 LLR。"""
    clean = samples - failures
    return failures * hit_increment + clean * clean_increment


def evaluate_operating_point(
    contamination: float,
    policy: SprtPolicy,
) -> OperatingPoint:
    """用精确 DP 评估某个污染水平下的 SPRT。

    概率质量在整数 ``(samples, failures)`` 状态上流动。越过边界（或达到
    ``max_samples``）的状态会从活跃集合移除，其质量被加到对应结果，并累加进
    期望样本数 / 期望批数。
    """
    if not 0.0 <= contamination <= 1.0:
        raise ValueError("contamination must be in [0, 1]")

    lower, upper, hit_increment, clean_increment = sprt_constants(policy)

    # 活跃（尚未停止）状态的质量：(samples, failures) -> 概率。
    active: dict[tuple[int, int], float] = {(0, 0): 1.0}

    accept_probability = 0.0
    reject_probability = 0.0
    inconclusive_probability = 0.0
    expected_samples = 0.0
    expected_batches = 0.0

    def record_stop(samples: int, mass: float) -> None:
        """计入一条长度为 ``samples``、权重为 mass 的停止轨迹。"""
        nonlocal expected_samples, expected_batches
        expected_samples += samples * mass
        # E[ceil(T/batch)] 直接来自停止分布——不是 ceil(E[T]/batch)。
        # 这正是我们要按停止时间做 DP 的原因。
        expected_batches += math.ceil(samples / policy.batch_size) * mass

    for _ in range(policy.max_samples):
        next_active: dict[tuple[int, int], float] = defaultdict(float)

        for (samples, failures), state_mass in active.items():
            # 伯努利转移：干净（outcome 0）对异常（outcome 1）。
            transitions = (
                (0, 1.0 - contamination),
                (1, contamination),
            )
            for outcome, outcome_probability in transitions:
                mass = state_mass * outcome_probability
                if mass == 0.0:
                    continue

                new_samples = samples + 1
                new_failures = failures + outcome
                llr = state_llr(
                    new_samples, new_failures, hit_increment, clean_increment
                )

                if llr <= lower:
                    accept_probability += mass
                    record_stop(new_samples, mass)
                elif llr >= upper:
                    reject_probability += mass
                    record_stop(new_samples, mass)
                elif new_samples == policy.max_samples:
                    # 达到截断预算仍未决断。
                    inconclusive_probability += mass
                    record_stop(new_samples, mass)
                else:
                    next_active[(new_samples, new_failures)] += mass

        active = next_active
        if not active:
            break

    # 按构造，任何残余质量都属于 INCONCLUSIVE 结果。
    inconclusive_probability += sum(active.values())

    total = (
        accept_probability + reject_probability + inconclusive_probability
    )
    if abs(total - 1.0) >= 1e-12:
        raise ArithmeticError(f"Probability conservation failed: {total}")

    return OperatingPoint(
        contamination=contamination,
        accept_probability=accept_probability,
        reject_probability=reject_probability,
        inconclusive_probability=inconclusive_probability,
        expected_samples=expected_samples,
        expected_batches=expected_batches,
    )
