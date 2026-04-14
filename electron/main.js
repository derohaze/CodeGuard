const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');

let mainWindow;
const INITIAL_WINDOW_WIDTH = 1120;
const INITIAL_WINDOW_HEIGHT = 720;
const MIN_WINDOW_WIDTH = 980;
const MIN_WINDOW_HEIGHT = 640;

app.setName('Khwarizm');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: INITIAL_WINDOW_WIDTH,
    height: INITIAL_WINDOW_HEIGHT,
    minWidth: MIN_WINDOW_WIDTH,
    minHeight: MIN_WINDOW_HEIGHT,
    center: true,
    show: false,
    backgroundColor: '#f8f4ee',
    autoHideMenuBar: true,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#f8f4ee',
      symbolColor: '#2a241e',
      height: 32
    },
    title: 'Khwarizm',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    },
    icon: path.join(__dirname, '../public/icon.png')
  });

  mainWindow.removeMenu();

  // ÙÙŠ Development mode Ù‡Ù†Ø­Ù…Ù„ Ù…Ù† Vite dev server
  // ÙÙŠ Production Ù‡Ù†Ø­Ù…Ù„ Ù…Ù† Ø§Ù„Ù…Ù„ÙØ§Øª Ø§Ù„Ù…Ø¨Ù†ÙŠØ©
  const isDev = process.env.NODE_ENV === 'development';
  
  if (isDev) {
    mainWindow.loadURL('http://localhost:8080');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'));
  }

  mainWindow.setTitle('Khwarizm');
  mainWindow.once('ready-to-show', () => {
    if (!mainWindow) return;
    if (mainWindow.isMaximized()) {
      mainWindow.unmaximize();
    }
    if (mainWindow.isFullScreen()) {
      mainWindow.setFullScreen(false);
    }
    mainWindow.setSize(INITIAL_WINDOW_WIDTH, INITIAL_WINDOW_HEIGHT);
    mainWindow.center();
    mainWindow.show();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(() => {
  ipcMain.removeHandler('dialog:pick-path');
  ipcMain.handle('dialog:pick-path', async (_event, kind) => {
    if (!mainWindow) return null;

    const properties = kind === 'file' ? ['openFile'] : ['openDirectory'];
    const title = kind === 'file' ? 'Choose a file to scan' : 'Choose a folder to scan';

    const result = await dialog.showOpenDialog(mainWindow, {
      title,
      properties,
    });

    if (result.canceled || result.filePaths.length === 0) {
      return null;
    }

    return result.filePaths[0];
  });

  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
