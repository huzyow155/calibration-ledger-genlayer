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
  console.log("Running on-chain evidence transactions against deployed contract:", contractAddress);

  const accountA = createAccount();
  const accountB = createAccount();
  console.log("Forecaster A Address:", accountA.address);
  console.log("Forecaster B Address:", accountB.address);

  const clientA = createClient({ chain: chains.studionet, account: accountA });
  const clientB = createClient({ chain: chains.studionet, account: accountB });

  const testCases = [
    {
      caseId: 1,
      title: "Correct High-Confidence Call",
      forecasterLabel: "Forecaster A",
      account: accountA,
      client: clientA,
      eventText: "Did Apple announce the iPhone 16 series with Apple Intelligence in September 2024?",
      probBp: 9000,
      deadlineHint: "2024-09-30",
      evidenceText: "Apple officially unveiled the iPhone 16 family powered by Apple Intelligence during its 'It's Glowtime' keynote event on September 9 2024 in Cupertino.",
      expectedOutcome: "YES",
    },
    {
      caseId: 2,
      title: "Incorrect High-Confidence Call (The Trap Case)",
      forecasterLabel: "Forecaster A",
      account: accountA,
      client: clientA,
      eventText: "Did SpaceX launch the lunar Starship uncrewed Moon landing mission before October 2026?",
      probBp: 9900,
      deadlineHint: "2026-10-01",
      evidenceText: "As of October 2026, NASA and SpaceX confirmed the uncrewed Starship lunar landing demonstration remains in development and has not yet launched to the lunar surface.",
      expectedOutcome: "NO",
    },
    {
      caseId: 3,
      title: "Ambiguous Resolution (Unclear / Wash Evidence)",
      forecasterLabel: "Forecaster A",
      account: accountA,
      client: clientA,
      eventText: "Did global atmospheric carbon dioxide average fall below 400 ppm in 2026?",
      probBp: 1500,
      deadlineHint: "2026-12-31",
      evidenceText: "Local weather stations in rural Vermont recorded calm winds, mild autumn temperatures, and fluctuating barometric pressure readings throughout late September.",
      expectedOutcome: "AMBIGUOUS",
    },
    {
      caseId: 4,
      title: "Correct Low-Confidence Call",
      forecasterLabel: "Forecaster B",
      account: accountB,
      client: clientB,
      eventText: "Will Bitcoin trade below 10000 USD during the fourth quarter of 2026?",
      probBp: 1000,
      deadlineHint: "2026-12-31",
      evidenceText: "Market data from major exchanges confirmed Bitcoin was trading securely in the 60000 to 75000 USD channel throughout Q4 2026, never approaching 10000 USD.",
      expectedOutcome: "NO",
    },
    {
      caseId: 5,
      title: "Well-Calibrated Moderate Confidence Call",
      forecasterLabel: "Forecaster B",
      account: accountB,
      client: clientB,
      eventText: "Did the Paris 2024 Summer Olympic Games conclude in August 2024?",
      probBp: 8500,
      deadlineHint: "2024-08-31",
      evidenceText: "The International Olympic Committee and Paris organizers held the official closing ceremony for the 2024 Olympic Games on August 11 2024 at Stade de France.",
      expectedOutcome: "YES",
    },
  ];

  const results = [];

  for (const tc of testCases) {
    console.log(`\n==================================================`);
    console.log(`Executing Case ${tc.caseId}: ${tc.title}`);
    console.log(`Forecaster: ${tc.forecasterLabel} (${tc.account.address})`);
    console.log(`Prob: ${tc.probBp} bp (${(tc.probBp / 100).toFixed(2)}%)`);
    console.log(`Event: ${tc.eventText}`);

    // Step 1: Register prediction
    const regStart = Date.now();
    const regTxHash = await tc.client.writeContract({
      address: contractAddress,
      functionName: 'register_prediction',
      args: [tc.eventText, tc.probBp, tc.deadlineHint],
    });
    console.log(`register_prediction Tx Hash: ${regTxHash}`);

    const regReceipt = await tc.client.waitForTransactionReceipt({
      hash: regTxHash,
      retries: 120,
      interval: 3000,
    });
    const regElapsed = (Date.now() - regStart) / 1000;
    const regExecResult = regReceipt.consensus_data?.leader_receipt?.[0]?.execution_result || "UNKNOWN";
    console.log(`Register status: ${regReceipt.status_name}, result: ${regReceipt.result_name}, execution: ${regExecResult} (${regElapsed.toFixed(2)}s)`);

    const leaderReturn = regReceipt.consensus_data?.leader_receipt?.[0]?.result?.payload?.readable;
    let predictionId = "";
    if (leaderReturn) {
      try {
        predictionId = JSON.parse(leaderReturn);
      } catch {
        predictionId = leaderReturn.replace(/['"]/g, '');
      }
    }
    console.log(`Assigned Prediction ID: ${predictionId}`);

    // Read state before resolution
    const predBefore = await tc.client.readContract({
      address: contractAddress,
      functionName: 'get_prediction',
      args: [predictionId],
    });

    // Step 2: Resolve event
    console.log(`Submitting resolve_event consensus tx...`);
    const resStart = Date.now();
    const resTxHash = await tc.client.writeContract({
      address: contractAddress,
      functionName: 'resolve_event',
      args: [predictionId, tc.evidenceText],
    });
    console.log(`resolve_event Tx Hash: ${resTxHash}`);

    const resReceipt = await tc.client.waitForTransactionReceipt({
      hash: resTxHash,
      retries: 120,
      interval: 3000,
    });
    const resElapsed = (Date.now() - resStart) / 1000;
    const resExecResult = resReceipt.consensus_data?.leader_receipt?.[0]?.execution_result || "UNKNOWN";
    console.log(`Resolve status: ${resReceipt.status_name}, result: ${resReceipt.result_name}, execution: ${resExecResult} (${resElapsed.toFixed(2)}s)`);

    // Read state after resolution
    const predAfter = await tc.client.readContract({
      address: contractAddress,
      functionName: 'get_prediction',
      args: [predictionId],
    });
    const parsedAfter = JSON.parse(predAfter);
    console.log(`Resolved Outcome: ${parsedAfter.outcome} (Expected: ${tc.expectedOutcome})`);
    console.log(`Resolution Quote: ${parsedAfter.resolution_quote}`);

    results.push({
      caseId: tc.caseId,
      title: tc.title,
      forecaster: tc.account.address,
      forecasterLabel: tc.forecasterLabel,
      eventText: tc.eventText,
      probBp: tc.probBp,
      deadlineHint: tc.deadlineHint,
      evidenceText: tc.evidenceText,
      expectedOutcome: tc.expectedOutcome,
      predictionId: predictionId,
      registerTxHash: regTxHash,
      registerReceiptStatus: regReceipt.status_name,
      registerConsensusResult: regReceipt.result_name,
      registerExecutionResult: regExecResult,
      registerLatencySec: regElapsed,
      resolveTxHash: resTxHash,
      resolveReceiptStatus: resReceipt.status_name,
      resolveConsensusResult: resReceipt.result_name,
      resolveExecutionResult: resExecResult,
      resolveLatencySec: resElapsed,
      recordBefore: JSON.parse(predBefore),
      recordAfter: parsedAfter,
    });
  }

  // Final Reports read-back
  console.log("\n==================================================");
  console.log("Fetching Final On-Chain Calibration Reports...");

  const reportA = await clientA.readContract({
    address: contractAddress,
    functionName: 'get_calibration_report',
    args: [accountA.address],
  });
  console.log("\nForecaster A Calibration Report:", reportA);

  const listA = await clientA.readContract({
    address: contractAddress,
    functionName: 'list_predictions_by_forecaster',
    args: [accountA.address, 10],
  });
  console.log("Forecaster A Discovery List:", listA);

  const reportB = await clientB.readContract({
    address: contractAddress,
    functionName: 'get_calibration_report',
    args: [accountB.address],
  });
  console.log("\nForecaster B Calibration Report:", reportB);

  const listB = await clientB.readContract({
    address: contractAddress,
    functionName: 'list_predictions_by_forecaster',
    args: [accountB.address, 10],
  });
  console.log("Forecaster B Discovery List:", listB);

  const liveEvidenceData = {
    contractAddress: contractAddress,
    forecasterA: accountA.address,
    forecasterB: accountB.address,
    cases: results,
    forecasterAReport: JSON.parse(reportA),
    forecasterAList: JSON.parse(listA),
    forecasterBReport: JSON.parse(reportB),
    forecasterBList: JSON.parse(listB),
  };

  fs.writeFileSync(
    path.join(__dirname, 'live_evidence.json'),
    JSON.stringify(liveEvidenceData, null, 2)
  );
  console.log("\nSuccessfully saved live evidence to scripts/deploy/live_evidence.json");
}

main().catch(err => {
  console.error("Execution failed:", err);
  process.exit(1);
});
