// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Test} from "forge-std/Test.sol";
import {PolicyRegistry} from "../src/PolicyRegistry.sol";

contract PolicyRegistryTest is Test {
    PolicyRegistry public registry;
    address public owner = address(0x1000);
    address public stranger = address(0x9999);

    bytes32 constant TEST_HASH = keccak256("test-policy");

    function setUp() public {
        vm.prank(owner);
        registry = new PolicyRegistry(owner);
    }

    function testSetAndGetPolicy() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        registry.setPolicy(TEST_HASH, p);

        PolicyRegistry.Policy memory stored = registry.getPolicy(TEST_HASH);
        assertEq(stored.maxRows, 100000);
        assertEq(stored.featureCount, 128);
        assertEq(stored.auditBatchSize, 64);
        vm.stopPrank();
    }

    function testOnlyOwnerCanSet() public {
        vm.prank(stranger);
        vm.expectRevert();
        registry.setPolicy(TEST_HASH, _validPolicy());
    }

    function testRejectBadRows() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        p.maxRows = 0;
        vm.expectRevert();
        registry.setPolicy(TEST_HASH, p);
        vm.stopPrank();
    }

    function testRejectBadFeatures() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        p.featureCount = 64;
        vm.expectRevert();
        registry.setPolicy(TEST_HASH, p);
        vm.stopPrank();
    }

    function testRejectBadBatchSize() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        p.auditBatchSize = 128;
        vm.expectRevert();
        registry.setPolicy(TEST_HASH, p);
        vm.stopPrank();
    }

    function testRejectBadThresholds() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        p.tauBadPpm = 40000; // lower than tauGoodPpm=50000
        vm.expectRevert();
        registry.setPolicy(TEST_HASH, p);
        vm.stopPrank();
    }

    function testRejectInactivePolicy() public {
        vm.startPrank(owner);
        PolicyRegistry.Policy memory p = _validPolicy();
        p.active = false;
        registry.setPolicy(TEST_HASH, p);
        vm.stopPrank();

        vm.expectRevert();
        registry.getPolicy(TEST_HASH);
    }

    function testTeeMeasurement() public {
        bytes32 m = keccak256("tee-measurement");
        vm.prank(owner);
        registry.setTeeMeasurement(m, true);
        assertTrue(registry.approvedTeeMeasurements(m));
    }

    function _validPolicy() private view returns (PolicyRegistry.Policy memory) {
        return PolicyRegistry.Policy({
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
    }
}
