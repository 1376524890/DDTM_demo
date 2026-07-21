// SPDX-License-Identifier: MIT
pragma solidity ^0.8.30;

import {Ownable2Step} from "@openzeppelin/contracts/access/Ownable2Step.sol";

contract PolicyRegistry is Ownable2Step {
    struct Policy {
        bool active;
        bytes32 schemaHash;
        bytes32 utilityCircuitHash;
        bytes32 auditCircuitHash;
        address utilityVerifier;
        address auditVerifier;
        uint64 maxRows;
        uint32 featureCount;
        uint32 auditBatchSize;
        uint32 maxAuditSamples;
        uint64 tauGoodPpm;
        uint64 tauBadPpm;
        uint64 alphaPpm;
        uint64 betaPpm;
        uint256 minUtilityEnc;
        uint256 maxLinearError;
        uint256 maxShift;
        uint256 lambdaMad;
        uint256 lambdaShift;
        uint256 lambdaLinear;
        uint256 safetyMargin;
        uint256 kappaPpm;
    }

    mapping(bytes32 => Policy) private policies;
    mapping(bytes32 => bool) public approvedTeeMeasurements;
    event PolicySet(bytes32 indexed policyHash, Policy policy);
    event TeeMeasurementSet(bytes32 indexed measurement, bool approved);

    constructor(address initialOwner) Ownable(initialOwner) {}

    function setPolicy(bytes32 policyHash, Policy calldata policy) external onlyOwner {
        require(policyHash != bytes32(0), "policy hash");
        require(policy.maxRows > 0 && policy.maxRows <= 100_000, "rows");
        require(policy.featureCount == 128, "features");
        require(policy.auditBatchSize == 64, "batch");
        require(policy.tauGoodPpm < policy.tauBadPpm, "thresholds");
        require(policy.utilityVerifier != address(0) && policy.auditVerifier != address(0), "verifier");
        policies[policyHash] = policy;
        emit PolicySet(policyHash, policy);
    }

    function setTeeMeasurement(bytes32 measurement, bool approved) external onlyOwner {
        approvedTeeMeasurements[measurement] = approved;
        emit TeeMeasurementSet(measurement, approved);
    }

    function getPolicy(bytes32 policyHash) external view returns (Policy memory) {
        Policy memory policy = policies[policyHash];
        require(policy.active, "inactive policy");
        return policy;
    }
}
