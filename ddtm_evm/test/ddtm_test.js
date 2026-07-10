const { expect } = require("chai");
const { ethers, artifacts } = require("hardhat");

describe("DDTMProtocol V1", function () {
  const PRICE = ethers.parseEther("1");
  const BOND = ethers.parseEther("0.1");
  const WINDOW = 60;
  const PROOF = "0x1234";

  let owner;
  let seller;
  let buyer;
  let arbitrator;
  let outsider;
  let qualityVerifier;
  let keyVerifier;
  let deliveryVerifier;
  let ddtm;
  let requestCounter;

  function requestId(label) {
    requestCounter += 1;
    return ethers.keccak256(ethers.toUtf8Bytes(`${label}:${requestCounter}`));
  }

  async function now() {
    return Number((await ethers.provider.getBlock("latest")).timestamp);
  }

  async function deployProtocol() {
    [owner, seller, buyer, arbitrator, outsider] = await ethers.getSigners();

    qualityVerifier = await (await ethers.getContractFactory("MockPiQVerifier")).deploy();
    keyVerifier = await (await ethers.getContractFactory("MockPiKeyVerifier")).deploy();
    deliveryVerifier = await (await ethers.getContractFactory("MockPiDeliverVerifier")).deploy();

    ddtm = await (
      await ethers.getContractFactory("DDTMProtocol")
    ).deploy(
      await qualityVerifier.getAddress(),
      await keyVerifier.getAddress(),
      await deliveryVerifier.getAddress(),
      arbitrator.address,
      WINDOW,
      WINDOW,
      WINDOW,
      WINDOW,
      WINDOW
    );
    await ddtm.waitForDeployment();
    requestCounter = 0;
  }

  async function createListing(overrides = {}) {
    const terms = {
      cD: 11n,
      cQ: 12n,
      cK: 13n,
      zkRoot: 14n,
      objectDigest: ethers.keccak256(ethers.toUtf8Bytes("ciphertext")),
      objectKeyHash: ethers.keccak256(ethers.toUtf8Bytes("ddtm/ciphertext/0")),
      contractHash: ethers.keccak256(ethers.toUtf8Bytes("contract-v1")),
      price: PRICE,
      minPresent: 3n,
      maxValue: 1000n,
      maxAge: 3600n,
      asOfTime: BigInt(await now()),
      nonce: 77n,
      ...overrides,
    };
    const tx = await ddtm.connect(seller).list(terms, requestId("list"), { value: BOND });
    const receipt = await tx.wait();
    const id = (await ddtm.listingCount()) - 1n;
    return { id, terms, receipt };
  }

  async function bid(id, req = requestId("bid")) {
    await ddtm.connect(buyer).bid(id, 123456n, req, { value: PRICE });
  }

  async function verifyQuality(id) {
    await ddtm.connect(seller).submitQualityProof(id, PROOF, 21n, requestId("quality"));
  }

  async function verifyDelivery(id) {
    await ddtm.connect(seller).submitDeliveryProof(id, PROOF, 22n, requestId("delivery"));
  }

  async function releaseKey(id) {
    const envelopeDigest = ethers.keccak256(ethers.toUtf8Bytes("rsa-oaep-envelope"));
    await ddtm
      .connect(seller)
      .submitKeyProof(id, PROOF, 23n, envelopeDigest, 24n, requestId("key"));
  }

  async function reachKeyReleased(id) {
    await bid(id);
    await verifyQuality(id);
    await verifyDelivery(id);
    await releaseKey(id);
  }

  beforeEach(deployProtocol);

  it("runs the complete verifier-gated trade and credits the seller", async function () {
    const { id } = await createListing();
    await reachKeyReleased(id);

    expect(await ddtm.getState(id)).to.equal(4n);
    await ddtm.connect(buyer).confirm(id, requestId("confirm"));

    expect(await ddtm.getState(id)).to.equal(6n);
    expect(await ddtm.credits(seller.address)).to.equal(PRICE + BOND);

    await expect(ddtm.connect(seller).withdraw())
      .to.emit(ddtm, "Withdrawal")
      .withArgs(seller.address, PRICE + BOND);
    expect(await ddtm.credits(seller.address)).to.equal(0n);
  });

  it("rejects a failed quality proof without advancing state", async function () {
    const { id } = await createListing();
    await bid(id);
    await qualityVerifier.setValid(false);

    await expect(
      ddtm.connect(seller).submitQualityProof(id, PROOF, 21n, requestId("bad-quality"))
    ).to.be.revertedWithCustomError(ddtm, "InvalidProof");
    expect(await ddtm.getState(id)).to.equal(1n);
  });

  it("enforces request idempotency on-chain", async function () {
    const { id } = await createListing();
    const duplicate = requestId("duplicate");
    await bid(id, duplicate);

    const { id: secondId } = await createListing({ nonce: 78n });
    await expect(
      ddtm.connect(buyer).bid(secondId, 123456n, duplicate, { value: PRICE })
    )
      .to.be.revertedWithCustomError(ddtm, "DuplicateRequest")
      .withArgs(duplicate);
  });

  it("refunds escrow and slashes the seller bond after quality timeout", async function () {
    const { id } = await createListing();
    await bid(id);
    await ethers.provider.send("evm_increaseTime", [WINDOW + 1]);
    await ethers.provider.send("evm_mine");

    await ddtm.connect(outsider).timeoutQuality(id, requestId("quality-timeout"));
    expect(await ddtm.getState(id)).to.equal(7n);
    expect(await ddtm.credits(buyer.address)).to.equal(PRICE + BOND);
  });

  it("binds disputes to evidence and permits only the configured arbitrator", async function () {
    const { id } = await createListing();
    await reachKeyReleased(id);

    const evidenceHash = ethers.keccak256(ethers.toUtf8Bytes("wrong-key-evidence"));
    const evidenceURIHash = ethers.keccak256(ethers.toUtf8Bytes("minio://evidence/1"));
    await ddtm
      .connect(buyer)
      .openDispute(id, evidenceHash, evidenceURIHash, requestId("dispute"));

    await expect(
      ddtm
        .connect(outsider)
        .resolveDispute(
          id,
          false,
          ethers.keccak256(ethers.toUtf8Bytes("decision")),
          requestId("unauthorized-decision")
        )
    ).to.be.revertedWithCustomError(ddtm, "Unauthorized");

    await ddtm
      .connect(arbitrator)
      .resolveDispute(
        id,
        false,
        ethers.keccak256(ethers.toUtf8Bytes("buyer-wins")),
        requestId("decision")
      );

    expect(await ddtm.getState(id)).to.equal(7n);
    expect(await ddtm.credits(buyer.address)).to.equal(PRICE + BOND);
    const listing = await ddtm.getListing(id);
    expect(listing.evidenceHash).to.equal(evidenceHash);
  });

  it("allows seller settlement after the dispute window expires", async function () {
    const { id } = await createListing();
    await reachKeyReleased(id);
    await ethers.provider.send("evm_increaseTime", [WINDOW + 1]);
    await ethers.provider.send("evm_mine");

    await ddtm.connect(outsider).finalizeAfterDisputeWindow(id, requestId("window-finalize"));
    expect(await ddtm.getState(id)).to.equal(6n);
    expect(await ddtm.credits(seller.address)).to.equal(PRICE + BOND);
  });

  it("restricts abort to the seller and returns the seller bond", async function () {
    const { id } = await createListing();
    await expect(ddtm.connect(outsider).abort(id, requestId("bad-abort"))).to.be.revertedWithCustomError(
      ddtm,
      "Unauthorized"
    );

    await ddtm.connect(seller).abort(id, requestId("abort"));
    expect(await ddtm.getState(id)).to.equal(8n);
    expect(await ddtm.credits(seller.address)).to.equal(BOND);
  });

  it("records a transaction-specific context after bidding", async function () {
    const { id } = await createListing();
    expect(await ddtm.contextOf(id)).to.equal(0n);
    await bid(id);
    const context = await ddtm.contextOf(id);
    expect(context).to.be.greaterThan(0n);
    expect(context).to.be.lessThan(await ddtm.SNARK_SCALAR_FIELD());
  });

  it("keeps deployed runtime bytecode within the EIP-170 limit", async function () {
    const artifact = await artifacts.readArtifact("DDTMProtocol");
    const runtimeBytes = (artifact.deployedBytecode.length - 2) / 2;
    console.log(`DDTM V1 runtime bytecode: ${runtimeBytes} bytes`);
    expect(runtimeBytes).to.be.at.most(24_576);
  });

  it("reports gas for the full state transition path", async function () {
    const { id, receipt: listReceipt } = await createListing({ nonce: 999n });
    const gas = { list: listReceipt.gasUsed };

    let tx = await ddtm.connect(buyer).bid(id, 123456n, requestId("gas-bid"), { value: PRICE });
    gas.bid = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(seller).submitQualityProof(id, PROOF, 21n, requestId("gas-quality"));
    gas.quality = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(seller).submitDeliveryProof(id, PROOF, 22n, requestId("gas-delivery"));
    gas.delivery = (await tx.wait()).gasUsed;
    tx = await ddtm
      .connect(seller)
      .submitKeyProof(
        id,
        PROOF,
        23n,
        ethers.keccak256(ethers.toUtf8Bytes("gas-envelope")),
        24n,
        requestId("gas-key")
      );
    gas.key = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(buyer).confirm(id, requestId("gas-confirm"));
    gas.confirm = (await tx.wait()).gasUsed;

    const total = Object.values(gas).reduce((sum, value) => sum + value, 0n);
    console.log("DDTM V1 gas", Object.fromEntries(Object.entries(gas).map(([k, v]) => [k, v.toString()])), "total", total.toString());
    expect(total).to.be.greaterThan(0n);
  });
});
