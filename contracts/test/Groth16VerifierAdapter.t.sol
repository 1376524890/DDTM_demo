// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Test} from "forge-std/Test.sol";
import {Groth16VerifierAdapter} from "../src/Groth16VerifierAdapter.sol";

/// @title Groth16VerifierAdapterTest
/// @notice Tests for the gnark Groth16 verifier adapter.
///
/// Full testing requires a deployed gnark-exported verifier contract.
/// The tests here validate:
///   - Constructor parameter validation
///   - Proof length checking
///   - Input count enforcement
contract Groth16VerifierAdapterTest is Test {
    address constant MOCK_VERIFIER = address(0x5000);
    uint256 constant EXPECTED_INPUTS = 13;

    function testConstructValid() public {
        Groth16VerifierAdapter adapter = new Groth16VerifierAdapter(
            MOCK_VERIFIER, EXPECTED_INPUTS
        );
        assertEq(adapter.groth16Verifier(), MOCK_VERIFIER);
        assertEq(adapter.expectedInputCount(), EXPECTED_INPUTS);
    }

    function testConstructZeroVerifier() public {
        vm.expectRevert("zero verifier");
        new Groth16VerifierAdapter(address(0), EXPECTED_INPUTS);
    }

    function testConstructZeroInputs() public {
        vm.expectRevert("zero inputs");
        new Groth16VerifierAdapter(MOCK_VERIFIER, 0);
    }

    function testVerifyWrongProofLength() public {
        Groth16VerifierAdapter adapter = new Groth16VerifierAdapter(
            MOCK_VERIFIER, EXPECTED_INPUTS
        );

        // Wrong proof length (not 256 bytes).
        bytes memory shortProof = new bytes(128);
        uint256[] memory inputs = new uint256[](EXPECTED_INPUTS);

        vm.expectRevert("proof length != 256");
        adapter.verify(shortProof, inputs);
    }

    function testVerifyTooFewInputs() public {
        Groth16VerifierAdapter adapter = new Groth16VerifierAdapter(
            MOCK_VERIFIER, EXPECTED_INPUTS
        );

        bytes memory proof = new bytes(256);
        uint256[] memory inputs = new uint256[](5);

        vm.expectRevert("too few inputs");
        adapter.verify(proof, inputs);
    }

    function testVerifyCorrectFormat() public {
        Groth16VerifierAdapter adapter = new Groth16VerifierAdapter(
            MOCK_VERIFIER, EXPECTED_INPUTS
        );

        bytes memory proof = new bytes(256);
        uint256[] memory inputs = new uint256[](EXPECTED_INPUTS);

        // The mock verifier doesn't exist, so the call will fail.
        // This tests that the adapter does NOT revert on format errors
        // but instead returns false from the failed staticcall.
        bool result = adapter.verify(proof, inputs);
        assertFalse(result, "should return false for nonexistent verifier");
    }
}
