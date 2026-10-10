const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const { createClient, chains, createAccount } = require('genlayer-js');
const fs = require('fs');
const path = require('path');

async function main() {
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'deployments.json'), 'utf8')
  );
  const ledgerAddr = deployments.calibrationLedger.address;
  const councilAddr = deployments.calibratedCouncilConsumer.address;

  const accounts = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'demo_accounts.json'), 'utf8')
  );

  const accA = createAccount(accounts.forecasterA_pk);
  const accB = createAccount(accounts.forecasterB_pk);
  const accC = createAccount(accounts.forecasterC_pk);

  const clientA = createClient({ chain: chains.studionet, account: accA });
  const clientB = createClient({ chain: chains.studionet, account: accB });
  const clientC = createClient({ chain: chains.studionet, account: accC });

  const cases = {
    case_a1: { pid: "53f6d83d16df" },
    case_a2: { pid: "86ee08dcfee2" },
    case_b1: { pid: "5a7753c28378" },
    case_b2: { pid: "37b05c2ee6b2" },
    case_c1: { pid: "3393c1ce5063" },
  };

  console.log("=== FINISHING REAL EVIDENCE RESOLUTIONS & SETTLEMENTS ===");
  console.log("Ledger:", ledgerAddr);
  console.log("Council:", councilAddr);

  // Check state of case_a1 first
  const recA1 = JSON.parse(await clientA.readContract({
    address: ledgerAddr,
    functionName: "get_prediction",
    args: [cases.case_a1.pid],
  }));
  console.log(`case_a1 status: ${recA1.status}, outcome: ${recA1.outcome}, resolved_at: ${recA1.resolved_at}`);
  cases.case_a1.status = recA1.status;
  cases.case_a1.outcome = recA1.outcome;
  cases.case_a1.resolved_at = recA1.resolved_at;
  cases.case_a1.source_hash = recA1.source_hash;
  cases.case_a1.source_url = recA1.source_url;

  // Resolve case_a2, case_b1, case_b2, case_c1
  const remaining = ["case_a2", "case_b1", "case_b2", "case_c1"];
  for (const k of remaining) {
    const pid = cases[k].pid;
    console.log(`\nResolving ${k} (${pid})...`);
    const t0 = Date.now();
    const tx = await clientA.writeContract({
      address: ledgerAddr,
      functionName: "resolve_event",
      args: [pid],
    });
    console.log(`Tx: ${tx}`);
    const receipt = await clientA.waitForTransactionReceipt({ hash: tx, retries: 120, interval: 3000 });
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`Receipt: ${receipt.status_name} (${elapsed}s)`);

    const rec = JSON.parse(await clientA.readContract({
      address: ledgerAddr,
      functionName: "get_prediction",
      args: [pid],
    }));
    console.log(`Record status: ${rec.status}, outcome: ${rec.outcome}, resolved_at: ${rec.resolved_at}`);
    cases[k].status = rec.status;
    cases[k].outcome = rec.outcome;
    cases[k].resolved_at = rec.resolved_at;
    cases[k].source_hash = rec.source_hash;
    cases[k].source_url = rec.source_url;
    cases[k].resolveTx = tx;
  }

  // Contest case_c1
  console.log("\n--- CONTESTING CASE_C1 ---");
  const pidC = cases.case_c1.pid;
  const contestAltUrl = "https://en.wikipedia.org/wiki/Falcon_9";
  console.log(`Contesting case_c1 (${pidC}) with alt source: ${contestAltUrl}...`);
  const cTx = await clientC.writeContract({
    address: ledgerAddr,
    functionName: "contest_resolution",
    args: [pidC, contestAltUrl],
  });
  console.log(`Contest Tx: ${cTx}`);
  const cRc = await clientC.waitForTransactionReceipt({ hash: cTx, retries: 120, interval: 3000 });
  console.log(`Contest Status: ${cRc.status_name}`);

  const recC = JSON.parse(await clientA.readContract({
    address: ledgerAddr,
    functionName: "get_prediction",
    args: [pidC],
  }));
  console.log(`Case C1 Contested Flag: ${recC.contested}, Status: ${recC.status}`);
  cases.case_c1.contested = recC.contested;
  cases.case_c1.contested_at = recC.contested_at;

  // Find the latest resolved_at timestamp among cases a1, a2, b1, b2
  let latestResolvedMs = 0;
  for (const k of ["case_a1", "case_a2", "case_b1", "case_b2"]) {
    const rTime = new Date(cases[k].resolved_at.slice(0, 19) + "Z").getTime();
    if (rTime > latestResolvedMs) latestResolvedMs = rTime;
  }

  const contestWaitDeadline = latestResolvedMs + 305 * 1000;
  console.log(`\nWaiting until contest window expires at ${new Date(contestWaitDeadline).toISOString()}...`);

  while (Date.now() < contestWaitDeadline) {
    const remainSec = Math.ceil((contestWaitDeadline - Date.now()) / 1000);
    console.log(`Contest window active: ${remainSec}s remaining...`);
    await new Promise((r) => setTimeout(r, Math.min(remainSec, 20) * 1000));
  }
  console.log("Contest window expired! Proceeding to settlement.");

  // Settle cases a1, a2, b1, b2
  console.log("\n--- SETTLING CASES A1, A2, B1, B2 ---");
  const settledCases = ["case_a1", "case_a2", "case_b1", "case_b2"];
  const settlements = {};

  for (const k of settledCases) {
    const pid = cases[k].pid;
    console.log(`\nSettling ${k} (${pid})...`);
    const t0 = Date.now();
    const tx = await clientA.writeContract({
      address: ledgerAddr,
      functionName: "settle",
      args: [pid],
    });
    console.log(`Settle Tx: ${tx}`);
    const receipt = await clientA.waitForTransactionReceipt({ hash: tx, retries: 120, interval: 3000 });
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`Receipt: ${receipt.status_name} (${elapsed}s)`);

    const rec = JSON.parse(await clientA.readContract({
      address: ledgerAddr,
      functionName: "get_prediction",
      args: [pid],
    }));
    console.log(`Record status: ${rec.status}, settled_at: ${rec.settled_at}`);
    settlements[k] = {
      predictionId: pid,
      settleTx: tx,
      status: rec.status,
      settled_at: rec.settled_at,
    };
  }

  // Reports
  console.log("\n--- FETCHING CALIBRATION REPORTS ---");
  const repA = JSON.parse(await clientA.readContract({
    address: ledgerAddr,
    functionName: "get_calibration_report",
    args: [accA.address],
  }));
  console.log("Forecaster A Report:", JSON.stringify(repA, null, 2));

  const repB = JSON.parse(await clientB.readContract({
    address: ledgerAddr,
    functionName: "get_calibration_report",
    args: [accB.address],
  }));
  console.log("Forecaster B Report:", JSON.stringify(repB, null, 2));

  // Council Endorsement
  console.log("\n--- CALIBRATED COUNCIL ENDORSEMENT ---");
  const endorseTx = await clientB.writeContract({
    address: councilAddr,
    functionName: "endorse_policy",
    args: ["We endorse independent verification of astrophysical telemetry records."],
  });
  console.log(`Council Endorse Tx: ${endorseTx}`);
  const endorseRc = await clientB.waitForTransactionReceipt({ hash: endorseTx, retries: 120, interval: 3000 });
  console.log(`Council Endorse Status: ${endorseRc.status_name}`);

  const output = {
    cases,
    settlements,
    forecasterA: {
      address: accA.address,
      report: repA,
    },
    forecasterB: {
      address: accB.address,
      report: repB,
    },
    council: {
      address: councilAddr,
      endorseTx,
      status: endorseRc.status_name,
    },
  };

  fs.writeFileSync(
    path.join(__dirname, 'real_demo_settled_reports.json'),
    JSON.stringify(output, null, 2)
  );
  console.log("\nSaved complete real evidence pipeline results to real_demo_settled_reports.json");
}

main().catch(err => {
  console.error("Pipeline finished with error:", err);
  process.exit(1);
});
