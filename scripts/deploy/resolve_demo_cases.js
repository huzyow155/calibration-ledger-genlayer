const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');

async function main() {
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'deployments.json'), 'utf8')
  );
  const contractAddress = deployments.calibrationLedger.address;
  console.log("Resolving demo cases on CalibrationLedger at:", contractAddress);

  const demoAccounts = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'demo_accounts.json'), 'utf8')
  );

  const accA = createAccount(demoAccounts.forecasterA_pk);
  const accB = createAccount(demoAccounts.forecasterB_pk);
  const accC = createAccount(demoAccounts.forecasterC_pk);

  // Anyone can call resolve_event, we use accA
  const client = createClient({
    chain: chains.studionet,
    account: accA,
  });

  const pids = {
    case_a1: "53f6d83d16df",
    case_a2: "86ee08dcfee2",
    case_b1: "5a7753c28378",
    case_b2: "37b05c2ee6b2",
    case_c1: "3393c1ce5063",
  };

  // Check if resolve_after is reached
  const targetTime = new Date("2026-10-10T03:17:26Z").getTime();
  const nowMs = Date.now();
  if (nowMs < targetTime) {
    const waitSec = Math.ceil((targetTime - nowMs) / 1000) + 5;
    console.log(`Waiting ${waitSec}s for resolve_after deadline to pass...`);
    await new Promise((r) => setTimeout(r, waitSec * 1000));
  }
  console.log("Deadline reached! Executing resolve_event transactions...");

  const resolutionResults = {};

  for (const [caseKey, pid] of Object.entries(pids)) {
    console.log(`\nResolving ${caseKey} (PID: ${pid})...`);
    const start = Date.now();
    const txHash = await client.writeContract({
      address: contractAddress,
      functionName: 'resolve_event',
      args: [pid],
    });
    console.log(`Resolve Tx Hash: ${txHash}`);

    const receipt = await client.waitForTransactionReceipt({
      hash: txHash,
      retries: 120,
      interval: 3000,
    });
    const elapsed = (Date.now() - start) / 1000;
    console.log(`Resolve Receipt Status: ${receipt.status_name} (${elapsed.toFixed(1)}s)`);

    const recRaw = await client.readContract({
      address: contractAddress,
      functionName: 'get_prediction',
      args: [pid],
    });
    const record = JSON.parse(recRaw);
    console.log(`Record status: ${record.status}, outcome: ${record.outcome}, quote: ${record.resolution_quote}`);

    resolutionResults[caseKey] = {
      predictionId: pid,
      txHash: txHash,
      latencySec: elapsed,
      status: record.status,
      outcome: record.outcome,
      resolved_at: record.resolved_at,
      source_hash: record.source_hash,
      source_url: record.source_url,
    };
  }

  // Contest case_c1 during contest window
  console.log(`\nExecuting contest_resolution for case_c1 (${pids.case_c1})...`);
  const clientC = createClient({ chain: chains.studionet, account: accC });
  const contestStart = Date.now();
  const contestTxHash = await clientC.writeContract({
    address: contractAddress,
    functionName: 'contest_resolution',
    args: [pids.case_c1, ""],
  });
  console.log(`Contest Tx Hash: ${contestTxHash}`);
  const contestReceipt = await clientC.waitForTransactionReceipt({
    hash: contestTxHash,
    retries: 120,
    interval: 3000,
  });
  console.log(`Contest Status: ${contestReceipt.status_name}`);
  const recC = JSON.parse(await client.readContract({
    address: contractAddress,
    functionName: 'get_prediction',
    args: [pids.case_c1],
  }));
  console.log(`Case C1 contested flag: ${recC.contested}, status: ${recC.status}`);

  fs.writeFileSync(
    path.join(__dirname, 'demo_resolutions.json'),
    JSON.stringify(resolutionResults, null, 2)
  );
  console.log("Saved resolution results to demo_resolutions.json");
}

main().catch(err => {
  console.error("Resolution execution failed:", err);
  process.exit(1);
});
