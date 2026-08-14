"""Markdown 报告构建（Phase 8 / 规范 §68 日志最小字段）。

从一次全流程交易的 raw JSON 生成可读 Markdown 报告。
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def _money(x, unit="CU"):
    if x is None:
        return "-"
    return f"{x:,.2f} {unit}"


def build_markdown(result: dict) -> str:
    """把交易结果 dict 转成 Markdown 报告。"""
    lines: list[str] = []
    lines.append("# VALOR 全流程交易报告")
    lines.append(f"\n生成时间：`{datetime.now(timezone.utc).isoformat()}`\n")
    lines.append(f"**成交决策：`{result.get('decision')}`**\n")

    lines.append("## 1. 资格/合规（§6）")
    ent = result.get("entitlement", {})
    lines.append(f"- 卖方资格：`{ent.get('grant_authority')}`；合规：`{ent.get('compliant')}`\n")

    lines.append("## 2. 质量复现 Gate B（§15/§47）")
    q = result.get("quality", {})
    lines.append(f"- Gate B 通过：`{q.get('gate_b_pass')}`")
    lines.append(f"- 分布式启用 primitive：{q.get('distributed_enabled')}\n")

    lines.append("## 3. Data-VOI（§26-28）")
    v = result.get("valuation", {})
    lines.append(f"- U_base = {_money(v.get('u_base'))}")
    lines.append(f"- U_base+Δ = {_money(v.get('u_plus'))}")
    lines.append(f"- 竞争外部性 L_comp = {_money(v.get('l_comp'))}")
    lines.append(f"- 保守下界 V̲_gross = {_money(v.get('v_gross_lower'))}\n")

    lines.append("## 4. Audit-VOI（§24-25）")
    a = result.get("audit", {})
    lines.append(f"- 审计步数：`{a.get('n_steps')}`")
    lines.append(f"- 后验 π：`{a.get('posterior')}`")
    lines.append(f"- 审计支付（卖/买）：{_money(a.get('audit_pay_s'))} / {_money(a.get('audit_pay_b'))}\n")

    lines.append("## 5. 检测认证（§22）")
    c = result.get("certification", {})
    lines.append(f"- p̲_B^sys = `{c.get('p_breach_lower_sys'):.4f}`\n")

    lines.append("## 6. 责任（§30-31）")
    l = result.get("liability", {})
    lines.append(f"- B_S^* = {_money(l.get('b_s_star'))}")
    lines.append(f"- B_S^pre = {_money(l.get('b_s_pre'))}")
    lines.append(f"- 资本成本 C_B^cap = {_money(l.get('c_b_cap'))}\n")

    lines.append("## 7. 定价（§39-41）")
    p = result.get("pricing", {})
    lines.append(f"- P_max = {_money(p.get('p_max'))}")
    lines.append(f"- P_min = {_money(p.get('p_min'))}")
    lines.append(f"- 贸易边际 M = {_money(p.get('margin'))}")
    lines.append(f"- 结算价 P* = {_money(p.get('clearing_price'))}")
    lines.append(f"- 决策：`{p.get('decision')}`\n")

    lines.append("## 8. 状态机与结算（§43）")
    s = result.get("state", {})
    lines.append(f"- 终态：`{s.get('terminal')}`；权利状态：`{s.get('rights_state')}`")
    lines.append(f"- bond 罚没：{_money(s.get('bond_slashed'))}\n")

    lines.append("## 9. 反馈（§45-46）")
    f = result.get("feedback", {})
    lines.append(f"- realised value：{_money(f.get('realised_value'))}")
    lines.append(f"- ground-truth 资格事件：`{f.get('eligible_events')}`")
    return "\n".join(lines)


def build_report(run_result_path: str, out_md: str) -> int:
    """从 run_result JSON 生成 Markdown 报告。"""
    result = json.loads(Path(run_result_path).read_text(encoding="utf-8"))
    md = build_markdown(result)
    Path(out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(out_md).write_text(md, encoding="utf-8")
    print(f"报告已写入 {out_md}")
    return 0
