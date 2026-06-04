const { contextBridge, ipcRenderer } = require('electron');

// هنا هتعرض APIs للـ frontend عشان يتواصل مع الـ backend
contextBridge.exposeInMainWorld('electronAPI', {
  // مثال: استدعاء backend APIs
  // callBackend: (endpoint, data) => ipcRenderer.invoke('backend-call', endpoint, data),
  
  // هتضيف المزيد لما تبدأ في الـ backend
  platform: process.platform,
  pickPath: (kind) => ipcRenderer.invoke('dialog:pick-path', kind),
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  }
});
