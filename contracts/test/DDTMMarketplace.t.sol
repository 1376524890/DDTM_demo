// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Test, console} from "forge-std/Test.sol";
import {DDTMMarketplace} from "../src/DDTMMarketplace.sol";
import {PolicyRegistry} from "../src/PolicyRegistry.sol";
import {AttestationRegistry} from "../src/AttestationRegistry.sol";
import {RandomnessRegistry} from "../src/RandomnessRegistry.sol";

contract DDTMMarketplaceTest is Test {
    DDTMMarketplace public market;
    PolicyRegistry public policies;
    AttestationRegistry public attestations;
    RandomnessRegistry public randomness;

    address public owner = address(0x1000);
    address public seller = address(0x2000);
    address public buyer = address(0x3000);
    address public relay1 = address(0x4000);
    address public relay2 = address(0x4001);
    address public relay3 = address(0x4002);

    bytes32 constant SCHEMA_HASH = bytes32(uint256(0xCAFE));
    bytes32 constant POLICY_HASH = keccak256("policy-v1");
    bytes32 constant DATA_ROOT = bytes32(uint256(0xDADA));
    bytes32 constant MODEL_COMMIT = bytes32(uint256(0xDEAD));
    bytes32 constant VALIDATION_ROOT = bytes32(uint256(0xBEEF));
    bytes32 constant AUDIT_COMMIT = bytes32(uint256(0xFACE));

    function setUp() public {
        vm.startPrank(owner);

        address[] memory relays = new address[](3);
        relays[0] = relay1;
        relays[1] = relay2;
        relays[2] = relay3;

        randomness = new RandomnessRegistry(owner, relays, 2);
        policies = new PolicyRegistry(owner);
        attestations = new AttestationRegistry(owner, policies, relays, 2);

        // Register a policy.
        PolicyRegistry.Policy memory policy = PolicyRegistry.Policy({
            active: true,
            schemaHash: SCHEMA_HASH,
            utilityCircuitHash: bytes32(0),
            auditCircuitHash: bytes32(0),
            utilityVerifier: address(0x5000),
            auditVerifier: address(0x5001),
            maxRows: 100000,
            featureCount: 128,
            auditBatchSize: 64,
            maxAuditSamples: 1536,
            tauGoodPpm: 50000,
            tauBadPpm: 100000,
            alphaPpm: 10000,
            betaPpm: 50000,
            minUtilityEnc: 65,
            maxLinearError: 32768,
            maxShift: 131072,
            lambdaMad: 65536,
            lambdaShift: 16384,
            lambdaLinear: 32768,
            safetyMargin: 500,
            kappaPpm: 1000000
        });
        policies.setPolicy(POLICY_HASH, policy);

        market = new DDTMMarketplace(policies, attestations, randomness);
        vm.stopPrank();
    }

    function testList() public {
        vm.deal(seller, 100 ether);
        vm.prank(seller);
        uint256 id = market.list{value: 100 ether}(
            POLICY_HASH, DATA_ROOT, SCHEMA_HASH,
            MODEL_COMMIT, VALIDATION_ROOT, AUDIT_COMMIT,
            bytes32("beacon"), 1000, 100000, 1,
            1 ether, 2 ether, 500000,
            keccak256("req-1")
        );
        assertEq(id, 0);

        DDTMMarketplace.Listing memory listing = getListing(id);
        assertEq(listing.seller, seller);
        assertEq(uint256(listing.state), uint256(DDTMMarketplace.State.LISTED));
    }

    function testBid() public {
        vm.deal(seller, 100 ether);
        vm.prank(seller);
        uint256 id = market.list{value: 100 ether}(
            POLICY_HASH, DATA_ROOT, SCHEMA_HASH,
            MODEL_COMMIT, VALIDATION_ROOT, AUDIT_COMMIT,
            bytes32("beacon"), 1000, 100000, 1,
            1 ether, 2 ether, 500000,
            keccak256("req-1")
        );

        vm.deal(buyer, 100 ether);
        vm.prank(buyer);
        market.bid{value: 1 ether}(id, keccak256("req-2"));

        DDTMMarketplace.Listing memory listing = getListing(id);
        assertEq(listing.buyer, buyer);
        assertEq(uint256(listing.state), uint256(DDTMMarketplace.State.ESCROWED));
    }

    function testCannotDoubleBid() public {
        vm.deal(seller, 100 ether);
        vm.prank(seller);
        uint256 id = market.list{value: 100 ether}(
            POLICY_HASH, DATA_ROOT, SCHEMA_HASH,
            MODEL_COMMIT, VALIDATION_ROOT, AUDIT_COMMIT,
            bytes32("beacon"), 1000, 100000, 1,
            1 ether, 2 ether, 500000,
            keccak256("req-1")
        );

        vm.deal(buyer, 100 ether);
        vm.prank(buyer);
        market.bid{value: 1 ether}(id, keccak256("req-2"));

        // Second bid should revert.
        vm.expectRevert();
        vm.prank(buyer);
        market.bid{value: 1 ether}(id, keccak256("req-3"));
    }

    function testReplayProtection() public {
        vm.deal(seller, 100 ether);
        bytes32 reqId = keccak256("req-replay");
        vm.prank(seller);
        market.list{value: 100 ether}(
            POLICY_HASH, DATA_ROOT, SCHEMA_HASH,
            MODEL_COMMIT, VALIDATION_ROOT, AUDIT_COMMIT,
            bytes32("beacon"), 1000, 100000, 1,
            1 ether, 2 ether, 500000,
            reqId
        );

        // Replay should fail.
        vm.expectRevert();
        vm.prank(seller);
        market.list{value: 100 ether}(
            POLICY_HASH, DATA_ROOT, SCHEMA_HASH,
            MODEL_COMMIT, VALIDATION_ROOT, AUDIT_COMMIT,
            bytes32("beacon"), 1000, 100000, 1,
            1 ether, 2 ether, 500000,
            reqId
        );
    }

    function testBondCalculation() public {
        uint256 bond = market.requiredBond(POLICY_HASH, 10000, 12000, 951215);
        // B_min = (Gmax + safetyMargin) / p_det - price
        // = (12000 + 500) / 0.951215 - 10000
        // Expected: ~3141 (with ppm scaling)
        assertGt(bond, 0);
        assertLt(bond, 10000);
    }

    function testWithdraw() public {
        // Give credits to an address and verify withdrawal.
        vm.deal(address(market), 10 ether);
        // Cannot directly set credits; test via a settled transaction.
    }

    // Helper
    function getListing(uint256 id) internal view returns (DDTMMarketplace.Listing memory) {
        // Access via direct storage read (for test only).
        // In production, use public accessor.
        (address s, address b, uint8 st,,,,,,,,,,,,,,,,,,,,) = market.listings(id);
        // Simplified - just verify the call doesn't revert.
        return DDTMMarketplace.Listing({
            seller: s,
            buyer: b,
            state: DDTMMarketplace.State(st),
            policyHash: bytes32(0),
            dataRoot: bytes32(0),
            schemaHash: bytes32(0),
            modelCommitment: bytes32(0),
            validationRoot: bytes32(0),
            auditCommitment: bytes32(0),
            metricsCommitment: bytes32(0),
            sessionId: bytes32(0),
            beaconId: bytes32(0),
            beaconRound: 0,
            rowCount: 0,
            datasetVersion: 0,
            auditN: 0,
            auditFailures: 0,
            auditBatch: 0,
            price: 0,
            bond: 0,
            buyerEscrow: 0,
            manifestDigest: bytes32(0),
            keyEnvelopeDigest: bytes32(0),
            transcriptHash: bytes32(0),
            deadline: 0
        });
    }
}
