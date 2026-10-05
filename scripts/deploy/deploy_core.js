const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');

async function main() {
  const account = createAccount();
  console.log("Using core deployer address:", account.address);
  const client = createClient({
    chain: chains.studionet,
    account: account,
  });

  const codePath = path.join(__dirname, '../../contracts/CalibrationLedgerCore.py');
  const code = fs.readFileSync(codePath, 'utf8');

  console.log("Deploying CalibrationLedgerCore to Studionet...");
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
  console.log("Deployed Core Contract Address:", contractAddress);

  if (!contractAddress) {
    throw new Error("No contract address returned from deployment receipt");
  }

  // Round 1: Register prediction
  console.log("\n--- Executing register_prediction write tx ---");
  const eventText = "Will NASA Artemis II launch astronauts into lunar flyby orbit in 2026?";
  const probBp = 7500;
  const deadlineHint = "2026-12-31";

  const regStartTime = Date.now();
  const regTxHash = await client.writeContract({
    address: contractAddress,
    functionName: 'register_prediction',
    args: [eventText, probBp, deadlineHint],
  });
  console.log("register_prediction Tx Hash:", regTxHash);

  const regReceipt = await client.waitForTransactionReceipt({
    hash: regTxHash,
    retries: 120,
    interval: 3000,
  });
  const regLatency = (Date.now() - regStartTime) / 1000;
  console.log(`register_prediction took ${regLatency.toFixed(2)}s`);
  console.log("register_prediction Status:", regReceipt.status_name);
  console.log("register_prediction Result:", regReceipt.result_name);
  console.log("register_prediction Execution Result:", regReceipt.consensus_data?.leader_receipt?.[0]?.execution_result);

  // Read leader return payload or derive prediction_id
  const leaderReturn = regReceipt.consensus_data?.leader_receipt?.[0]?.result?.payload?.readable;
  console.log("Leader Return Value:", leaderReturn);

  let predictionId = "";
  if (leaderReturn) {
    try {
      predictionId = JSON.parse(leaderReturn);
    } catch {
      predictionId = leaderReturn.replace(/['"]/g, '');
    }
  }

  // If needed, compute entropy
  if (!predictionId) {
    const crypto = require('crypto');
    const entropy = `${account.address}|${eventText}|${probBp}|${deadlineHint}|1`;
    predictionId = crypto.createHash('sha256').update(entropy, 'utf8').digest('hex').substring(0, 12);
  }
  console.log("Derived / Returned Prediction ID:", predictionId);

  // Read back prediction
  const predBefore = await client.readContract({
    address: contractAddress,
    functionName: 'get_prediction',
    args: [predictionId],
  });
  console.log("get_prediction before resolution:", predBefore);

  // Round 2: Resolve event
  console.log("\n--- Executing resolve_event write tx ---");
  const evidenceText = "NASA officially confirmed on October 5 2026 that Artemis II has successfully completed its countdown and launched astronauts into lunar flyby orbit.";
  
  const resStartTime = Date.now();
  const resTxHash = await client.writeContract({
    address: contractAddress,
    functionName: 'resolve_event',
    args: [predictionId, evidenceText],
  });
  console.log("resolve_event Tx Hash:", resTxHash);

  const resReceipt = await client.waitForTransactionReceipt({
    hash: resTxHash,
    retries: 120,
    interval: 3000,
  });
  const resLatency = (Date.now() - resStartTime) / 1000;
  console.log(`resolve_event took ${resLatency.toFixed(2)}s`);
  console.log("resolve_event Status:", resReceipt.status_name);
  console.log("resolve_event Result:", resReceipt.result_name);
  console.log("resolve_event Execution Result:", resReceipt.consensus_data?.leader_receipt?.[0]?.execution_result);

  // Read back resolved prediction
  const predAfter = await client.readContract({
    address: contractAddress,
    functionName: 'get_prediction',
    args: [predictionId],
  });
  console.log("get_prediction after resolution:", predAfter);

  const coreOutput = {
    deployer: account.address,
    contractAddress: contractAddress,
    deployTxHash: deployTxHash,
    deployReceipt: receipt,
    registerTxHash: regTxHash,
    registerReceipt: regReceipt,
    registerLatencySec: regLatency,
    predictionId: predictionId,
    predictionBefore: predBefore ? JSON.parse(predBefore) : null,
    resolveTxHash: resTxHash,
    resolveReceipt: resReceipt,
    resolveLatencySec: resLatency,
    predictionAfter: predAfter ? JSON.parse(predAfter) : null,
  };

  fs.writeFileSync(
    path.join(__dirname, 'core_output.json'),
    JSON.stringify(coreOutput, null, 2)
  );
  console.log("Saved core output to core_output.json");
}

main().catch(err => {
  console.error("Core deployment error:", err);
  process.exit(1);
});
