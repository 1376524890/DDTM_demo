// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";
import {PolicyRegistry} from "./PolicyRegistry.sol";

contract AttestationRegistry is Ownable2Step {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    struct Session {
        bytes32 measurement;
        bytes32 reportDataHash;
        bytes32 policyHash;
        bytes32 ephemeralKeyHash;
        uint64 expiresAt;
        bool revoked;
    }

    PolicyRegistry public immutable policyRegistry;
    mapping(address => bool) public relay;
    uint8 public relayThreshold;
    mapping(bytes32 => Session) public sessions;

    event SessionRegistered(bytes32 indexed sessionId, bytes32 measurement, bytes32 reportDataHash, uint64 expiresAt);

    constructor(address owner_, PolicyRegistry registry_, address[] memory relays_, uint8 threshold_) Ownable(owner_) {
        require(threshold_ > 0 && threshold_ <= relays_.length, "threshold");
        policyRegistry = registry_;
        relayThreshold = threshold_;
        for (uint256 i; i < relays_.length; ++i) relay[relays_[i]] = true;
    }

    function registerSession(
        bytes32 sessionId,
        Session calldata session,
        bytes[] calldata relaySignatures
    ) external {
        require(sessionId != bytes32(0) && sessions[sessionId].expiresAt == 0, "session");
        require(policyRegistry.approvedTeeMeasurements(session.measurement), "measurement");
        require(session.expiresAt > block.timestamp, "expired");
        bytes32 digest = keccak256(abi.encode(block.chainid, address(this), sessionId, session)).toEthSignedMessageHash();
        address previous;
        uint256 valid;
        for (uint256 i; i < relaySignatures.length; ++i) {
            address signer = digest.recover(relaySignatures[i]);
            require(relay[signer] && signer > previous, "relay order/duplicate");
            previous = signer;
            ++valid;
        }
        require(valid >= relayThreshold, "relay threshold");
        sessions[sessionId] = session;
        emit SessionRegistered(sessionId, session.measurement, session.reportDataHash, session.expiresAt);
    }

    function requireValid(bytes32 sessionId, bytes32 policyHash) external view returns (Session memory session) {
        session = sessions[sessionId];
        require(!session.revoked && session.expiresAt >= block.timestamp, "invalid session");
        require(session.policyHash == policyHash, "policy mismatch");
    }
}
