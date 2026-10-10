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
  console.log("Registering demo cases on CalibrationLedger at:", contractAddress);

  // We create deterministic accounts for Forecaster A and Forecaster B
  // or generated accounts saved to demo_accounts.json so we can reuse them across steps
  const crypto = require('crypto');
  let accountsData = null;
  const accountsPath = path.join(__dirname, 'demo_accounts.json');
  if (fs.existsSync(accountsPath)) {
    accountsData = JSON.parse(fs.readFileSync(accountsPath, 'utf8'));
  } else {
    accountsData = {
      forecasterA_pk: '0x' + crypto.randomBytes(32).toString('hex'),
      forecasterB_pk: '0x' + crypto.randomBytes(32).toString('hex'),
      forecasterC_pk: '0x' + crypto.randomBytes(32).toString('hex'),
    };
    fs.writeFileSync(accountsPath, JSON.stringify(accountsData, null, 2));
  }

  const accA = createAccount(accountsData.forecasterA_pk);
  const accB = createAccount(accountsData.forecasterB_pk);
  const accC = createAccount(accountsData.forecasterC_pk);

  console.log("Forecaster A:", accA.address);
  console.log("Forecaster B:", accB.address);
  console.log("Forecaster C (Active/Contest):", accC.address);

  const clientA = createClient({
    chain: chains.studionet,
    account: accA,
  });

  const clientB = createClient({
    chain: chains.studionet,
    account: accB,
  });

  const clientC = createClient({
    chain: chains.studionet,
    account: accC,
  });

  // Calculate resolve_after timestamp: exactly 360 seconds (6 minutes) from current UTC time
  const now = new Date();
  const resolveAfterDate = new Date(now.getTime() + 360 * 1000);
  const resolveAfter = resolveAfterDate.toISOString().replace(/\.\d{3}Z$/, 'Z');
  console.log(`Current UTC: ${now.toISOString()}`);
  console.log(`Setting resolve_after to: ${resolveAfter} (+360s lead time)`);

  const cases = [
    {
      id: "case_a1",
      forecasterLabel: "Forecaster A",
      client: clientA,
      forecasterAddress: accA.address,
      eventText: "Did the Federal Open Market Committee decide to lower the target range for the federal funds rate by 25 basis points?",
      probBp: 9500,
      resolveAfter: resolveAfter,
      sourceUrl: "https://raw.githubusercontent.com/huzyow155/calibration-ledger-genlayer/main/fixtures/fomc_rate_cut.md",
      expectedOutcome: "YES",
      verbatimQuote: "Federal Open Market Committee decided to lower the target range for the federal funds rate by 25 basis points to 4.50 to 4.75 percent",
    },
    {
      id: "case_a2",
      forecasterLabel: "Forecaster A",
      client: clientA,
      forecasterAddress: accA.address,
      eventText: "Did engineers successfully catch the Super Heavy booster during the Starship Flight 6 test flight?",
      probBp: 9900, // THE TRAP CASE (Overconfident call on failed catch)
      resolveAfter: resolveAfter,
      sourceUrl: "https://raw.githubusercontent.com/huzyow155/calibration-ledger-genlayer/main/fixtures/spacex_flight6.md",
      expectedOutcome: "NO",
      verbatimQuote: "engineers confirmed the booster catch attempt was stood down due to safety sensor criteria",
    },
    {
      id: "case_b1",
      forecasterLabel: "Forecaster B",
      client: clientB,
      forecasterAddress: accB.address,
      eventText: "Did Project Meridian complete its Phase 2 mainnet launch on the initial schedule?",
      probBp: 1000, // Well-calibrated honest low probability call
      resolveAfter: resolveAfter,
      sourceUrl: "https://raw.githubusercontent.com/huzyow155/calibration-ledger-genlayer/main/fixtures/meridian_delays.md",
      expectedOutcome: "NO",
      verbatimQuote: "project lead announced the Phase 2 mainnet launch was postponed to next fiscal quarter to guarantee network security",
    },
    {
      id: "case_b2",
      forecasterLabel: "Forecaster B",
      client: clientB,
      forecasterAddress: accB.address,
      eventText: "Did the Governing Council of the European Central Bank decide to decrease the deposit facility rate by 25 basis points?",
      probBp: 9000, // Well-calibrated honest high probability call
      resolveAfter: resolveAfter,
      sourceUrl: "https://raw.githubusercontent.com/huzyow155/calibration-ledger-genlayer/main/fixtures/ecb_rate_decision.md",
      expectedOutcome: "YES",
      verbatimQuote: "Governing Council decided to decrease the deposit facility rate by 25 basis points to 3.25 percent",
    },
    {
      id: "case_c1",
      forecasterLabel: "Forecaster C (Active/Contest)",
      client: clientC,
      forecasterAddress: accC.address,
      eventText: "Did Candidate Davis secure the majority in the certified metropolitan election returns?",
      probBp: 8000,
      resolveAfter: resolveAfter,
      sourceUrl: "https://raw.githubusercontent.com/huzyow155/calibration-ledger-genlayer/main/fixtures/active_election.md",
      expectedOutcome: "YES",
      verbatimQuote: "Official election results confirmed Candidate Davis secured the majority with 52.4 percent of the vote",
    },
  ];

  const registeredCases = [];

  for (const c of cases) {
    console.log(`\nRegistering ${c.id} (${c.forecasterLabel})...`);
    console.log(`Event: ${c.eventText}`);
    console.log(`Prob: ${c.probBp} bp (${c.probBp / 100}%)`);
    console.log(`Source: ${c.sourceUrl}`);

    const start = Date.now();
    const txHash = await c.client.writeContract({
      address: contractAddress,
      functionName: 'register_prediction',
      args: [c.eventText, c.probBp, c.resolveAfter, c.sourceUrl],
    });
    console.log(`Register Tx Hash: ${txHash}`);

    const receipt = await c.client.waitForTransactionReceipt({
      hash: txHash,
      retries: 120,
      interval: 3000,
    });
    const elapsed = (Date.now() - start) / 1000;
    console.log(`Receipt Status: ${receipt.status_name} (${elapsed.toFixed(1)}s)`);

    // Read predictions for this forecaster to get the prediction ID
    const listRaw = await c.client.readContract({
      address: contractAddress,
      functionName: 'list_predictions_by_forecaster',
      args: [c.forecasterAddress, 10],
    });
    const pids = JSON.parse(listRaw);
    const pid = pids[pids.length - 1];
    console.log(`Assigned Prediction ID: ${pid}`);

    registeredCases.push({
      ...c,
      predictionId: pid,
      registerTxHash: txHash,
      registerLatencySec: elapsed,
    });
  }

  const output = {
    contractAddress: contractAddress,
    resolveAfter: resolveAfter,
    registeredAt: new Date().toISOString(),
    cases: registeredCases,
  };

  fs.writeFileSync(
    path.join(__dirname, 'demo_registered.json'),
    JSON.stringify(output, null, 2)
  );
  console.log("\nAll 5 demo cases registered successfully on-chain! Saved to demo_registered.json");
}

main().catch(err => {
  console.error("Registration failed:", err);
  process.exit(1);
});
