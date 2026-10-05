const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');

async function main() {
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'deployments.json'), 'utf8')
  );
  const ledgerAddress = deployments.calibrationLedger.address;
  console.log("Connecting CalibratedCouncil to CalibrationLedger at:", ledgerAddress);

  const account = createAccount();
  console.log("Using consumer deployer address:", account.address);
  const client = createClient({
    chain: chains.studionet,
    account: account,
  });

  const codePath = path.join(__dirname, '../../examples/consumer/CalibratedCouncil.py');
  const code = fs.readFileSync(codePath, 'utf8');

  console.log("Deploying CalibratedCouncil to Studionet...");
  const deployTxHash = await client.deployContract({
    code: code,
    args: [ledgerAddress],
  });
  console.log("Deploy Transaction Hash:", deployTxHash);

  const receipt = await client.waitForTransactionReceipt({
    hash: deployTxHash,
    retries: 120,
    interval: 3000,
  });
  console.log("Deploy Receipt Status:", receipt.status_name);
  console.log("Deploy Receipt Result:", receipt.result_name);
  const contractAddress = receipt.recipient;
  console.log("Deployed CalibratedCouncil Address:", contractAddress);

  if (!contractAddress) {
    throw new Error("No contract address returned");
  }

  deployments.calibratedCouncilConsumer = {
    address: contractAddress,
    deployTxHash: deployTxHash,
    deployStatus: receipt.status_name,
    consensusResult: receipt.result_name,
    executionResult: receipt.consensus_data?.leader_receipt?.[0]?.execution_result || "SUCCESS",
    sourceFile: "examples/consumer/CalibratedCouncil.py",
    explorerUrl: `https://explorer-studio.genlayer.com/address/${contractAddress}`
  };

  fs.writeFileSync(
    path.join(__dirname, 'deployments.json'),
    JSON.stringify(deployments, null, 2)
  );
  console.log("Updated deployments.json with consumer contract");
}

main().catch(err => {
  console.error("Consumer deploy error:", err);
  process.exit(1);
});
