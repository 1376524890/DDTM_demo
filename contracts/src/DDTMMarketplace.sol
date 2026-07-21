// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {PolicyRegistry} from "./PolicyRegistry.sol";
import {AttestationRegistry} from "./AttestationRegistry.sol";
import {RandomnessRegistry} from "./RandomnessRegistry.sol";
import {IZKVerifierAdapter} from "./interfaces/IZKVerifierAdapter.sol";

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

    PolicyRegistry public immutable policies;
    AttestationRegistry public immutable attestations;
    RandomnessRegistry public immutable randomness;
    uint256 public listingCount;
    mapping(uint256 => Listing) public listings;
    mapping(address => uint256) public credits;
    mapping(bytes32 => bool) public consumedRequest;

    // Per-policy SPRT constants (set together with policy).
    struct SprtParams {
        int256 hitIncrementQ32;
        int256 cleanIncrementQ32;
        int256 upperQ32;
        int256 lowerQ32;
    }
    mapping(bytes32 => SprtParams) public sprtParams;

    event StateChanged(uint256 indexed id, State state, bytes32 transcriptHash);

    modifier unique(bytes32 requestId) {
        require(requestId != bytes32(0) && !consumedRequest[requestId], "request");
        consumedRequest[requestId] = true;
        _;
    }

    constructor(PolicyRegistry p, AttestationRegistry a, RandomnessRegistry r) {
        policies = p; attestations = a; randomness = r;
    }

    function requiredBond(bytes32 policyHash, uint256 price, uint256 gMax, uint256 detectionPpm) public view returns (uint256) {
        PolicyRegistry.Policy memory p = policies.getPolicy(policyHash);
        require(detectionPpm > 0 && detectionPpm <= 1_000_000, "detection");
        uint256 covered = ((gMax + p.safetyMargin) * 1_000_000 + detectionPpm - 1) / detectionPpm;
        return covered > price ? covered - price : 0;
    }

    function list(
        bytes32 policyHash, bytes32 dataRoot, bytes32 schemaHash, bytes32 modelCommitment,
        bytes32 validationRoot, bytes32 auditCommitment, bytes32 beaconId, uint64 beaconRound,
        uint64 rowCount, uint64 datasetVersion, uint256 price, uint256 gMax,
        uint256 detectionPpm, bytes32 requestId
    ) external payable unique(requestId) returns (uint256 id) {
        PolicyRegistry.Policy memory p = policies.getPolicy(policyHash);
        require(schemaHash == p.schemaHash && rowCount > 0 && rowCount <= p.maxRows, "schema/rows");
        uint256 bond = requiredBond(policyHash, price, gMax, detectionPpm);
        require(msg.value >= bond && price > 0, "bond/price");
        id = listingCount++;
        listings[id] = Listing({
            seller: msg.sender, buyer: address(0), state: State.LISTED,
            policyHash: policyHash, dataRoot: dataRoot, schemaHash: schemaHash,
            modelCommitment: modelCommitment, validationRoot: validationRoot,
            auditCommitment: auditCommitment, metricsCommitment: bytes32(0),
            sessionId: bytes32(0), beaconId: beaconId, beaconRound: beaconRound,
            rowCount: rowCount, datasetVersion: datasetVersion, auditN: 0,
            auditFailures: 0, auditBatch: 0, price: price, bond: msg.value,
            buyerEscrow: 0, manifestDigest: bytes32(0), keyEnvelopeDigest: bytes32(0),
            transcriptHash: keccak256(abi.encode(requestId, dataRoot, policyHash)), deadline: 0
        });
        emit StateChanged(id, State.LISTED, listings[id].transcriptHash);
    }

    function bid(uint256 id, bytes32 requestId) external payable unique(requestId) {
        Listing storage x = listings[id];
        require(x.state == State.LISTED && msg.sender != x.seller && msg.value == x.price, "bid");
        x.buyer = msg.sender; x.buyerEscrow = msg.value; x.state = State.ESCROWED;
        x.deadline = uint64(block.timestamp + 1 days); advance(id, x, requestId);
    }

    function registerSession(uint256 id, bytes32 sessionId, bytes32 requestId) external unique(requestId) {
        Listing storage x = listings[id];
        require(msg.sender == x.seller && x.state == State.ESCROWED, "session state");
        attestations.requireValid(sessionId, x.policyHash);
        x.sessionId = sessionId; x.state = State.TEE_REGISTERED; advance(id, x, requestId);
    }

    function submitUtility(
        uint256 id, bytes32 metricsCommitment, bytes calldata proof,
        uint256[] calldata publicInputs, bytes32 requestId
    ) external unique(requestId) {
        Listing storage x = listings[id];
        require(msg.sender == x.seller && x.state == State.TEE_REGISTERED, "utility state");
        PolicyRegistry.Policy memory p = policies.getPolicy(x.policyHash);
        require(IZKVerifierAdapter(p.utilityVerifier).verify(proof, publicInputs), "utility proof");
        // Adapter must expose inputs in the registry-defined order. The coordinator
        // checks exact equality before transaction submission; critical commitments
        // are also repeated here.
        require(publicInputs.length >= 5, "utility inputs");
        require(bytes32(publicInputs[1]) == x.dataRoot, "data root");
        require(bytes32(publicInputs[4]) == metricsCommitment, "metrics");
        x.metricsCommitment = metricsCommitment; x.state = State.UTILITY_VERIFIED;
        x.deadline = uint64(block.timestamp + 1 days); advance(id, x, requestId);
    }

    function startAudit(uint256 id, bytes32 requestId) external unique(requestId) {
        Listing storage x = listings[id];
        require(x.state == State.UTILITY_VERIFIED, "audit state");
        RandomnessRegistry.BeaconRound memory b = randomness.rounds(randomness.key(x.beaconId, x.beaconRound));
        require(b.verifiedAt != 0, "randomness unavailable");
        x.state = State.AUDITING; advance(id, x, requestId);
    }

    function submitAuditBatch(
        uint256 id, uint32 newN, uint32 newFailures, bytes calldata proof,
        uint256[] calldata publicInputs, bytes32 requestId
    ) external unique(requestId) {
        Listing storage x = listings[id];
        require(msg.sender == x.seller && x.state == State.AUDITING, "audit batch state");
        PolicyRegistry.Policy memory p = policies.getPolicy(x.policyHash);
        require(newN == x.auditN + p.auditBatchSize && newN <= p.maxAuditSamples, "audit n");
        require(newFailures >= x.auditFailures && newFailures <= newN, "audit failures");
        require(IZKVerifierAdapter(p.auditVerifier).verify(proof, publicInputs), "audit proof");
        x.auditN = newN; x.auditFailures = newFailures; x.auditBatch += 1;
        advance(id, x, requestId);
    }

    function setSprtParams(bytes32 policyHash, SprtParams calldata params) external {
        require(msg.sender == address(policies.owner()), "only policy owner");
        require(sprtParams[policyHash].hitIncrementQ32 == 0, "already set");
        sprtParams[policyHash] = params;
    }

    function decideAudit(uint256 id, bytes32 requestId) external unique(requestId) {
        Listing storage x = listings[id];
        require(x.state == State.AUDITING, "decision state");
        require(x.auditN > 0, "no audit data");

        SprtParams memory sp = sprtParams[x.policyHash];
        require(sp.hitIncrementQ32 != 0, "SPRT not configured");

        // Compute LLR: failures*hit + (n-failures)*clean
        int256 failures = int256(uint256(x.auditFailures));
        int256 clean = int256(x.auditN) - failures;
        int256 llr = failures * sp.hitIncrementQ32 + clean * sp.cleanIncrementQ32;
        llr = llr / (1 << 32);

        if (llr >= sp.upperQ32 / (1 << 32)) {
            x.state = State.AUDIT_REJECTED;
            refundBuyer(x);
        } else if (llr <= sp.lowerQ32 / (1 << 32)) {
            x.state = State.AUDIT_ACCEPTED;
        } else if (x.auditN >= policies.getPolicy(x.policyHash).maxAuditSamples) {
            x.state = State.AUDIT_INCONCLUSIVE;
        } else {
            revert("audit not yet decisive; submit more batches");
        }
        advance(id, x, requestId);
    }

    function commitCiphertext(uint256 id, bytes32 manifestDigest, bytes32 requestId) external unique(requestId) {
        Listing storage x = listings[id];
        require(msg.sender == x.seller && x.state == State.AUDIT_ACCEPTED && manifestDigest != bytes32(0), "manifest");
        x.manifestDigest = manifestDigest; x.state = State.CIPHERTEXT_COMMITTED; advance(id, x, requestId);
    }

    function releaseKey(uint256 id, bytes32 envelopeDigest, bytes32 requestId) external unique(requestId) {
        Listing storage x = listings[id];
        require(msg.sender == x.seller && x.state == State.CIPHERTEXT_COMMITTED && envelopeDigest != bytes32(0), "key");
        x.keyEnvelopeDigest = envelopeDigest; x.state = State.KEY_RELEASED;
        x.deadline = uint64(block.timestamp + 1 days); advance(id, x, requestId);
    }

    function confirm(uint256 id, bytes32 requestId) external unique(requestId) nonReentrant {
        Listing storage x = listings[id];
        require(msg.sender == x.buyer && x.state == State.KEY_RELEASED, "confirm");
        x.state = State.CONFIRMED;
        credits[x.seller] += x.price + x.bond;
        x.buyerEscrow = 0; x.bond = 0; advance(id, x, requestId);
    }

    function withdraw() external nonReentrant {
        uint256 amount = credits[msg.sender]; require(amount > 0, "credit");
        credits[msg.sender] = 0;
        (bool ok,) = payable(msg.sender).call{value: amount}(""); require(ok, "transfer");
    }

    function refundBuyer(Listing storage x) private {
        credits[x.buyer] += x.buyerEscrow + x.bond;
        x.buyerEscrow = 0; x.bond = 0;
    }

    function advance(uint256 id, Listing storage x, bytes32 requestId) private {
        x.transcriptHash = keccak256(abi.encode(x.transcriptHash, requestId, x.state, block.number));
        emit StateChanged(id, x.state, x.transcriptHash);
    }
}
