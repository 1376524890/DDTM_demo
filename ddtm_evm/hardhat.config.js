require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: {
    version: "0.8.20",
    settings: {
      viaIR: true,
      // V1 favors deployable bytecode size over repeated-call gas optimization.
      optimizer: { enabled: true, runs: 1 },
    },
  },
  networks: {
    hardhat: {
      chainId: 31337,
      blockGasLimit: 60_000_000,
    },
    localhost: {
      url: process.env.RPC_URL ?? "http://127.0.0.1:8545",
      chainId: 31337,
    },
  },
  mocha: {
    timeout: 180_000,
  },
};
