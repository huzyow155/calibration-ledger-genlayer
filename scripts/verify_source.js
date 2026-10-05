const dns = require('dns');
dns.setDefaultResultOrder('ipv4first');

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

async function main() {
  const deployments = JSON.parse(
    fs.readFileSync(path.join(__dirname, 'deploy/deployments.json'), 'utf8')
  );
  const deployTxHash = deployments.calibrationLedger.deployTxHash;
  const localContractPath = path.join(__dirname, '../contracts/CalibrationLedger.py');
  const localCode = fs.readFileSync(localContractPath, 'utf8');
  const localSha256 = crypto.createHash('sha256').update(localCode, 'utf8').digest('hex');

  console.log("Local contract SHA-256:", localSha256);
  console.log("Fetching deploy transaction via RPC eth_getTransactionByHash:", deployTxHash);

  const rpcUrl = deployments.rpc;
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
    throw new Error("RPC returned empty result for deploy tx: " + JSON.stringify(json));
  }

  // Contract code is in json.result.data.contract_code (base64 encoded)
  const contractCodeB64 = json.result.data?.contract_code;
  if (!contractCodeB64) {
    throw new Error("No data.contract_code in transaction: " + JSON.stringify(json.result.data));
  }

  const decodedSource = Buffer.from(contractCodeB64, 'base64').toString('utf8');
  const chainSha256 = crypto.createHash('sha256').update(decodedSource, 'utf8').digest('hex');

  console.log("On-chain decoded source SHA-256:", chainSha256);
  const match = (chainSha256 === localSha256);
  console.log("Source verification MATCH:", match);

  const verificationResult = {
    deployTxHash: deployTxHash,
    rpcUrl: rpcUrl,
    localSha256: localSha256,
    chainSha256: chainSha256,
    match: match,
    sourceBytesLength: decodedSource.length,
  };

  fs.writeFileSync(
    path.join(__dirname, 'deploy/verification_result.json'),
    JSON.stringify(verificationResult, null, 2)
  );
  console.log("Saved verification result to verification_result.json");
}

main().catch(err => {
  console.error("Verification failed:", err);
  process.exit(1);
});
