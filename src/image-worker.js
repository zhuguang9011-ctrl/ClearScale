const { parentPort, workerData } = require('node:worker_threads');
const { prepare, finish } = require('./optimize');
(async () => {
  const result = await (workerData.action === 'prepare' ? prepare : finish)(...workerData.args);
  parentPort.postMessage({ result });
})().catch(error => { throw error; });
