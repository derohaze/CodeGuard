---
name: service-orchestrator
description: Service lifecycle management — start, stop, check, and monitor backend (FastAPI+Node gateway) and frontend (Vite) services. Load this skill when you need to bring up the target application or manage running services during testing.
allowed-tools:
  - shell
  - http
  - file_read
  - web_fetch
---

# Service orchestrator — lifecycle playbook

Use this skill to start, verify, and stop the Aegix application services. The project has three services:

| Service | Location | Port |
|---|---|---|
| Backend Python API | `backend/` | 8000 |
| Backend Node gateway | `backend/node/` | 7000 |
| Frontend Vite dev server | root | 5173 |

## 1. Prerequisites check

Before starting anything:

- Verify Python 3.14+ is available: `python --version`
- Verify Bun is available: `bun --version`
- Verify pnpm is available (for node gateway): `pnpm --version`
- Check backend `.env` exists and has `NVIDIA_API_KEY` set
- Check no stale processes on target ports:
  - `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue` (Windows)
  - `lsof -ti:8000 2>/dev/null` (Linux/macOS)

## 2. Start backend

```powershell
# From the repository root
cd backend
python main.py
```

This starts both the FastAPI Python API (port 8000) and the Node.js gateway (port 7000). The process runs in the foreground — you should run it in a **separate terminal** or **background process**.

To run in background on Windows:
```powershell
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "backend" -RedirectStandardOutput "backend.log" -RedirectStandardError "backend-err.log"
```

Wait 5 seconds then verify:
```powershell
Start-Sleep -Seconds 5
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health
```

Expected: `200`. If not, wait 5 more seconds and retry. If still failing, read `backend.log` / `backend-err.log`.

## 3. Start frontend

```powershell
# From the repository root, in a separate terminal
bun run dev
```

To run in background on Windows:
```powershell
Start-Process -NoNewWindow -FilePath "bun" -ArgumentList "run dev" -WorkingDirectory "." -RedirectStandardOutput "frontend.log" -RedirectStandardError "frontend-err.log"
```

Verify:
```powershell
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173
```

Expected: `200`.

## 4. Health check (both services)

```powershell
# Backend API health
curl -s http://127.0.0.1:8000/health

# Frontend
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:5173

# Node gateway (if needed)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:7000/health
```

All should return `200`.

## 5. Stop services

To stop gracefully:

```powershell
# Find and kill backend Python process
Get-Process -Id (Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force

# Find and kill frontend (bun) process  
Get-Process -Id (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue).OwningProcess -ErrorAction SilentlyContinue | Stop-Process -Force

# Verify all ports are free
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 7000 -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue
```

On Linux/macOS:
```bash
kill $(lsof -ti:8000) 2>/dev/null; kill $(lsof -ti:5173) 2>/dev/null; kill $(lsof -ti:7000) 2>/dev/null; true
```

## 6. Restart flow (for testing with changes)

```powershell
# 1. Stop services
# 2. Rebuild if needed: cd backend && pip install -r requirements.txt
# 3. Start backend
# 4. Wait for health
# 5. Start frontend
# 6. Verify both
```

Always verify with an actual HTTP request — process being alive does not mean the service is ready.
