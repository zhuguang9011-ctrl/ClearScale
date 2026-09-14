const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('clearScale', {
  chooseImages: () => ipcRenderer.invoke('images:choose'),
  chooseFolder: () => ipcRenderer.invoke('folder:choose'),
  openFolder: folder => ipcRenderer.invoke('folder:open', folder),
  engineStatus: () => ipcRenderer.invoke('engine:status'),
  start: payload => ipcRenderer.invoke('upscale:start', payload),
  cancel: () => ipcRenderer.invoke('upscale:cancel'),
  onProgress: callback => ipcRenderer.on('upscale:progress', (_, value) => callback(value))
});
