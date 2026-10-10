const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

async function verifyContract(name, deployTxHash, localPath, rpcUrl) {
  const localCode = fs.readFileSync(localPath, 'utf8');
  const localSha256 = crypto.createHash('sha256').update(localCode, 'utf8').digest('hex');

  console.log(`\nVerifying ${name}...`);
  console.log(`Local file: ${localPath}`);
  console.log(`Local SHA-256: ${localSha256}`);
  console.log(`Deploy tx hash: ${deployTxHash}`);

  const res = await fetch(rpcUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      jsonrpc: '2.0',
      id: 1,
      method: 'eth_getTransactionByHash',
      params: [deployTxHash],
    }),
  });

  const json = await res.json();
  if (!json.result) {
    throw new Error(`RPC returned empty result for ${name} deploy tx: ` + JSON.stringify(json));
  }

  const contractCodeB64 = json.result.data?.contract_code;
  if (!contractCodeB64) {
    throw new Error(`No data.contract_code in transaction for ${name}: ` + JSON.stringify(json.result.data));
  }

  const decodedSource = Buffer.from(contractCodeB64, 'base64').toString('utf8');
  const chainSha256 = crypto.createHash('sha256').update(decodedSource, 'utf8').digest('hex');

  console.log(`RPC call used: eth_getTransactionByHash`);
  console.log(`RPC payload field used: result.data.contract_code (base64 decoded)`);
  console.log(`On-chain decoded SHA-256: ${chainSha256}`);
  const match = (chainSha256 === localSha256);
  console.log(`SHA-256 Match: ${match ? 'EXACT MATCH (VERIFIED)' : 'MISMATCH'}`);

  return {
    contract: name,
    deployTxHash: deployTxHash,
    rpcMethod: 'eth_getTransactionByHash',
    rpcField: 'result.data.contract_code',
    localSha256: localSha256,
    chainSha256: chainSha256,
    match: match,
    sourceBytesLength: decodedSource.length,
  };
}

async function main() {
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'deploy/deployments.json'), 'utf8')
  );
  const rpcUrl = deployments.rpc;

  const results = {};
  if (deployments.calibrationLedger?.deployTxHash) {
    results.calibrationLedger = await verifyContract(
      'CalibrationLedger',
      deployments.calibrationLedger.deployTxHash,
      path.join(__dirname, '../contracts/CalibrationLedger.py'),
      rpcUrl
    );
  }

  if (deployments.calibratedCouncilConsumer?.deployTxHash) {
    results.calibratedCouncilConsumer = await verifyContract(
      'CalibratedCouncil',
      deployments.calibratedCouncilConsumer.deployTxHash,
      path.join(__dirname, '../examples/consumer/CalibratedCouncil.py'),
      rpcUrl
    );
  }

  fs.writeFileSync(
    path.join(__dirname, 'deploy/verification_result.json'),
    JSON.stringify(results, null, 2)
  );
  console.log("\nSaved verification result to verification_result.json");
}

main().catch(err => {
  console.error("Verification failed:", err);
  process.exit(1);
});
