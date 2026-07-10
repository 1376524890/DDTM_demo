const fs = require("node:fs");
const path = require("node:path");
const hre = require("hardhat");

async function main() {
  const [deployer, seller, buyer, arbitrator] = await hre.ethers.getSigners();

  const PiQ = await hre.ethers.getContractFactory("PiQVerifier");
  const piQ = await PiQ.deploy();
  await piQ.waitForDeployment();

  const PiKey = await hre.ethers.getContractFactory("PiKeyVerifier");
  const piKey = await PiKey.deploy();
  await piKey.waitForDeployment();

  const PiDeliver = await hre.ethers.getContractFactory("PiDeliverVerifier");
  const piDeliver = await PiDeliver.deploy();
  await piDeliver.waitForDeployment();

  const windowSeconds = Number(process.env.DDTM_WINDOW_SECONDS ?? 300);
  const DDTM = await hre.ethers.getContractFactory("DDTMProtocol");
  const ddtm = await DDTM.deploy(
    await piQ.getAddress(),
    await piKey.getAddress(),
    await piDeliver.getAddress(),
    arbitrator.address,
    windowSeconds,
    windowSeconds,
    windowSeconds,
    windowSeconds,
    windowSeconds
  );
  const receipt = await ddtm.deploymentTransaction().wait();

  const network = await hre.ethers.provider.getNetwork();
  const output = {
    version: "ddtm-v1",
    chainId: network.chainId.toString(),
    deploymentBlock: receipt.blockNumber,
    ddtm: await ddtm.getAddress(),
    verifiers: {
      quality: await piQ.getAddress(),
      key: await piKey.getAddress(),
      delivery: await piDeliver.getAddress(),
    },
    actors: {
      deployer: deployer.address,
      seller: seller.address,
      buyer: buyer.address,
      arbitrator: arbitrator.address,
    },
  };

  const outputFile = process.env.DEPLOYMENT_OUTPUT ?? path.join(__dirname, "..", "deployments", "v1.json");
  fs.mkdirSync(path.dirname(outputFile), { recursive: true });
  fs.writeFileSync(outputFile, `${JSON.stringify(output, null, 2)}\n`);
  console.log(JSON.stringify(output, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
