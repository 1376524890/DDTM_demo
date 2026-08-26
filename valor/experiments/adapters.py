"""Experiment adapters (Round 6 Phase 19): physical failure injection lives here,
not in production mechanism modules."""

from __future__ import annotations

from typing import Any, Callable


class TamperingSellerProvider:
    """Wraps a seller service so every opening is tampered (Merkle mismatch)."""

    def __init__(self, seller_service) -> None:
        self._inner = seller_service

    def process_challenge(self, challenge):
        from valor.privacy_audit.canonicalize import (
            canonical_mnist_row, canonical_row_from_payload,
        )
        from valor.privacy_audit.opening import make_opening

        opens = self._inner.process_challenge(challenge)
        if not opens:
            return []
        from valor.privacy_audit.opening import RowOpening

        out = []
        for o in opens:
            if isinstance(o, RowOpening):
                idx, img, label = canonical_row_from_payload(
                    o.row_payload, index=o.index)
                img = img.copy()
                img[0] = (int(img[0]) + 1) % 256
                out.append(make_opening(
                    index=o.index,
                    row_payload=canonical_mnist_row(o.index, img, label),
                    salt=bytes.fromhex(o.salt), proof=o.proof))
            else:
                idx = o["index"]
                row_payload = bytes.fromhex(o["row_payload"])
                img = canonical_row_from_payload(row_payload, index=idx)[1].copy()
                img[0] = (int(img[0]) + 1) % 256
                out.append(make_opening(
                    index=idx,
                    row_payload=canonical_mnist_row(
                        idx, img, canonical_row_from_payload(
                            row_payload, index=idx)[2]),
                    salt=bytes.fromhex(o["salt"]),
                    proof=__import__("valor.privacy_audit.opening", fromlist=["MerkleProof"]).MerkleProof.from_plain(o["merkle_proof"])))
        return out


class OfflineAuditorTransport:
    """Wraps a node client factory and makes selected nodes offline."""

    def __init__(self, base_factory: Callable[[str], Any], offline_nodes: list[str]) -> None:
        self._base = base_factory
        self._offline = set(str(n) for n in offline_nodes)

    def __call__(self, node_id: str) -> Any:
        if str(node_id) in self._offline:
            raise ConnectionError(f"offline node {node_id}")
        return self._base(node_id)


class InvalidSignatureAuditorTransport:
    """Wraps a node client factory and corrupts signatures from selected nodes."""

    def __init__(self, base_factory: Callable[[str], Any], invalid_nodes: list[str]) -> None:
        self._base = base_factory
        self._invalid = set(str(n) for n in invalid_nodes)

    def __call__(self, node_id: str) -> Any:
        client = self._base(node_id)
        orig_submit = client.submit_task

        def _submit(task):
            ev = orig_submit(task)
            if str(node_id) in self._invalid:
                ev["signature"] = "0" * 128
            return ev

        client.submit_task = _submit  # type: ignore
        return client


class MismatchedDeliveryProvider:
    """Returns a mismatched delivery commitment for failure experiments."""

    def deliver(self, *, delivery_commitment, **kwargs):
        return {"verified": False, "delivery_commitment": "mismatch",
                "reason": "SELLER_BREACH_DELIVERY_EXPERIMENT"}
