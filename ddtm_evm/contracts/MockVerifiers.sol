// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockPiQVerifier {
    bool public valid = true;

    function setValid(bool value) external {
        valid = value;
    }

    function verifyProof(bytes calldata proof, uint256[8] calldata) external view {
        require(valid && proof.length > 0, "invalid quality proof");
    }
}

contract MockPiKeyVerifier {
    bool public valid = true;

    function setValid(bool value) external {
        valid = value;
    }

    function verifyProof(bytes calldata proof, uint256[6] calldata) external view {
        require(valid && proof.length > 0, "invalid key proof");
    }
}

contract MockPiDeliverVerifier {
    bool public valid = true;

    function setValid(bool value) external {
        valid = value;
    }

    function verifyProof(bytes calldata proof, uint256[6] calldata) external view {
        require(valid && proof.length > 0, "invalid delivery proof");
    }
}
