const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { execSync } = require('child_process');

async function main() {
  const account = createAccount();
  console.log("Using CalibrationLedger deployer address:", account.address);
  const client = createClient({
    chain: chains.studionet,
    account: account,
  });

  const codePath = path.join(__dirname, '../../contracts/CalibrationLedger.py');
  const code = fs.readFileSync(codePath, 'utf8');
  const sourceSha256 = crypto.createHash('sha256').update(code, 'utf8').digest('hex');
  console.log("Local CalibrationLedger.py SHA-256:", sourceSha256);

  console.log("Deploying CalibrationLedger to Studionet...");
  const deployTxHash = await client.deployContract({
    code: code,
    args: [],
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
  console.log("Deployed CalibrationLedger Contract Address:", contractAddress);

  if (!contractAddress) {
    throw new Error("No contract address returned from deployment receipt");
  }

  // Get current git commit hash
  let commitHash = "";
  try {
    commitHash = execSync("git rev-parse HEAD", { encoding: "utf8" }).trim();
  } catch {
    commitHash = "unknown";
  }

  const deployments = {
    network: "GenLayer Studionet",
    chainId: 61999,
    rpc: "https://studio.genlayer.com/api",
    explorerBase: "https://explorer-studio.genlayer.com",
    calibrationLedger: {
      address: contractAddress,
      deployTxHash: deployTxHash,
      deployStatus: receipt.status_name,
      consensusResult: receipt.result_name,
      executionResult: receipt.consensus_data?.leader_receipt?.[0]?.execution_result || "SUCCESS",
      commitHash: commitHash,
      sourceFile: "contracts/CalibrationLedger.py",
      sourceSha256: sourceSha256,
      explorerUrl: `https://explorer-studio.genlayer.com/address/${contractAddress}`
    }
  };

  fs.writeFileSync(
    path.join(__dirname, 'deployments.json'),
    JSON.stringify(deployments, null, 2)
  );
  console.log("Saved deployments to deployments.json");

  // Read initial discovery views
  const initialList = await client.readContract({
    address: contractAddress,
    functionName: 'list_predictions_by_forecaster',
    args: [account.address, 10],
  });
  console.log("Initial list_predictions_by_forecaster:", initialList);

  const initialReport = await client.readContract({
    address: contractAddress,
    functionName: 'get_calibration_report',
    args: [account.address],
  });
  console.log("Initial get_calibration_report:", initialReport);
}

main().catch(err => {
  console.error("Ledger deployment error:", err);
  process.exit(1);
});
