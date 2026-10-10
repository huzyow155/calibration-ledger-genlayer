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
      eventText: "Did astronauts Neil Armstrong and Buzz Aldrin land on the Moon during the Apollo 11 mission?",
      probBp: 9500,
      resolveAfter: resolveAfter,
      sourceUrl: "https://en.wikipedia.org/wiki/Apollo_11",
      expectedOutcome: "YES",
      verbatimQuote: "After a three-day transit, Armstrong and Aldrin descended to the surface aboard",
    },
    {
      id: "case_a2",
      forecasterLabel: "Forecaster A",
      client: clientA,
      forecasterAddress: accA.address,
      eventText: "Was the maiden launch of the Falcon 9 rocket conducted in the year 2020 or later?",
      probBp: 9900, // THE TRAP CASE (Overconfident call on failed catch)
      resolveAfter: resolveAfter,
      sourceUrl: "https://en.wikipedia.org/wiki/Falcon_9",
      expectedOutcome: "NO",
      verbatimQuote: "The first Falcon 9 launch was on June 4, 2010",
    },
    {
      id: "case_b1",
      forecasterLabel: "Forecaster B",
      client: clientB,
      forecasterAddress: accB.address,
      eventText: "Is the Falcon 9 launch vehicle designed and manufactured by the Boeing company?",
      probBp: 1000, // Well-calibrated honest low probability call
      resolveAfter: resolveAfter,
      sourceUrl: "https://en.wikipedia.org/wiki/Falcon_9",
      expectedOutcome: "NO",
      verbatimQuote: "Manufacturer SpaceX",
    },
    {
      id: "case_b2",
      forecasterLabel: "Forecaster B",
      client: clientB,
      forecasterAddress: accB.address,
      eventText: "Is the James Webb Space Telescope designed primarily to conduct infrared astronomy?",
      probBp: 9000, // Well-calibrated honest high probability call
      resolveAfter: resolveAfter,
      sourceUrl: "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope",
      expectedOutcome: "YES",
      verbatimQuote: "The James Webb Space Telescope (JWST) is a space telescope designed to conduct i",
    },
    {
      id: "case_c1",
      forecasterLabel: "Forecaster C (Active/Contest)",
      client: clientC,
      forecasterAddress: accC.address,
      eventText: "Did the Apollo 11 astronauts return safely to Earth aboard the command module Columbia?",
      probBp: 8000,
      resolveAfter: resolveAfter,
      sourceUrl: "https://en.wikipedia.org/wiki/Apollo_11",
      expectedOutcome: "YES",
      verbatimQuote: "the crew returned safely to Earth on July 24, splashing down in the Pacific Ocean",
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
