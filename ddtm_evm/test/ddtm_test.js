const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("DDTM Protocol — Full State Machine & Performance", function () {
  let ddtm, seller, buyer, arbitrator;
  const PRICE = ethers.parseEther("1.0");
  const DEPOSIT = ethers.parseEther("0.1");
  const THETA = 80;

  before(async function () {
    const [owner, s, b, a] = await ethers.getSigners();
    seller = s; buyer = b; arbitrator = a;
    const DDTM = await ethers.getContractFactory("DDTMProtocol");
    ddtm = await DDTM.deploy();
    await ddtm.waitForDeployment();
    await owner.sendTransaction({ to: seller.address, value: ethers.parseEther("10") });
    await owner.sendTransaction({ to: buyer.address, value: ethers.parseEther("10") });
  });

  const stateNames = ["LISTED","BIDDING","ESCROWED","QUALITY_VERIFIED","DELIVERING",
                      "DISPUTED","ARBITRATING","CONFIRMED","REFUNDED","ABORTED"];

  async function checkState(id, name) {
    const s = await ddtm.getState(id);
    expect(s).to.equal(stateNames.indexOf(name));
  }

  async function doList() {
    const cD = ethers.keccak256(ethers.toUtf8Bytes("d"));
    const cQ = ethers.keccak256(ethers.toUtf8Bytes("q"));
    const cK = ethers.keccak256(ethers.toUtf8Bytes("k"));
    const root = ethers.keccak256(ethers.toUtf8Bytes("r"));
    const tx = await ddtm.connect(seller).list(cD, cQ, cK, root, PRICE, THETA, { value: DEPOSIT });
    const r = await tx.wait();
    return { id: await ddtm.listingCount() - 1n, gas: r.gasUsed };
  }

  it("Scenario 1: Normal trade → CONFIRMED", async () => {
    const {id} = await doList();
    await ddtm.connect(buyer).bid(id, { value: PRICE });
    await ddtm.connect(seller).submitProof(id);
    await ddtm.connect(seller).startDelivery(id);
    await ddtm.connect(buyer).confirm(id);
    await checkState(id, "CONFIRMED");
  });

  it("Scenario 2: Wrong key → DISPUTED → REFUNDED", async () => {
    const {id} = await doList();
    await ddtm.connect(buyer).bid(id, { value: PRICE });
    await ddtm.connect(seller).submitProof(id);
    await ddtm.connect(seller).startDelivery(id);
    await ddtm.connect(buyer).dispute(id, "wrong_key");
    await checkState(id, "DISPUTED");
    await ddtm.connect(arbitrator).resolveArbitration(id, false);
    await checkState(id, "REFUNDED");
  });

  it("Scenario 3: Seller wins dispute → CONFIRMED", async () => {
    const {id} = await doList();
    await ddtm.connect(buyer).bid(id, { value: PRICE });
    await ddtm.connect(seller).submitProof(id);
    await ddtm.connect(seller).startDelivery(id);
    await ddtm.connect(buyer).dispute(id, "false_claim");
    await ddtm.connect(arbitrator).resolveArbitration(id, true);
    await checkState(id, "CONFIRMED");
  });

  it("Scenario 4: Abort listing → ABORTED", async () => {
    const {id} = await doList();
    await ddtm.connect(seller).abort(id);
    await checkState(id, "ABORTED");
  });

  it("Scenario 5: Seller refuses → REFUNDED via timeout", async () => {
    const {id} = await doList();
    await ddtm.connect(buyer).bid(id, { value: PRICE });
    await ddtm.connect(seller).submitProof(id);
    await ddtm.connect(seller).startDelivery(id);
    // Buyer does NOT confirm - timeout the dispute
    await ddtm.connect(buyer).dispute(id, "no_delivery");
    await checkState(id, "DISPUTED");
    await ethers.provider.send("evm_increaseTime", [7200]);
    await ethers.provider.send("evm_mine");
    await ddtm.timeoutDispute(id);
    await checkState(id, "REFUNDED");
  });

  // ============================================================
  // Performance: Gas Benchmarks
  // ============================================================
  it("Performance: Gas costs", async () => {
    const cD = ethers.keccak256(ethers.toUtf8Bytes("gd"));
    const cQ = ethers.keccak256(ethers.toUtf8Bytes("gq"));
    const cK = ethers.keccak256(ethers.toUtf8Bytes("gk"));
    const root = ethers.keccak256(ethers.toUtf8Bytes("gr"));
    let tx = await ddtm.connect(seller).list(cD, cQ, cK, root, PRICE, THETA, { value: DEPOSIT });
    const listGas = (await tx.wait()).gasUsed;
    const id = await ddtm.listingCount() - 1n;
    tx = await ddtm.connect(buyer).bid(id, { value: PRICE });
    const bidGas = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(seller).submitProof(id);
    const proofGas = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(seller).startDelivery(id);
    const delivGas = (await tx.wait()).gasUsed;
    tx = await ddtm.connect(buyer).confirm(id);
    const confGas = (await tx.wait()).gasUsed;

    console.log(`\n=== DDTM EVM Gas (Hardhat Local) ===`);
    console.log(`  listing:     ${String(listGas).padStart(7)}`);
    console.log(`  bidding:     ${String(bidGas).padStart(7)}`);
    console.log(`  submitProof: ${String(proofGas).padStart(7)}`);
    console.log(`  delivery:    ${String(delivGas).padStart(7)}`);
    console.log(`  confirm:     ${String(confGas).padStart(7)}`);
    console.log(`  TOTAL:       ${String(listGas+bidGas+proofGas+delivGas+confGas).padStart(7)}`);
  });

  // ============================================================
  // Performance: Concurrent TPS
  // ============================================================
  it("Performance: Concurrent TPS (50 listings)", async () => {
    const N = 50;
    const start = Date.now();
    const ps = [];
    for (let i = 0; i < N; i++) {
      const cD = ethers.keccak256(ethers.toUtf8Bytes(`d${i}`));
      const cQ = ethers.keccak256(ethers.toUtf8Bytes(`q${i}`));
      const cK = ethers.keccak256(ethers.toUtf8Bytes(`k${i}`));
      const root = ethers.keccak256(ethers.toUtf8Bytes(`r${i}`));
      ps.push(ddtm.connect(seller).list(cD, cQ, cK, root, PRICE, THETA, { value: DEPOSIT }).then(tx => tx.wait()));
    }
    await Promise.all(ps);
    const tps = N / ((Date.now() - start) / 1000);
    console.log(`\n=== Concurrent Load ===`);
    console.log(`  ${N} listings in ${((Date.now()-start)/1000).toFixed(1)}s → ${tps.toFixed(1)} TPS`);
    expect(tps).to.be.gt(1);
  });
});
