// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {PolicyRegistry} from "./PolicyRegistry.sol";
import {AttestationRegistry} from "./AttestationRegistry.sol";
import {RandomnessRegistry} from "./RandomnessRegistry.sol";
import {IZKVerifierAdapter} from "./interfaces/IZKVerifierAdapter.sol";

/// @title DDTMMarketplace
/// @notice Core marketplace implementing the 18-state DDTM-QAS protocol.
///
/// State flow:
///   LISTED -> ESCROWED -> TEE_REGISTERED -> UTILITY_VERIFIED -> AUDITING
///   AUDITING -> AUDIT_ACCEPTED | AUDIT_REJECTED | AUDIT_INCONCLUSIVE
///   AUDIT_ACCEPTED -> CIPHERTEXT_COMMITTED -> KEY_RELEASED -> BUYER_CHECKING
///   AUDIT_REJECTED -> REFUNDED
///   AUDIT_INCONCLUSIVE -> CONDITIONAL
///   BUYER_CHECKING -> CONFIRMED | DISPUTED
///   DISPUTED -> RESOLVED_SELLER | RESOLVED_BUYER
///   Any state -> ABORTED (on timeout)
contract DDTMMarketplace is ReentrancyGuard {
    enum State {
        LISTED, ESCROWED, TEE_REGISTERED, UTILITY_VERIFIED, AUDITING,
        AUDIT_ACCEPTED, AUDIT_REJECTED, AUDIT_INCONCLUSIVE, CONDITIONAL,
        CIPHERTEXT_COMMITTED, KEY_RELEASED, BUYER_CHECKING, DISPUTED,
        CONFIRMED, REFUNDED, RESOLVED_SELLER, RESOLVED_BUYER, ABORTED
    }

    struct Listing {
        address seller;
        address buyer;
        State state;
        bytes32 policyHash;
        bytes32 dataRoot;
        bytes32 schemaHash;
        bytes32 modelCommitment;
        bytes32 validationRoot;
        bytes32 auditCommitment;
        bytes32 metricsCommitment;
        bytes32 sessionId;
        bytes32 beaconId;
        uint64 beaconRound;
        uint64 rowCount;
        uint64 datasetVersion;
        uint32 auditN;
        uint32 auditFailures;
        uint32 auditBatch;
        uint256 price;
        uint256 bond;
        uint256 buyerEscrow;
        bytes32 manifestDigest;
        bytes32 keyEnvelopeDigest;
        bytes32 transcriptHash;
        uint64 deadline;
    }

    // Per-policy SPRT constants.
    struct SprtParams {
        int256 hitIncrementQ32;
        int256 cleanIncrementQ32;
        int256 upperQ32;
        int256 lowerQ32;
    }

    // Attested delivery receipt for dispute resolution.
    struct DeliveryReceipt {
        bool match_;
        bytes32 recomputedRoot;
        bytes32 sessionId;
    }

    PolicyRegistry public immutable policies;
    AttestationRegistry public immutable attestations;
    RandomnessRegistry public immutable randomness;
    uint256 public listingCount;
    mapping(uint256 => Listing) public listings;
    mapping(address => uint256) public credits;
    mapping(bytes32 => bool) public consumedRequest;
    mapping(bytes32 => SprtParams) public sprtParams;

    // Audit cost borne by seller if audit fails or inconclusive.
    uint256 public auditCostPerBatch = 0.008 ether;

    event StateChanged(uint256 indexed id, State state, bytes32 transcriptHash);
    event DisputeOpened(uint256 indexed id, bytes32 manifestDigest);
    event DisputeResolved(uint256 indexed id, bool sellerWins, bytes32 recomputedRoot);

    modifier unique(bytes32 requestId) {
        require(requestId != bytes32(0) && !consumedRequest[requestId], "duplicate request");
        consumedRequest[requestId] = true;
        _;
    }

    modifier notExpired(uint256 id) {
        Listing storage x = listings[id];
        require(x.deadline == 0 || block.timestamp < x.deadline, "deadline expired");
        _;
    }

    modifier onlySeller(uint256 id) {
        require(msg.sender == listings[id].seller, "not seller");
        _;
    }

    modifier onlyBuyer(uint256 id) {
        require(msg.sender == listings[id].buyer, "not buyer");
        _;
    }

    constructor(PolicyRegistry p, AttestationRegistry a, RandomnessRegistry r) {
        policies = p;
        attestations = a;
        randomness = r;
    }

    // ============================================================
    // Phase 2: Seller Listing
    // ============================================================

    function requiredBond(
        bytes32 policyHash, uint256 price, uint256 gMax, uint256 detectionPpm
    ) public view returns (uint256) {
        PolicyRegistry.Policy memory p = policies.getPolicy(policyHash);
        require(detectionPpm > 0 && detectionPpm <= 1_000_000, "invalid detection ppm");
        // B_min = max(0, (Gmax + safetyMargin) / p_det - price)
        uint256 covered = ((gMax + p.safetyMargin) * 1_000_000 + detectionPpm - 1) / detectionPpm;
        return covered > price ? covered - price : 0;
    }

    function list(
        bytes32 policyHash,
        bytes32 dataRoot,
        bytes32 schemaHash,
        bytes32 modelCommitment,
        bytes32 validationRoot,
        bytes32 auditCommitment,
        bytes32 beaconId,
        uint64 beaconRound,
        uint64 rowCount,
        uint64 datasetVersion,
        uint256 price,
        uint256 gMax,
        uint256 detectionPpm,
        bytes32 requestId
    ) external payable unique(requestId) returns (uint256 id) {
        PolicyRegistry.Policy memory p = policies.getPolicy(policyHash);
        require(schemaHash == p.schemaHash, "schema mismatch");
        require(rowCount > 0 && rowCount <= p.maxRows, "invalid row count");
        uint256 bond = requiredBond(policyHash, price, gMax, detectionPpm);
        require(msg.value >= bond, "insufficient bond");
        require(price > 0, "price must be positive");

        id = listingCount++;
        listings[id] = Listing({
            seller: msg.sender,
            buyer: address(0),
            state: State.LISTED,
            policyHash: policyHash,
            dataRoot: dataRoot,
            schemaHash: schemaHash,
            modelCommitment: modelCommitment,
            validationRoot: validationRoot,
            auditCommitment: auditCommitment,
            metricsCommitment: bytes32(0),
            sessionId: bytes32(0),
            beaconId: beaconId,
            beaconRound: beaconRound,
            rowCount: rowCount,
            datasetVersion: datasetVersion,
            auditN: 0,
            auditFailures: 0,
            auditBatch: 0,
            price: price,
            bond: msg.value,
            buyerEscrow: 0,
            manifestDigest: bytes32(0),
            keyEnvelopeDigest: bytes32(0),
            transcriptHash: keccak256(abi.encode(requestId, dataRoot, policyHash)),
            deadline: uint64(block.timestamp + 30 days)
        });
        emit StateChanged(id, State.LISTED, listings[id].transcriptHash);
    }

    // ============================================================
    // Phase 2b: Buyer Bid
    // ============================================================

    function bid(uint256 id, bytes32 requestId)
        external payable unique(requestId) notExpired(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.LISTED, "not listed");
        require(msg.sender != x.seller, "seller cannot bid");
        require(msg.value == x.price, "incorrect price");

        x.buyer = msg.sender;
        x.buyerEscrow = msg.value;
        x.state = State.ESCROWED;
        x.deadline = uint64(block.timestamp + 1 days);
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 3: TEE Session Registration
    // ============================================================

    function registerSession(uint256 id, bytes32 sessionId, bytes32 requestId)
        external unique(requestId) notExpired(id) onlySeller(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.ESCROWED, "not escrowed");
        attestations.requireValid(sessionId, x.policyHash);
        x.sessionId = sessionId;
        x.state = State.TEE_REGISTERED;
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 3b: Utility Proof Submission
    // ============================================================

    function submitUtility(
        uint256 id, bytes32 metricsCommitment,
        bytes calldata proof, uint256[] calldata publicInputs,
        bytes32 requestId
    ) external unique(requestId) notExpired(id) onlySeller(id) {
        Listing storage x = listings[id];
        require(x.state == State.TEE_REGISTERED, "not tee registered");
        PolicyRegistry.Policy memory p = policies.getPolicy(x.policyHash);

        require(
            IZKVerifierAdapter(p.utilityVerifier).verify(proof, publicInputs),
            "invalid utility proof"
        );
        require(publicInputs.length >= 5, "too few utility inputs");
        require(bytes32(publicInputs[1]) == x.dataRoot, "data root mismatch");
        require(bytes32(publicInputs[4]) == metricsCommitment, "metrics mismatch");

        x.metricsCommitment = metricsCommitment;
        x.state = State.UTILITY_VERIFIED;
        x.deadline = uint64(block.timestamp + 1 days);
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 4: ZASA Audit
    // ============================================================

    function startAudit(uint256 id, bytes32 requestId)
        external unique(requestId) notExpired(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.UTILITY_VERIFIED, "not utility verified");

        bytes32 roundKey = randomness.key(x.beaconId, x.beaconRound);
        RandomnessRegistry.BeaconRound memory b = randomness.rounds(roundKey);
        require(b.verifiedAt != 0, "drand round not yet available");

        x.state = State.AUDITING;
        _advance(id, x, requestId);
    }

    function submitAuditBatch(
        uint256 id, uint32 newN, uint32 newFailures,
        bytes calldata proof, uint256[] calldata publicInputs,
        bytes32 requestId
    ) external unique(requestId) onlySeller(id) {
        Listing storage x = listings[id];
        require(x.state == State.AUDITING, "not auditing");
        PolicyRegistry.Policy memory p = policies.getPolicy(x.policyHash);

        require(
            newN == x.auditN + p.auditBatchSize,
            "audit N must advance by batch size"
        );
        require(newN <= p.maxAuditSamples, "exceeds max audit samples");
        require(newFailures >= x.auditFailures, "failures cannot decrease");
        require(newFailures <= newN, "failures exceed N");

        require(
            IZKVerifierAdapter(p.auditVerifier).verify(proof, publicInputs),
            "invalid audit proof"
        );

        x.auditN = newN;
        x.auditFailures = newFailures;
        x.auditBatch += 1;
        _advance(id, x, requestId);
    }

    function setSprtParams(bytes32 policyHash, SprtParams calldata params) external {
        require(msg.sender == policies.owner(), "only policy owner");
        require(sprtParams[policyHash].hitIncrementQ32 == 0, "SPRT already set");
        sprtParams[policyHash] = params;
    }

    function decideAudit(uint256 id, bytes32 requestId)
        external unique(requestId)
    {
        Listing storage x = listings[id];
        require(x.state == State.AUDITING, "not auditing");
        require(x.auditN > 0, "no audit batches submitted");

        SprtParams memory sp = sprtParams[x.policyHash];
        require(sp.hitIncrementQ32 != 0, "SPRT params not configured");

        // On-chain LLR computation using Q32 fixed-point arithmetic.
        // LLR = failures * log(tau1/tau0) + (n-failures) * log((1-tau1)/(1-tau0))
        // All log terms are pre-computed as Q32 integers.
        int256 failures = int256(uint256(x.auditFailures));
        int256 clean = int256(uint256(x.auditN)) - failures;
        int256 llr_q32 = failures * sp.hitIncrementQ32 + clean * sp.cleanIncrementQ32;

        // Compare in Q32 space to avoid division precision loss.
        if (llr_q32 >= sp.upperQ32) {
            x.state = State.AUDIT_REJECTED;
            _refundBuyer(x);
        } else if (llr_q32 <= sp.lowerQ32) {
            x.state = State.AUDIT_ACCEPTED;
        } else if (x.auditN >= policies.getPolicy(x.policyHash).maxAuditSamples) {
            x.state = State.AUDIT_INCONCLUSIVE;
        } else {
            revert("audit not yet decisive; submit more batches or wait for max samples");
        }
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 4b: Inconclusive Handling
    // ============================================================

    /// @notice Buyer accepts residual risk after INCONCLUSIVE audit.
    /// Seller pays audit costs from bond; remaining bond returned.
    function acceptConditional(uint256 id, bytes32 requestId)
        external unique(requestId) notExpired(id) onlyBuyer(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.AUDIT_INCONCLUSIVE, "not inconclusive");

        // Deduct audit costs from seller bond.
        uint256 auditCost = x.auditBatch * auditCostPerBatch;
        if (auditCost > x.bond) auditCost = x.bond;
        if (auditCost > 0) {
            // Audit costs go to platform (or could go to buyer compensation).
            // For prototype, burn or hold in contract.
            x.bond -= auditCost;
        }

        x.state = State.CONDITIONAL;
        x.deadline = uint64(block.timestamp + 3 days);
        _advance(id, x, requestId);
    }

    /// @notice Buyer rejects INCONCLUSIVE result; seller refunds buyer.
    function rejectInconclusive(uint256 id, bytes32 requestId)
        external unique(requestId) notExpired(id) onlyBuyer(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.AUDIT_INCONCLUSIVE, "not inconclusive");

        // Deduct audit costs from bond, refund buyer's escrow + remaining bond.
        uint256 auditCost = x.auditBatch * auditCostPerBatch;
        if (auditCost > x.bond) auditCost = x.bond;
        uint256 buyerRefund = x.buyerEscrow + x.bond - auditCost;
        x.bond = 0;
        x.buyerEscrow = 0;
        credits[x.buyer] += buyerRefund;
        x.state = State.REFUNDED;
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 5: Encrypted Delivery
    // ============================================================

    function commitCiphertext(uint256 id, bytes32 manifestDigest, bytes32 requestId)
        external unique(requestId) notExpired(id) onlySeller(id)
    {
        Listing storage x = listings[id];
        require(
            x.state == State.AUDIT_ACCEPTED || x.state == State.CONDITIONAL,
            "not accepted or conditional"
        );
        require(manifestDigest != bytes32(0), "manifest required");
        x.manifestDigest = manifestDigest;
        x.state = State.CIPHERTEXT_COMMITTED;
        _advance(id, x, requestId);
    }

    function releaseKey(uint256 id, bytes32 envelopeDigest, bytes32 requestId)
        external unique(requestId) onlySeller(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.CIPHERTEXT_COMMITTED, "not ciphertext committed");
        require(envelopeDigest != bytes32(0), "envelope required");
        x.keyEnvelopeDigest = envelopeDigest;
        x.state = State.KEY_RELEASED;
        x.deadline = uint64(block.timestamp + 1 days);
        _advance(id, x, requestId);
    }

    // ============================================================
    // Phase 6: Settlement
    // ============================================================

    function confirm(uint256 id, bytes32 requestId)
        external unique(requestId) notExpired(id) nonReentrant onlyBuyer(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.KEY_RELEASED, "key not released");

        // Buyer confirms: root matches, deliverable accepted.
        x.state = State.CONFIRMED;
        credits[x.seller] += x.price + x.bond;
        x.buyerEscrow = 0;
        x.bond = 0;
        _advance(id, x, requestId);
    }

    /// @notice Buyer disputes: delivered data root does not match cD.
    function dispute(uint256 id, bytes32 requestId)
        external unique(requestId) notExpired(id) nonReentrant onlyBuyer(id)
    {
        Listing storage x = listings[id];
        require(x.state == State.KEY_RELEASED, "key not released");

        x.state = State.DISPUTED;
        emit DisputeOpened(id, x.manifestDigest);
        _advance(id, x, requestId);
    }

    /// @notice Attested dispute resolution via fresh TEE session.
    /// The TEE re-decrypts the chain-bound ciphertext, recomputes the
    /// Poseidon2 root, and outputs a signed delivery receipt.
    function resolveDispute(
        uint256 id,
        bool match_,
        bytes32 recomputedRoot,
        bytes32 sessionId,
        bytes32 requestId
    ) external unique(requestId) nonReentrant {
        Listing storage x = listings[id];
        require(x.state == State.DISPUTED, "not disputed");

        // Attestation check: the session must be valid for this policy.
        attestations.requireValid(sessionId, x.policyHash);

        if (match_) {
            // Delivered data matches listing commitment. Seller wins.
            x.state = State.RESOLVED_SELLER;
            credits[x.seller] += x.price + x.bond;
            x.buyerEscrow = 0;
            x.bond = 0;
        } else {
            // Delivery mismatch. Buyer wins, gets refund + bond.
            x.state = State.RESOLVED_BUYER;
            credits[x.buyer] += x.buyerEscrow + x.bond;
            x.buyerEscrow = 0;
            x.bond = 0;
        }
        emit DisputeResolved(id, match_, recomputedRoot);
        _advance(id, x, requestId);
    }

    // ============================================================
    // Timeout & Abort
    // ============================================================

    /// @notice Any party can abort an expired listing.
    /// Escrow returns to buyer, bond returns to seller (unless fraud proven).
    function abort(uint256 id, bytes32 requestId)
        external unique(requestId) nonReentrant
    {
        Listing storage x = listings[id];
        require(x.deadline > 0 && block.timestamp >= x.deadline, "not expired");
        require(
            x.state != State.CONFIRMED &&
            x.state != State.REFUNDED &&
            x.state != State.RESOLVED_SELLER &&
            x.state != State.RESOLVED_BUYER &&
            x.state != State.ABORTED,
            "already final"
        );

        State prevState = x.state;

        // Refund: buyer gets escrow back, seller gets remaining bond.
        if (x.buyerEscrow > 0) {
            credits[x.buyer] += x.buyerEscrow;
            x.buyerEscrow = 0;
        }
        if (x.bond > 0) {
            // If audit was in progress, deduct audit costs.
            if (prevState == State.AUDITING) {
                uint256 auditCost = x.auditBatch * auditCostPerBatch;
                if (auditCost < x.bond) {
                    credits[x.seller] += x.bond - auditCost;
                }
            } else {
                credits[x.seller] += x.bond;
            }
            x.bond = 0;
        }

        x.state = State.ABORTED;
        _advance(id, x, requestId);
    }

    // ============================================================
    // Withdrawal
    // ============================================================

    function withdraw() external nonReentrant {
        uint256 amount = credits[msg.sender];
        require(amount > 0, "no credits");
        credits[msg.sender] = 0;
        (bool ok,) = payable(msg.sender).call{value: amount}("");
        require(ok, "transfer failed");
    }

    // ============================================================
    // Admin
    // ============================================================

    function setAuditCostPerBatch(uint256 amount) external {
        require(msg.sender == policies.owner(), "only policy owner");
        auditCostPerBatch = amount;
    }

    // ============================================================
    // Internal helpers
    // ============================================================

    function _refundBuyer(Listing storage x) private {
        credits[x.buyer] += x.buyerEscrow + x.bond;
        x.buyerEscrow = 0;
        x.bond = 0;
    }

    function _advance(uint256 id, Listing storage x, bytes32 requestId) private {
        x.transcriptHash = keccak256(
            abi.encode(x.transcriptHash, requestId, x.state, block.number)
        );
        emit StateChanged(id, x.state, x.transcriptHash);
    }
}
