const { parentPort, workerData } = require('node:worker_threads');
const { prepare, finish } = require('./optimize');
(async () => {
  const actions = { prepare, finish, surface: require('./surface').surface };
  if (!actions[workerData.action]) throw new Error('未知图像处理操作');
  const result = await actions[workerData.action](...workerData.args);
  parentPort.postMessage({ result });
})().catch(error => { throw error; });
