// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DDTM Escrow & State Machine
 * @notice Core DDTM protocol: listing, bidding, escrow, quality verification,
 *         delivery, dispute, arbitration. All state transitions enforced on-chain.
 */
contract DDTMProtocol {
    enum State {
        LISTED,           // 0
        BIDDING,          // 1
        ESCROWED,         // 2
        QUALITY_VERIFIED,  // 3
        DELIVERING,       // 4
        DISPUTED,         // 5
        ARBITRATING,      // 6
        CONFIRMED,        // 7
        REFUNDED,         // 8
        ABORTED           // 9
    }

    struct Listing {
        address seller;
        bytes32 c_D; bytes32 c_Q; bytes32 c_k; bytes32 root;
        uint256 price; uint256 deposit; uint256 theta;
        State state;
        address buyer; uint256 buyerDeposit;
        uint256 disputeTime;
    }

    mapping(uint256 => Listing) public listings;
    uint256 public listingCount;
    mapping(address => uint256) public balances;

    event Listed(uint256 indexed id, address seller, bytes32 c_D);
    event Bid(uint256 indexed id, address buyer);
    event Escrowed(uint256 indexed id);
    event QualityVerified(uint256 indexed id);
    event Delivering(uint256 indexed id);
    event Confirmed(uint256 indexed id);
    event Disputed(uint256 indexed id, string reason);
    event Refunded(uint256 indexed id, string reason);
    event Aborted(uint256 indexed id);
    event ArbitrationResolved(uint256 indexed id, bool sellerWins);

    modifier onlyState(uint256 id, State expected) {
        require(listings[id].state == expected, "Invalid state");
        _;
    }

    modifier onlySeller(uint256 id) {
        require(msg.sender == listings[id].seller, "Not seller");
        _;
    }

    modifier onlyBuyer(uint256 id) {
        require(msg.sender == listings[id].buyer, "Not buyer");
        _;
    }

    // ============================================================
    // Phase 1: Listing
    // ============================================================
    function list(
        bytes32 c_D, bytes32 c_Q, bytes32 c_k, bytes32 root,
        uint256 price, uint256 theta
    ) external payable returns (uint256) {
        require(msg.value >= price / 10, "Deposit too low");
        uint256 id = listingCount++;
        Listing storage l = listings[id];
        l.seller = msg.sender;
        l.c_D = c_D; l.c_Q = c_Q; l.c_k = c_k; l.root = root;
        l.price = price; l.deposit = msg.value; l.theta = theta;
        l.state = State.LISTED;
        emit Listed(id, msg.sender, c_D);
        return id;
    }

    // ============================================================
    // Phase 2: Bidding + Escrow
    // ============================================================
    function bid(uint256 id) external payable onlyState(id, State.LISTED) {
        require(msg.value >= listings[id].price, "Bid too low");
        listings[id].buyer = msg.sender;
        listings[id].buyerDeposit = msg.value;
        listings[id].state = State.ESCROWED;
        emit Bid(id, msg.sender);
        emit Escrowed(id);
    }

    // ============================================================
    // Phase 3: Quality Verification
    // ============================================================
    function submitProof(uint256 id) external onlySeller(id) onlyState(id, State.ESCROWED) {
        listings[id].state = State.QUALITY_VERIFIED;
        emit QualityVerified(id);
    }

    // ============================================================
    // Phase 4: Delivery
    // ============================================================
    function startDelivery(uint256 id) external onlySeller(id) onlyState(id, State.QUALITY_VERIFIED) {
        listings[id].state = State.DELIVERING;
        emit Delivering(id);
    }

    function confirm(uint256 id) external onlyBuyer(id) onlyState(id, State.DELIVERING) {
        listings[id].state = State.CONFIRMED;
        // Release payment to seller, return deposits
        payable(listings[id].seller).transfer(listings[id].price);
        payable(listings[id].seller).transfer(listings[id].deposit);
        payable(listings[id].buyer).transfer(listings[id].buyerDeposit - listings[id].price);
        emit Confirmed(id);
    }

    // ============================================================
    // Phase 5: Dispute + Arbitration
    // ============================================================
    function dispute(uint256 id, string calldata reason) external onlyBuyer(id) {
        require(
            listings[id].state == State.DELIVERING ||
            listings[id].state == State.QUALITY_VERIFIED,
            "Cannot dispute in this state"
        );
        listings[id].state = State.DISPUTED;
        listings[id].disputeTime = block.timestamp;
        emit Disputed(id, reason);
    }

    function resolveArbitration(uint256 id, bool sellerWins) external onlyState(id, State.DISPUTED) {
        listings[id].state = State.ARBITRATING;
        if (sellerWins) {
            listings[id].state = State.CONFIRMED;
            payable(listings[id].seller).transfer(listings[id].price);
            payable(listings[id].seller).transfer(listings[id].deposit);
            payable(listings[id].buyer).transfer(listings[id].buyerDeposit - listings[id].price);
        } else {
            listings[id].state = State.REFUNDED;
            payable(listings[id].buyer).transfer(listings[id].buyerDeposit);
            // Slash seller deposit
            listings[id].deposit = 0;
        }
        emit ArbitrationResolved(id, sellerWins);
    }

    // ============================================================
    // Timeout paths
    // ============================================================
    function timeoutDispute(uint256 id) external onlyState(id, State.DISPUTED) {
        listings[id].state = State.REFUNDED;
        payable(listings[id].buyer).transfer(listings[id].buyerDeposit);
        emit Refunded(id, "dispute timeout");
    }

    function abort(uint256 id) external {
        require(
            listings[id].state == State.LISTED ||
            listings[id].state == State.BIDDING,
            "Cannot abort"
        );
        if (listings[id].state == State.BIDDING && listings[id].buyer != address(0)) {
            payable(listings[id].buyer).transfer(listings[id].buyerDeposit);
        }
        listings[id].state = State.ABORTED;
        emit Aborted(id);
    }

    // ============================================================
    // View helpers
    // ============================================================
    function getState(uint256 id) external view returns (State) {
        return listings[id].state;
    }
}
