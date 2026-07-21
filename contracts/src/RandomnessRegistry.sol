// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";
import {ECDSA} from "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import {MessageHashUtils} from "@openzeppelin/contracts/utils/cryptography/MessageHashUtils.sol";

contract RandomnessRegistry is Ownable2Step {
    using ECDSA for bytes32;
    using MessageHashUtils for bytes32;

    struct BeaconRound {
        bytes32 beaconId;
        uint64 round;
        bytes32 signatureHash;
        bytes32 randomness;
        uint64 verifiedAt;
    }

    mapping(address => bool) public relay;
    uint8 public relayThreshold;
    mapping(bytes32 => BeaconRound) public rounds;

    event RoundRegistered(bytes32 indexed key, bytes32 indexed beaconId, uint64 round, bytes32 randomness);

    constructor(address owner_, address[] memory relays_, uint8 threshold_) Ownable(owner_) {
        require(threshold_ > 0 && threshold_ <= relays_.length, "threshold");
        relayThreshold = threshold_;
        for (uint256 i; i < relays_.length; ++i) relay[relays_[i]] = true;
    }

    function key(bytes32 beaconId, uint64 round) public pure returns (bytes32) {
        return keccak256(abi.encode(beaconId, round));
    }

    function registerRound(BeaconRound calldata item, bytes[] calldata signatures) external {
        bytes32 k = key(item.beaconId, item.round);
        require(rounds[k].verifiedAt == 0 && item.randomness != bytes32(0), "round");
        bytes32 digest = keccak256(abi.encode(block.chainid, address(this), item.beaconId, item.round, item.signatureHash, item.randomness)).toEthSignedMessageHash();
        address previous;
        uint256 valid;
        for (uint256 i; i < signatures.length; ++i) {
            address signer = digest.recover(signatures[i]);
            require(relay[signer] && signer > previous, "relay order/duplicate");
            previous = signer;
            ++valid;
        }
        require(valid >= relayThreshold, "relay threshold");
        BeaconRound memory stored = item;
        stored.verifiedAt = uint64(block.timestamp);
        rounds[k] = stored;
        emit RoundRegistered(k, item.beaconId, item.round, item.randomness);
    }
}
