const { expect } = require("chai");
const { ethers } = require("hardhat");
const { spawnSync } = require("node:child_process");
const path = require("node:path");

const describeReal = process.env.DDTM_V1_REAL_ZKP === "1" ? describe : describe.skip;

describeReal("DDTM V1 real Groth16 integration", function () {
  this.timeout(300_000);

  const proverBinary = process.env.DDTM_V1_PROVER_BIN ?? path.resolve(__dirname, "../../ddtm_zkp/bin/v1prove");
  const artifacts = process.env.DDTM_V1_ZKP_ARTIFACTS ?? path.resolve(__dirname, "../../ddtm_zkp/artifacts/v1");
  const field = BigInt("21888242871839275222246405745257275088548364400416034343698204186575808495617");

  const witness = {
    blocks: [
      "10", "1900", "1", "0",
      "20", "1910", "1", "0",
      "30", "1920", "1", "0",
      "0", "1930", "0", "0",
    ],
    encRand: Array.from({ length: 16 }, (_, i) => String(100 + i)),
    key: "123456789",
    rD: "2001",
    rQ: "2002",
    rK: "2003",
    rEnc: "2004",
    minPresent: "3",
    maxValue: "100",
    maxAge: "200",
    asOfTime: "2000",
    context: "0",
    buyerKey: "0",
  };

  function prove(type, request) {
    const child = spawnSync(
      proverBinary,
      ["--type", type, "--artifacts", artifacts],
      { input: JSON.stringify(request), encoding: "utf8" }
    );
    if (child.status !== 0) {
      throw new Error(`v1prove ${type} failed: ${child.stderr || child.stdout}`);
    }
    return JSON.parse(child.stdout);
  }

  it("runs LISTED through CONFIRMED with three generated proofs", async function () {
    const [, seller, buyer, arbitrator] = await ethers.getSigners();
    const piQ = await (await ethers.getContractFactory("PiQVerifier")).deploy();
    const piKey = await (await ethers.getContractFactory("PiKeyVerifier")).deploy();
    const piDeliver = await (await ethers.getContractFactory("PiDeliverVerifier")).deploy();
    const ddtm = await (
      await ethers.getContractFactory("DDTMProtocol")
    ).deploy(
      await piQ.getAddress(),
      await piKey.getAddress(),
      await piDeliver.getAddress(),
      arbitrator.address,
      600,
      600,
      600,
      600,
      600
    );

    const commitments = prove("commitments", witness).commitments;
    const objectDigest = ethers.sha256(ethers.toUtf8Bytes("minio-ciphertext-v1"));
    const objectDigestField = (BigInt(objectDigest) % field).toString();
    const terms = {
      cD: commitments.cD,
      cQ: commitments.cQ,
      cK: commitments.cK,
      zkRoot: commitments.zkRoot,
      objectDigest,
      objectKeyHash: ethers.keccak256(ethers.toUtf8Bytes("ciphertexts/test.json")),
      contractHash: ethers.sha256(ethers.toUtf8Bytes("contract-v1")),
      price: ethers.parseEther("1"),
      minPresent: 3,
      maxValue: 100,
      maxAge: 200,
      asOfTime: 2000,
      nonce: 44,
    };

    await ddtm.connect(seller).list(terms, ethers.id("real-list"), { value: ethers.parseEther("0.1") });
    await ddtm.connect(buyer).bid(0, 987654321, ethers.id("real-bid"), { value: ethers.parseEther("1") });
    const context = (await ddtm.contextOf(0)).toString();

    const quality = prove("quality", { ...witness, context, buyerKey: "987654321" });
    expect(quality.publicInputs[6]).to.equal(context);
    await ddtm.connect(seller).submitQualityProof(0, quality.proof, quality.binding, ethers.id("real-quality"));

    const delivery = prove("delivery", {
      ...witness,
      context,
      buyerKey: "987654321",
      objectDigestField,
    });
    await ddtm.connect(seller).submitDeliveryProof(0, delivery.proof, delivery.binding, ethers.id("real-delivery"));

    const envelopeDigest = ethers.sha256(ethers.toUtf8Bytes("rsa-oaep-envelope-v1"));
    const envelopeDigestField = (BigInt(envelopeDigest) % field).toString();
    const key = prove("key", {
      ...witness,
      context,
      buyerKey: "987654321",
      envelopeDigestField,
    });
    await ddtm
      .connect(seller)
      .submitKeyProof(0, key.proof, key.keyEnvelope, envelopeDigest, key.binding, ethers.id("real-key"));

    expect(await ddtm.getState(0)).to.equal(4n);
    await ddtm.connect(buyer).confirm(0, ethers.id("real-confirm"));
    expect(await ddtm.getState(0)).to.equal(6n);
    expect(await ddtm.credits(seller.address)).to.equal(ethers.parseEther("1.1"));
  });

  it("rejects a proof replayed under a different transaction context", async function () {
    const [, seller, buyer, arbitrator] = await ethers.getSigners();
    const piQ = await (await ethers.getContractFactory("PiQVerifier")).deploy();
    const piKey = await (await ethers.getContractFactory("PiKeyVerifier")).deploy();
    const piDeliver = await (await ethers.getContractFactory("PiDeliverVerifier")).deploy();
    const ddtm = await (
      await ethers.getContractFactory("DDTMProtocol")
    ).deploy(
      await piQ.getAddress(),
      await piKey.getAddress(),
      await piDeliver.getAddress(),
      arbitrator.address,
      600,
      600,
      600,
      600,
      600
    );
    const commitments = prove("commitments", witness).commitments;
    const baseTerms = {
      cD: commitments.cD,
      cQ: commitments.cQ,
      cK: commitments.cK,
      zkRoot: commitments.zkRoot,
      objectDigest: ethers.sha256(ethers.toUtf8Bytes("ciphertext")),
      objectKeyHash: ethers.keccak256(ethers.toUtf8Bytes("object")),
      contractHash: ethers.sha256(ethers.toUtf8Bytes("contract")),
      price: ethers.parseEther("1"),
      minPresent: 3,
      maxValue: 100,
      maxAge: 200,
      asOfTime: 2000,
      nonce: 1,
    };
    await ddtm.connect(seller).list(baseTerms, ethers.id("replay-list-1"), { value: ethers.parseEther("0.1") });
    await ddtm.connect(seller).list({ ...baseTerms, nonce: 2 }, ethers.id("replay-list-2"), { value: ethers.parseEther("0.1") });
    await ddtm.connect(buyer).bid(0, 99, ethers.id("replay-bid-1"), { value: ethers.parseEther("1") });
    await ddtm.connect(buyer).bid(1, 99, ethers.id("replay-bid-2"), { value: ethers.parseEther("1") });

    const proofForFirst = prove("quality", {
      ...witness,
      context: (await ddtm.contextOf(0)).toString(),
      buyerKey: "99",
    });
    await expect(
      ddtm.connect(seller).submitQualityProof(1, proofForFirst.proof, proofForFirst.binding, ethers.id("replay-proof"))
    ).to.be.revertedWithCustomError(ddtm, "InvalidProof");
  });
});
