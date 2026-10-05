const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');

async function main() {
  const account = createAccount();
  console.log("Using deployer address:", account.address);
  const client = createClient({
    chain: chains.studionet,
    account: account,
  });

  const codePath = path.join(__dirname, '../../contracts/Probe.py');
  const code = fs.readFileSync(codePath, 'utf8');

  console.log("Deploying Probe contract to Studionet...");
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
  console.log("Deployed Probe Contract Address:", contractAddress);

  if (!contractAddress) {
    throw new Error("No contract address returned from deployment receipt");
  }

  const initResults = await client.readContract({
    address: contractAddress,
    functionName: 'get_results',
    args: [],
  });
  console.log("Initial Probe Results:", initResults);

  console.log("Executing probe_consensus write transaction...");
  const startTime = Date.now();
  const txHash = await client.writeContract({
    address: contractAddress,
    functionName: 'probe_consensus',
    args: [],
  });
  console.log("probe_consensus Tx Hash:", txHash);

  const writeReceipt = await client.waitForTransactionReceipt({
    hash: txHash,
    retries: 120,
    interval: 3000,
  });
  const elapsed = (Date.now() - startTime) / 1000;
  console.log(`probe_consensus took ${elapsed.toFixed(2)}s`);
  console.log("Write Receipt Status:", writeReceipt.status_name);
  console.log("Write Receipt Result:", writeReceipt.result_name);

  const finalResults = await client.readContract({
    address: contractAddress,
    functionName: 'get_results',
    args: [],
  });
  console.log("Final Probe Results:", finalResults);

  const probeData = {
    deployer: account.address,
    contractAddress: contractAddress,
    deployTxHash: deployTxHash,
    deployReceipt: receipt,
    consensusTxHash: txHash,
    consensusReceipt: writeReceipt,
    consensusLatencySec: elapsed,
    initialProbeResults: JSON.parse(initResults),
    finalProbeResults: JSON.parse(finalResults),
  };

  fs.writeFileSync(
    path.join(__dirname, 'probe_output.json'),
    JSON.stringify(probeData, null, 2)
  );
  console.log("Saved probe results to probe_output.json");
}

main().catch(err => {
  console.error("Probe deployment error:", err);
  process.exit(1);
});
