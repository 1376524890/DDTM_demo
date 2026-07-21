// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

interface IZKVerifierAdapter {
    function verify(bytes calldata proof, uint256[] calldata publicInputs) external view returns (bool);
}
