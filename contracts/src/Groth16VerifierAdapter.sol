// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {IZKVerifierAdapter} from "./interfaces/IZKVerifierAdapter.sol";

/// @title Groth16VerifierAdapter
/// @notice Wraps a gnark-exported Groth16 verifier to conform to IZKVerifierAdapter.
///
/// gnark exports a Solidity verifier with the interface:
///   contract Verifier {
///       function verifyProof(
///           uint256[2] calldata a,
///           uint256[2][2] calldata b,
///           uint256[2] calldata c,
///           uint256[] calldata input
///       ) external view returns (bool);
///   }
///
/// This adapter accepts the proof components separately and delegates to
/// the gnark verifier. The proof bytes are expected to be ABI-encoded as
/// (uint256[2] a, uint256[2][2] b, uint256[2] c), matching gnark's
/// serialization format (256 bytes total).
contract Groth16VerifierAdapter is IZKVerifierAdapter {
    address public immutable groth16Verifier;
    uint256 public immutable expectedInputCount;

    constructor(address _groth16Verifier, uint256 _expectedInputCount) {
        require(_groth16Verifier != address(0), "zero verifier");
        require(_expectedInputCount > 0, "zero inputs");
        groth16Verifier = _groth16Verifier;
        expectedInputCount = _expectedInputCount;
    }

    /// @notice Verify a Groth16 proof. The proof is the raw 256-byte gnark
    /// serialization. The publicInputs must match the circuit's public witness
    /// order and count.
    function verify(
        bytes calldata proof,
        uint256[] calldata publicInputs
    ) external view override returns (bool) {
        require(proof.length == 256, "proof length != 256");
        require(publicInputs.length >= expectedInputCount, "too few inputs");

        // Decode proof components.
        uint256[2] memory a;
        uint256[2][2] memory b;
        uint256[2] memory c;

        // Ar.X: bytes 0..31
        a[0] = uint256(bytes32(proof[0:32]));
        // Ar.Y: bytes 32..63
        a[1] = uint256(bytes32(proof[32:64]));
        // Bs[0][0]: bytes 64..95
        b[0][0] = uint256(bytes32(proof[64:96]));
        // Bs[0][1]: bytes 96..127
        b[0][1] = uint256(bytes32(proof[96:128]));
        // Bs[1][0]: bytes 128..159
        b[1][0] = uint256(bytes32(proof[128:160]));
        // Bs[1][1]: bytes 160..191
        b[1][1] = uint256(bytes32(proof[160:192]));
        // Krs.X: bytes 192..223
        c[0] = uint256(bytes32(proof[192:224]));
        // Krs.Y: bytes 224..255
        c[1] = uint256(bytes32(proof[224:256]));

        // Call gnark verifier.
        (bool ok, bytes memory ret) = groth16Verifier.staticcall(
            abi.encodeWithSignature(
                "verifyProof(uint256[2],uint256[2][2],uint256[2],uint256[])",
                a, b, c, publicInputs
            )
        );

        if (!ok || ret.length < 32) return false;
        return abi.decode(ret, (bool));
    }
}
