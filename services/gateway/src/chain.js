import { readFile } from "node:fs/promises";
import { Contract, Interface, JsonRpcProvider, Wallet } from "ethers";

const ABI = [
  "function list((uint256 cD,uint256 cQ,uint256 cK,uint256 zkRoot,bytes32 objectDigest,bytes32 objectKeyHash,bytes32 contractHash,uint256 price,uint256 minPresent,uint256 maxValue,uint256 maxAge,uint64 asOfTime,uint256 nonce) terms,bytes32 requestId) payable returns (uint256 id,bytes32 tid)",
  "function bid(uint256 id,uint256 buyerKey,bytes32 requestId) payable",
  "function submitQualityProof(uint256 id,bytes proof,uint256 binding,bytes32 requestId)",
  "function submitDeliveryProof(uint256 id,bytes proof,uint256 binding,bytes32 requestId)",
  "function submitKeyProof(uint256 id,bytes proof,uint256 keyEnvelope,bytes32 keyEnvelopeDigest,uint256 binding,bytes32 requestId)",
  "function confirm(uint256 id,bytes32 requestId)",
  "function finalizeAfterDisputeWindow(uint256 id,bytes32 requestId)",
  "function openDispute(uint256 id,bytes32 evidenceHash,bytes32 evidenceURIHash,bytes32 requestId)",
  "function resolveDispute(uint256 id,bool sellerWins,bytes32 decisionHash,bytes32 requestId)",
  "function timeoutQuality(uint256 id,bytes32 requestId)",
  "function timeoutDelivery(uint256 id,bytes32 requestId)",
  "function timeoutKey(uint256 id,bytes32 requestId)",
  "function timeoutArbitration(uint256 id,bytes32 requestId)",
  "function abort(uint256 id,bytes32 requestId)",
  "function withdraw()",
  "function contextOf(uint256 id) view returns (uint256)",
  "function getState(uint256 id) view returns (uint8)",
  "function getListing(uint256 id) view returns ((bytes32 tid,address seller,address buyer,uint8 state,uint256 cD,uint256 cQ,uint256 cK,uint256 zkRoot,bytes32 objectDigest,bytes32 objectKeyHash,bytes32 contractHash,uint256 price,uint256 sellerBond,uint256 buyerEscrow,uint256 minPresent,uint256 maxValue,uint256 maxAge,uint64 asOfTime,uint256 nonce,uint256 buyerKey,uint256 keyEnvelope,bytes32 keyEnvelopeDigest,bytes32 evidenceHash,bytes32 evidenceURIHash,uint64 qualityDeadline,uint64 deliveryDeadline,uint64 keyDeadline,uint64 disputeDeadline,uint64 arbitrationDeadline))",
  "event ListingCreated(uint256 indexed id,bytes32 indexed tid,address indexed seller,uint256 cD,uint256 cQ,uint256 cK,uint256 zkRoot,bytes32 objectDigest,bytes32 objectKeyHash,bytes32 requestId)",
  "event EscrowLocked(uint256 indexed id,bytes32 indexed tid,address indexed buyer,uint256 amount,uint256 buyerKey,uint256 context,bytes32 requestId)",
  "event QualityVerified(uint256 indexed id,bytes32 indexed tid,bytes32 proofHash,uint256 binding,bytes32 requestId)",
  "event DeliveryVerified(uint256 indexed id,bytes32 indexed tid,bytes32 proofHash,uint256 binding,bytes32 requestId)",
  "event KeyReleased(uint256 indexed id,bytes32 indexed tid,bytes32 proofHash,uint256 keyEnvelope,bytes32 keyEnvelopeDigest,uint256 binding,bytes32 requestId)",
  "event DisputeOpened(uint256 indexed id,bytes32 indexed tid,bytes32 evidenceHash,bytes32 evidenceURIHash,uint64 arbitrationDeadline,bytes32 requestId)",
  "event DisputeResolved(uint256 indexed id,bytes32 indexed tid,bool sellerWins,bytes32 decisionHash,bytes32 requestId)",
  "event Finalized(uint256 indexed id,bytes32 indexed tid,uint8 finalState,bytes32 reason,bytes32 requestId)",
];

const STATE_NAMES = [
  "LISTED",
  "ESCROWED",
  "QUALITY_VERIFIED",
  "DELIVERED",
  "KEY_RELEASED",
  "DISPUTED",
  "CONFIRMED",
  "REFUNDED",
  "ABORTED",
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function createChain(config) {
  const deployment = await loadDeployment(config);
  const address = config.contractAddress || deployment.ddtm;
  if (!address) throw new Error("DDTM contract address is not configured");

  const provider = new JsonRpcProvider(config.rpcUrl);
  const network = await provider.getNetwork();
  const seller = new Wallet(config.sellerPrivateKey, provider);
  const buyer = new Wallet(config.buyerPrivateKey, provider);
  const arbitrator = new Wallet(config.arbitratorPrivateKey, provider);
  const iface = new Interface(ABI);

  const contracts = Object.freeze({
    seller: new Contract(address, ABI, seller),
    buyer: new Contract(address, ABI, buyer),
    arbitrator: new Contract(address, ABI, arbitrator),
    readonly: new Contract(address, ABI, provider),
  });

  async function submit(role, method, args, overrides = {}) {
    const contract = contracts[role];
    if (!contract) throw new Error(`unknown chain role ${role}`);
    let lastError;
    for (let attempt = 0; attempt < 3; attempt += 1) {
      try {
        const tx = await contract[method](...args, overrides);
        const receipt = await tx.wait(config.confirmations);
        if (!receipt || receipt.status !== 1) throw new Error(`${method} transaction reverted`);
        return { txHash: tx.hash, receipt, events: parseReceipt(receipt, iface) };
      } catch (error) {
        lastError = error;
        const hash = error.transactionHash ?? error.receipt?.hash;
        if (hash) {
          const receipt = await provider.getTransactionReceipt(hash);
          if (receipt?.status === 1) {
            return { txHash: hash, receipt, events: parseReceipt(receipt, iface) };
          }
        }
        const message = String(error.shortMessage ?? error.message ?? error);
        const deterministic = /revert|custom error|insufficient funds|nonce has already been used/i.test(message);
        if (deterministic || attempt === 2) break;
        await sleep(300 * 2 ** attempt);
      }
    }
    throw lastError;
  }

  function roleAddress(role) {
    return contracts[role]?.runner?.address ?? null;
  }

  async function getListing(id) {
    const item = await contracts.readonly.getListing(id);
    const state = Number(item.state);
    return {
      tid: item.tid,
      seller: item.seller,
      buyer: item.buyer,
      state,
      stateName: STATE_NAMES[state] ?? `UNKNOWN_${state}`,
      cD: item.cD.toString(),
      cQ: item.cQ.toString(),
      cK: item.cK.toString(),
      zkRoot: item.zkRoot.toString(),
      objectDigest: item.objectDigest,
      objectKeyHash: item.objectKeyHash,
      contractHash: item.contractHash,
      price: item.price.toString(),
      sellerBond: item.sellerBond.toString(),
      buyerEscrow: item.buyerEscrow.toString(),
      minPresent: item.minPresent.toString(),
      maxValue: item.maxValue.toString(),
      maxAge: item.maxAge.toString(),
      asOfTime: item.asOfTime.toString(),
      nonce: item.nonce.toString(),
      buyerKey: item.buyerKey.toString(),
      keyEnvelope: item.keyEnvelope.toString(),
      keyEnvelopeDigest: item.keyEnvelopeDigest,
      evidenceHash: item.evidenceHash,
      evidenceURIHash: item.evidenceURIHash,
      qualityDeadline: item.qualityDeadline.toString(),
      deliveryDeadline: item.deliveryDeadline.toString(),
      keyDeadline: item.keyDeadline.toString(),
      disputeDeadline: item.disputeDeadline.toString(),
      arbitrationDeadline: item.arbitrationDeadline.toString(),
    };
  }

  return Object.freeze({
    provider,
    address,
    chainId: network.chainId,
    interface: iface,
    stateNames: STATE_NAMES,
    roleAddress,
    submit,
    getListing,
    getState: async (id) => Number(await contracts.readonly.getState(id)),
    getContext: async (id) => (await contracts.readonly.contextOf(id)).toString(),
    getLogs: (fromBlock, toBlock) =>
      provider.getLogs({ address, fromBlock, toBlock }),
    getBlock: (number) => provider.getBlock(number),
    parseLog: (log) => iface.parseLog(log),
  });
}

async function loadDeployment(config) {
  if (config.contractAddress) return { ddtm: config.contractAddress };
  const data = await readFile(config.deploymentFile, "utf8");
  return JSON.parse(data);
}

function parseReceipt(receipt, iface) {
  const events = [];
  for (const log of receipt.logs ?? []) {
    try {
      const parsed = iface.parseLog(log);
      if (parsed) events.push({ name: parsed.name, args: parsed.args });
    } catch {
      // Logs from verifier contracts are intentionally ignored.
    }
  }
  return events;
}
