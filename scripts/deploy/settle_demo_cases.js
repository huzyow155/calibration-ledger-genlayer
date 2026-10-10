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
  const clientA = createClient({ chain: chains.studionet, account: accA });
  const clientB = createClient({ chain: chains.studionet, account: accB });

  console.log("=== Settling Demo Predictions ===");
  console.log("CalibrationLedger:", ledgerAddr);
  console.log("CalibratedCouncil:", councilAddr);

  // Target timestamp: 03:26:00 UTC
  const targetTime = new Date("2026-10-10T03:26:00Z").getTime();
  const nowMs = Date.now();
  if (nowMs < targetTime) {
    const waitSec = Math.ceil((targetTime - nowMs) / 1000) + 2;
    console.log(`Waiting ${waitSec}s for all 300s contest windows to pass...`);
    await new Promise((r) => setTimeout(r, waitSec * 1000));
  }
  console.log("Contest windows expired. Executing settle()...");

  const toSettle = [
    { key: "case_a1", pid: "c8467666af9c" },
    { key: "case_a2", pid: "e9a52293efcd" },
    { key: "case_b1", pid: "70c79efd581b" },
    { key: "case_b2", pid: "df37af300e33" },
  ];

  const settleReceipts = {};

  for (const item of toSettle) {
    console.log(`\nSettling ${item.key} (${item.pid})...`);
    const t0 = Date.now();
    const tx = await clientA.writeContract({
      address: ledgerAddr,
      functionName: "settle",
      args: [item.pid],
    });
    console.log(`Settle Tx: ${tx}`);
    const receipt = await clientA.waitForTransactionReceipt({
      hash: tx,
      retries: 120,
      interval: 3000,
    });
    const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
    console.log(`Settle Receipt: ${receipt.status_name} (${elapsed}s)`);

    const rec = JSON.parse(
      await clientA.readContract({
        address: ledgerAddr,
        functionName: "get_prediction",
        args: [item.pid],
      })
    );
    console.log(`Record status: ${rec.status}, settled_at: ${rec.settled_at}`);
    settleReceipts[item.key] = {
      predictionId: item.pid,
      txHash: tx,
      latencySec: elapsed,
      status: rec.status,
      settled_at: rec.settled_at,
    };
  }

  // Fetch final calibration reports
  console.log("\n=== Fetching Forecaster Reports ===");
  const repA_raw = await clientA.readContract({
    address: ledgerAddr,
    functionName: "get_calibration_report",
    args: [accA.address],
  });
  const repA = JSON.parse(repA_raw);
  console.log("Forecaster A Report:", JSON.stringify(repA, null, 2));

  const repB_raw = await clientB.readContract({
    address: ledgerAddr,
    functionName: "get_calibration_report",
    args: [accB.address],
  });
  const repB = JSON.parse(repB_raw);
  console.log("Forecaster B Report:", JSON.stringify(repB, null, 2));

  // Check Council eligibility for Forecaster B
  console.log("\n=== Checking CalibratedCouncil Eligibility ===");
  try {
    const eligB = await clientB.readContract({
      address: councilAddr,
      functionName: "get_forecaster_eligibility",
      args: [accB.address],
    });
    console.log("Forecaster B Council Eligibility:", eligB);
  } catch (err) {
    console.log("Council eligibility check error:", err.message);
  }

  const finalReport = {
    settled: settleReceipts,
    forecasterA: {
      address: accA.address,
      report: repA,
    },
    forecasterB: {
      address: accB.address,
      report: repB,
    },
  };

  fs.writeFileSync(
    path.join(__dirname, 'demo_settled_reports.json'),
    JSON.stringify(finalReport, null, 2)
  );
  console.log("\nSaved final settled reports to demo_settled_reports.json");
}

main().catch(err => {
  console.error("Settlement script failed:", err);
  process.exit(1);
});
