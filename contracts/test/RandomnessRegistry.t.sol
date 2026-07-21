// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Test} from "forge-std/Test.sol";
import {RandomnessRegistry} from "../src/RandomnessRegistry.sol";

contract RandomnessRegistryTest is Test {
    RandomnessRegistry public registry;
    address public owner = address(0x1000);
    address public relay1 = address(0x4000);
    address public relay2 = address(0x4001);

    uint256 constant R1_KEY = 0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d;
    uint256 constant R2_KEY = 0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a;

    bytes32 constant BEACON_ID = bytes32("test-beacon");
    uint64 constant ROUND = 12345;

    function setUp() public {
        address[] memory relays = new address[](2);
        relays[0] = relay1;
        relays[1] = relay2;

        vm.prank(owner);
        registry = new RandomnessRegistry(owner, relays, 2);
    }

    function testRegisterRound() public {
        RandomnessRegistry.BeaconRound memory br = RandomnessRegistry.BeaconRound({
            beaconId: BEACON_ID,
            round: ROUND,
            signatureHash: keccak256("drnd-sig"),
            randomness: keccak256("drnd-randomness-00112233"),
            verifiedAt: 0
        });

        bytes32 digest = keccak256(
            abi.encode(block.chainid, address(registry), br.beaconId, br.round, br.signatureHash, br.randomness)
        );
        bytes32 ethDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));

        bytes[] memory sigs = new bytes[](2);
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(R1_KEY, ethDigest);
        sigs[0] = abi.encodePacked(r1, s1, v1);
        (uint8 v2, bytes32 r2, bytes32 s2) = vm.sign(R2_KEY, ethDigest);
        sigs[1] = abi.encodePacked(r2, s2, v2);

        registry.registerRound(br, sigs);

        bytes32 key = registry.key(BEACON_ID, ROUND);
        RandomnessRegistry.BeaconRound memory stored = registry.rounds(key);
        assertEq(stored.randomness, br.randomness);
        assertGt(stored.verifiedAt, 0);
    }

    function testCannotDoubleRegister() public {
        RandomnessRegistry.BeaconRound memory br = RandomnessRegistry.BeaconRound({
            beaconId: BEACON_ID,
            round: ROUND,
            signatureHash: keccak256("sig"),
            randomness: keccak256("rnd"),
            verifiedAt: 0
        });

        bytes32 digest = keccak256(
            abi.encode(block.chainid, address(registry), br.beaconId, br.round, br.signatureHash, br.randomness)
        );
        bytes32 ethDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));

        bytes[] memory sigs = new bytes[](2);
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(R1_KEY, ethDigest);
        sigs[0] = abi.encodePacked(r1, s1, v1);
        (uint8 v2, bytes32 r2, bytes32 s2) = vm.sign(R2_KEY, ethDigest);
        sigs[1] = abi.encodePacked(r2, s2, v2);

        registry.registerRound(br, sigs);

        vm.expectRevert();
        registry.registerRound(br, sigs);
    }

    function testInsufficientSignatures() public {
        RandomnessRegistry.BeaconRound memory br = RandomnessRegistry.BeaconRound({
            beaconId: BEACON_ID,
            round: ROUND,
            signatureHash: keccak256("sig"),
            randomness: keccak256("rnd"),
            verifiedAt: 0
        });

        bytes32 digest = keccak256(
            abi.encode(block.chainid, address(registry), br.beaconId, br.round, br.signatureHash, br.randomness)
        );
        bytes32 ethDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));

        // Only 1 signature (need 2).
        bytes[] memory sigs = new bytes[](1);
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(R1_KEY, ethDigest);
        sigs[0] = abi.encodePacked(r1, s1, v1);

        vm.expectRevert();
        registry.registerRound(br, sigs);
    }

    function testKeyDeterminism() public {
        bytes32 k1 = registry.key(BEACON_ID, ROUND);
        bytes32 k2 = registry.key(BEACON_ID, ROUND);
        assertEq(k1, k2);

        bytes32 k3 = registry.key(BEACON_ID, ROUND + 1);
        assertTrue(k1 != k3);
    }

    function testZeroRandomnessRejected() public {
        RandomnessRegistry.BeaconRound memory br = RandomnessRegistry.BeaconRound({
            beaconId: BEACON_ID,
            round: ROUND,
            signatureHash: keccak256("sig"),
            randomness: bytes32(0),
            verifiedAt: 0
        });

        bytes32 digest = keccak256(
            abi.encode(block.chainid, address(registry), br.beaconId, br.round, br.signatureHash, br.randomness)
        );
        bytes32 ethDigest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", digest));

        bytes[] memory sigs = new bytes[](2);
        (uint8 v1, bytes32 r1, bytes32 s1) = vm.sign(R1_KEY, ethDigest);
        sigs[0] = abi.encodePacked(r1, s1, v1);
        (uint8 v2, bytes32 r2, bytes32 s2) = vm.sign(R2_KEY, ethDigest);
        sigs[1] = abi.encodePacked(r2, s2, v2);

        vm.expectRevert();
        registry.registerRound(br, sigs);
    }
}
