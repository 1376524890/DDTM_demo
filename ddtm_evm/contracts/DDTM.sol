// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IPiQVerifier {
    function verifyProof(bytes calldata proof, uint256[8] calldata input) external view;
}

interface IPiKeyVerifier {
    function verifyProof(bytes calldata proof, uint256[5] calldata input) external view;
}

interface IPiDeliverVerifier {
    function verifyProof(bytes calldata proof, uint256[5] calldata input) external view;
}

/**
 * @title DDTMProtocol V1
 * @notice Reference implementation of the DDTM protocol on an EVM-compatible chain.
 *         Large ciphertexts are stored off-chain in MinIO. The contract stores immutable
 *         commitments, object digests, proof bindings and the complete escrow state machine.
 */
contract DDTMProtocol {
    uint256 public constant SNARK_SCALAR_FIELD =
        21888242871839275222246405745257275088548364400416034343698204186575808495617;

    enum State {
        LISTED,
        ESCROWED,
        QUALITY_VERIFIED,
        DELIVERED,
        KEY_RELEASED,
        DISPUTED,
        CONFIRMED,
        REFUNDED,
        ABORTED
    }

    struct ListingTerms {
        uint256 cD;
        uint256 cQ;
        uint256 cK;
        uint256 zkRoot;
        bytes32 objectDigest;
        bytes32 objectKeyHash;
        bytes32 contractHash;
        uint256 price;
        uint256 minPresent;
        uint256 maxValue;
        uint256 maxAge;
        uint64 asOfTime;
        uint256 nonce;
    }

    struct Listing {
        bytes32 tid;
        address seller;
        address buyer;
        State state;
        uint256 cD;
        uint256 cQ;
        uint256 cK;
        uint256 zkRoot;
        bytes32 objectDigest;
        bytes32 objectKeyHash;
        bytes32 contractHash;
        uint256 price;
        uint256 sellerBond;
        uint256 buyerEscrow;
        uint256 minPresent;
        uint256 maxValue;
        uint256 maxAge;
        uint64 asOfTime;
        uint256 nonce;
        uint256 buyerKey;
        uint256 keyEnvelope;
        bytes32 keyEnvelopeDigest;
        bytes32 evidenceHash;
        bytes32 evidenceURIHash;
        uint64 qualityDeadline;
        uint64 deliveryDeadline;
        uint64 keyDeadline;
        uint64 disputeDeadline;
        uint64 arbitrationDeadline;
    }

    error Unauthorized();
    error InvalidState(State actual, State expected);
    error InvalidValue();
    error InvalidProof(bytes32 proofType);
    error DuplicateRequest(bytes32 requestId);
    error DeadlineNotReached();
    error DeadlineExpired();
    error TransferFailed();

    IPiQVerifier public immutable qualityVerifier;
    IPiKeyVerifier public immutable keyVerifier;
    IPiDeliverVerifier public immutable deliveryVerifier;
    address public owner;
    address public arbitrator;

    uint64 public immutable qualityWindow;
    uint64 public immutable deliveryWindow;
    uint64 public immutable keyWindow;
    uint64 public immutable disputeWindow;
    uint64 public immutable arbitrationWindow;

    uint256 public listingCount;
    mapping(uint256 => Listing) private _listings;
    mapping(address => uint256) public credits;
    mapping(bytes32 => bool) public consumedRequests;

    event ListingCreated(
        uint256 indexed id,
        bytes32 indexed tid,
        address indexed seller,
        uint256 cD,
        uint256 cQ,
        uint256 cK,
        uint256 zkRoot,
        bytes32 objectDigest,
        bytes32 objectKeyHash,
        bytes32 requestId
    );
    event EscrowLocked(
        uint256 indexed id,
        bytes32 indexed tid,
        address indexed buyer,
        uint256 amount,
        uint256 buyerKey,
        uint256 context,
        bytes32 requestId
    );
    event QualityVerified(uint256 indexed id, bytes32 indexed tid, bytes32 proofHash, uint256 binding, bytes32 requestId);
    event DeliveryVerified(uint256 indexed id, bytes32 indexed tid, bytes32 proofHash, uint256 binding, bytes32 requestId);
    event KeyReleased(
        uint256 indexed id,
        bytes32 indexed tid,
        bytes32 proofHash,
        uint256 keyEnvelope,
        bytes32 keyEnvelopeDigest,
        uint256 binding,
        bytes32 requestId
    );
    event DisputeOpened(
        uint256 indexed id,
        bytes32 indexed tid,
        bytes32 evidenceHash,
        bytes32 evidenceURIHash,
        uint64 arbitrationDeadline,
        bytes32 requestId
    );
    event DisputeResolved(
        uint256 indexed id,
        bytes32 indexed tid,
        bool sellerWins,
        bytes32 decisionHash,
        bytes32 requestId
    );
    event Finalized(uint256 indexed id, bytes32 indexed tid, State finalState, bytes32 reason, bytes32 requestId);
    event Withdrawal(address indexed account, uint256 amount);
    event ArbitratorChanged(address indexed previousArbitrator, address indexed newArbitrator);

    constructor(
        address qualityVerifier_,
        address keyVerifier_,
        address deliveryVerifier_,
        address arbitrator_,
        uint64 qualityWindow_,
        uint64 deliveryWindow_,
        uint64 keyWindow_,
        uint64 disputeWindow_,
        uint64 arbitrationWindow_
    ) {
        if (
            qualityVerifier_ == address(0) ||
            keyVerifier_ == address(0) ||
            deliveryVerifier_ == address(0) ||
            arbitrator_ == address(0) ||
            qualityWindow_ == 0 ||
            deliveryWindow_ == 0 ||
            keyWindow_ == 0 ||
            disputeWindow_ == 0 ||
            arbitrationWindow_ == 0
        ) revert InvalidValue();

        qualityVerifier = IPiQVerifier(qualityVerifier_);
        keyVerifier = IPiKeyVerifier(keyVerifier_);
        deliveryVerifier = IPiDeliverVerifier(deliveryVerifier_);
        owner = msg.sender;
        arbitrator = arbitrator_;
        qualityWindow = qualityWindow_;
        deliveryWindow = deliveryWindow_;
        keyWindow = keyWindow_;
        disputeWindow = disputeWindow_;
        arbitrationWindow = arbitrationWindow_;
    }

    modifier onlyOwner() {
        if (msg.sender != owner) revert Unauthorized();
        _;
    }

    modifier onlySeller(uint256 id) {
        if (msg.sender != _listings[id].seller) revert Unauthorized();
        _;
    }

    modifier onlyBuyer(uint256 id) {
        if (msg.sender != _listings[id].buyer) revert Unauthorized();
        _;
    }

    modifier inState(uint256 id, State expected) {
        State actual = _listings[id].state;
        if (actual != expected) revert InvalidState(actual, expected);
        _;
    }

    modifier idempotent(bytes32 requestId) {
        if (requestId == bytes32(0)) revert InvalidValue();
        if (consumedRequests[requestId]) revert DuplicateRequest(requestId);
        consumedRequests[requestId] = true;
        _;
    }

    function list(ListingTerms calldata terms, bytes32 requestId)
        external
        payable
        idempotent(requestId)
        returns (uint256 id, bytes32 tid)
    {
        if (
            terms.cD >= SNARK_SCALAR_FIELD ||
            terms.cQ >= SNARK_SCALAR_FIELD ||
            terms.cK >= SNARK_SCALAR_FIELD ||
            terms.zkRoot >= SNARK_SCALAR_FIELD ||
            terms.objectDigest == bytes32(0) ||
            terms.objectKeyHash == bytes32(0) ||
            terms.contractHash == bytes32(0) ||
            terms.price == 0 ||
            terms.minPresent == 0 ||
            terms.asOfTime == 0
        ) revert InvalidValue();

        uint256 requiredBond = terms.price / 10;
        if (requiredBond == 0) requiredBond = 1;
        if (msg.value < requiredBond) revert InvalidValue();

        id = listingCount++;
        tid = keccak256(
            abi.encode(
                block.chainid,
                address(this),
                id,
                msg.sender,
                terms.contractHash,
                terms.nonce
            )
        );

        Listing storage item = _listings[id];
        item.tid = tid;
        item.seller = msg.sender;
        item.state = State.LISTED;
        item.cD = terms.cD;
        item.cQ = terms.cQ;
        item.cK = terms.cK;
        item.zkRoot = terms.zkRoot;
        item.objectDigest = terms.objectDigest;
        item.objectKeyHash = terms.objectKeyHash;
        item.contractHash = terms.contractHash;
        item.price = terms.price;
        item.sellerBond = msg.value;
        item.minPresent = terms.minPresent;
        item.maxValue = terms.maxValue;
        item.maxAge = terms.maxAge;
        item.asOfTime = terms.asOfTime;
        item.nonce = terms.nonce;

        emit ListingCreated(
            id,
            tid,
            msg.sender,
            terms.cD,
            terms.cQ,
            terms.cK,
            terms.zkRoot,
            terms.objectDigest,
            terms.objectKeyHash,
            requestId
        );
    }

    function bid(uint256 id, uint256 buyerKey, bytes32 requestId)
        external
        payable
        inState(id, State.LISTED)
        idempotent(requestId)
    {
        Listing storage item = _listings[id];
        if (msg.sender == item.seller || msg.value != item.price || buyerKey == 0 || buyerKey >= SNARK_SCALAR_FIELD) {
            revert InvalidValue();
        }

        item.buyer = msg.sender;
        item.buyerEscrow = msg.value;
        item.buyerKey = buyerKey;
        item.qualityDeadline = uint64(block.timestamp) + qualityWindow;
        item.state = State.ESCROWED;

        emit EscrowLocked(id, item.tid, msg.sender, msg.value, buyerKey, contextOf(id), requestId);
    }

    function submitQualityProof(uint256 id, bytes calldata proof, uint256 binding, bytes32 requestId)
        external
        onlySeller(id)
        inState(id, State.ESCROWED)
        idempotent(requestId)
    {
        Listing storage item = _listings[id];
        if (block.timestamp > item.qualityDeadline || binding >= SNARK_SCALAR_FIELD) revert DeadlineExpired();

        uint256[8] memory input = [
            item.cD,
            item.cQ,
            item.minPresent,
            item.maxValue,
            item.maxAge,
            uint256(item.asOfTime),
            contextOf(id),
            binding
        ];
        try qualityVerifier.verifyProof(proof, input) {
            item.deliveryDeadline = uint64(block.timestamp) + deliveryWindow;
            item.state = State.QUALITY_VERIFIED;
        } catch {
            revert InvalidProof("PI_Q");
        }

        emit QualityVerified(id, item.tid, keccak256(proof), binding, requestId);
    }

    function submitDeliveryProof(uint256 id, bytes calldata proof, uint256 binding, bytes32 requestId)
        external
        onlySeller(id)
        inState(id, State.QUALITY_VERIFIED)
        idempotent(requestId)
    {
        Listing storage item = _listings[id];
        if (block.timestamp > item.deliveryDeadline || binding >= SNARK_SCALAR_FIELD) revert DeadlineExpired();

        uint256[5] memory input = [item.cD, item.cK, item.zkRoot, contextOf(id), binding];
        try deliveryVerifier.verifyProof(proof, input) {
            item.keyDeadline = uint64(block.timestamp) + keyWindow;
            item.state = State.DELIVERED;
        } catch {
            revert InvalidProof("PI_DELIVER");
        }

        emit DeliveryVerified(id, item.tid, keccak256(proof), binding, requestId);
    }

    function submitKeyProof(
        uint256 id,
        bytes calldata proof,
        uint256 keyEnvelope,
        bytes32 keyEnvelopeDigest,
        uint256 binding,
        bytes32 requestId
    ) external onlySeller(id) inState(id, State.DELIVERED) idempotent(requestId) {
        Listing storage item = _listings[id];
        if (
            block.timestamp > item.keyDeadline ||
            keyEnvelope == 0 ||
            keyEnvelope >= SNARK_SCALAR_FIELD ||
            keyEnvelopeDigest == bytes32(0) ||
            binding >= SNARK_SCALAR_FIELD
        ) revert DeadlineExpired();

        uint256[5] memory input = [item.cK, item.buyerKey, keyEnvelope, contextOf(id), binding];
        try keyVerifier.verifyProof(proof, input) {
            item.keyEnvelope = keyEnvelope;
            item.keyEnvelopeDigest = keyEnvelopeDigest;
            item.disputeDeadline = uint64(block.timestamp) + disputeWindow;
            item.state = State.KEY_RELEASED;
        } catch {
            revert InvalidProof("PI_KEY");
        }

        emit KeyReleased(
            id,
            item.tid,
            keccak256(proof),
            keyEnvelope,
            keyEnvelopeDigest,
            binding,
            requestId
        );
    }

    function confirm(uint256 id, bytes32 requestId)
        external
        onlyBuyer(id)
        inState(id, State.KEY_RELEASED)
        idempotent(requestId)
    {
        _settleSeller(id, "BUYER_CONFIRMED", requestId);
    }

    function finalizeAfterDisputeWindow(uint256 id, bytes32 requestId)
        external
        inState(id, State.KEY_RELEASED)
        idempotent(requestId)
    {
        if (block.timestamp <= _listings[id].disputeDeadline) revert DeadlineNotReached();
        _settleSeller(id, "DISPUTE_WINDOW_EXPIRED", requestId);
    }

    function openDispute(
        uint256 id,
        bytes32 evidenceHash,
        bytes32 evidenceURIHash,
        bytes32 requestId
    ) external onlyBuyer(id) inState(id, State.KEY_RELEASED) idempotent(requestId) {
        Listing storage item = _listings[id];
        if (block.timestamp > item.disputeDeadline) revert DeadlineExpired();
        if (evidenceHash == bytes32(0) || evidenceURIHash == bytes32(0)) revert InvalidValue();

        item.evidenceHash = evidenceHash;
        item.evidenceURIHash = evidenceURIHash;
        item.arbitrationDeadline = uint64(block.timestamp) + arbitrationWindow;
        item.state = State.DISPUTED;

        emit DisputeOpened(
            id,
            item.tid,
            evidenceHash,
            evidenceURIHash,
            item.arbitrationDeadline,
            requestId
        );
    }

    function resolveDispute(
        uint256 id,
        bool sellerWins,
        bytes32 decisionHash,
        bytes32 requestId
    ) external inState(id, State.DISPUTED) idempotent(requestId) {
        if (msg.sender != arbitrator) revert Unauthorized();
        if (decisionHash == bytes32(0)) revert InvalidValue();
        if (block.timestamp > _listings[id].arbitrationDeadline) revert DeadlineExpired();

        emit DisputeResolved(id, _listings[id].tid, sellerWins, decisionHash, requestId);
        if (sellerWins) {
            _settleSeller(id, "ARBITRATION_SELLER", requestId);
        } else {
            _refundBuyer(id, "ARBITRATION_BUYER", requestId);
        }
    }

    function timeoutQuality(uint256 id, bytes32 requestId)
        external
        inState(id, State.ESCROWED)
        idempotent(requestId)
    {
        if (block.timestamp <= _listings[id].qualityDeadline) revert DeadlineNotReached();
        _refundBuyer(id, "QUALITY_TIMEOUT", requestId);
    }

    function timeoutDelivery(uint256 id, bytes32 requestId)
        external
        inState(id, State.QUALITY_VERIFIED)
        idempotent(requestId)
    {
        if (block.timestamp <= _listings[id].deliveryDeadline) revert DeadlineNotReached();
        _refundBuyer(id, "DELIVERY_TIMEOUT", requestId);
    }

    function timeoutKey(uint256 id, bytes32 requestId)
        external
        inState(id, State.DELIVERED)
        idempotent(requestId)
    {
        if (block.timestamp <= _listings[id].keyDeadline) revert DeadlineNotReached();
        _refundBuyer(id, "KEY_TIMEOUT", requestId);
    }

    function timeoutArbitration(uint256 id, bytes32 requestId)
        external
        inState(id, State.DISPUTED)
        idempotent(requestId)
    {
        if (block.timestamp <= _listings[id].arbitrationDeadline) revert DeadlineNotReached();
        _refundBuyer(id, "ARBITRATION_TIMEOUT", requestId);
    }

    function abort(uint256 id, bytes32 requestId)
        external
        onlySeller(id)
        inState(id, State.LISTED)
        idempotent(requestId)
    {
        Listing storage item = _listings[id];
        item.state = State.ABORTED;
        uint256 bond = item.sellerBond;
        item.sellerBond = 0;
        credits[item.seller] += bond;
        emit Finalized(id, item.tid, State.ABORTED, "SELLER_ABORTED", requestId);
    }

    function withdraw() external {
        uint256 amount = credits[msg.sender];
        if (amount == 0) revert InvalidValue();
        credits[msg.sender] = 0;
        (bool ok, ) = payable(msg.sender).call{value: amount}("");
        if (!ok) revert TransferFailed();
        emit Withdrawal(msg.sender, amount);
    }

    function setArbitrator(address newArbitrator) external onlyOwner {
        if (newArbitrator == address(0)) revert InvalidValue();
        address old = arbitrator;
        arbitrator = newArbitrator;
        emit ArbitratorChanged(old, newArbitrator);
    }

    function transferOwnership(address newOwner) external onlyOwner {
        if (newOwner == address(0)) revert InvalidValue();
        owner = newOwner;
    }

    function contextOf(uint256 id) public view returns (uint256) {
        Listing storage item = _listings[id];
        if (item.buyer == address(0)) return 0;
        return
            uint256(
                keccak256(
                    abi.encode(
                        item.tid,
                        block.chainid,
                        address(this),
                        item.contractHash,
                        item.seller,
                        item.buyer,
                        item.nonce
                    )
                )
            ) % SNARK_SCALAR_FIELD;
    }

    function getListing(uint256 id) external view returns (Listing memory) {
        return _listings[id];
    }

    function getState(uint256 id) external view returns (State) {
        return _listings[id].state;
    }

    function _settleSeller(uint256 id, bytes32 reason, bytes32 requestId) private {
        Listing storage item = _listings[id];
        uint256 amount = item.price + item.sellerBond;
        item.buyerEscrow = 0;
        item.sellerBond = 0;
        item.state = State.CONFIRMED;
        credits[item.seller] += amount;
        emit Finalized(id, item.tid, State.CONFIRMED, reason, requestId);
    }

    function _refundBuyer(uint256 id, bytes32 reason, bytes32 requestId) private {
        Listing storage item = _listings[id];
        uint256 amount = item.buyerEscrow + item.sellerBond;
        item.buyerEscrow = 0;
        item.sellerBond = 0;
        item.state = State.REFUNDED;
        credits[item.buyer] += amount;
        emit Finalized(id, item.tid, State.REFUNDED, reason, requestId);
    }
}
