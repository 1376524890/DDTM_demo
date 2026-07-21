// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Test} from "forge-std/Test.sol";
import {AttestationRegistry} from "../src/AttestationRegistry.sol";
import {PolicyRegistry} from "../src/PolicyRegistry.sol";

contract AttestationRegistryTest is Test {
    AttestationRegistry public registry;
    PolicyRegistry public policies;
    address public owner = address(0x1000);
    address public relay1 = address(0x4000);
    address public relay2 = address(0x4001);
    address public relay3 = address(0x4002);

    // Anvil default key #1
    uint256 constant RELAY_KEY_1 = 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d;
    uint256 constant RELAY_KEY_2 = 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a;

    bytes32 constant TEST_POLICY = keccak256("test-policy");
    bytes32 constant GOOD_MEASUREMENT = keccak256("good-mrenclave");

    function setUp() public {
        vm.startPrank(owner);

        address[] memory relays = new address[](3);
        relays[0] = relay1;
        relays[1] = relay2;
        relays[2] = relay3;

        policies = new PolicyRegistry(owner);
        registry = new AttestationRegistry(owner, policies, relays, 2);

        // Set up policy and approved measurement.
        PolicyRegistry.Policy memory p = PolicyRegistry.Policy({
            active: true,
            schemaHash: bytes32(uint256(0xCAFE)),
            utilityCircuitHash: bytes32(0),
            auditCircuitHash: bytes32(0),
            utilityVerifier: address(0x100),
            auditVerifier: address(0x200),
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
        policies.setPolicy(TEST_POLICY, p);
        policies.setTeeMeasurement(GOOD_MEASUREMENT, true);
        vm.stopPrank();
    }

    function testRejectBadMeasurement() public {
        // Try to register a session with an unapproved measurement.
        bytes32 badMeasurement = keccak256("bad-mrenclave");
        AttestationRegistry.Session memory session = AttestationRegistry.Session({
            measurement: badMeasurement,
            reportDataHash: bytes32(uint256(0x1234)),
            policyHash: TEST_POLICY,
            ephemeralKeyHash: bytes32(uint256(0x5678)),
            expiresAt: uint64(block.timestamp + 3600),
            revoked: false
        });

        bytes[] memory sigs = new bytes[](2);
        bytes32 digest = keccak256(abi.encode(block.chainid, address(registry), bytes32(uint256(0xCAFE)), session));
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(RELAY_KEY_1, digest);
        sigs[0] = abi.encodePacked(r1, s1, v1);
        (uint8 v2, bytes32 r2, bytes32 s2) = vm.sign(RELAY_KEY_2, digest);
        sigs[1] = abi.encodePacked(r2, s2, v2);

        vm.expectRevert();
        registry.registerSession(bytes32(uint256(0xCAFE)), session, sigs);
    }

    function testOnlyPolicyOwnerCanSetMeasurement() public {
        address stranger = address(0x9999);
        vm.prank(stranger);
        vm.expectRevert();
        policies.setTeeMeasurement(GOOD_MEASUREMENT, false);
    }

    function testSetTeeMeasurementByOwner() public {
        vm.prank(owner);
        policies.setTeeMeasurement(GOOD_MEASUREMENT, true);
        assertTrue(policies.approvedTeeMeasurements(GOOD_MEASUREMENT));
    }
}
