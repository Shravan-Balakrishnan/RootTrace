# RootTrace Mobile

React Native + Expo Go app dedicated exclusively to **RootTrace Live** operational workflows.

## Screens

| Screen | Description |
|--------|-------------|
| **Overview** | Live-lab process health, uptime metrics, and process control (Start/Stop/Restart) |
| **Debug** | Run the 4-agent AI investigation pipeline, review hypotheses, approve/reject patch proposals |
| **Incidents** | Postmortem records from the historical incident memory |
| **Audit** | Immutable audit log of all operator approvals and rejections |

## Setup

### 1. Configure the backend host

```bash
cp .env.local.example .env.local
```

Edit `.env.local` and set `EXPO_PUBLIC_API_BASE_URL` to your backend's **LAN IP** (not `localhost`):

```
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000
```

Find your LAN IP:
- **Windows**: `ipconfig` — look for "IPv4 Address"
- **macOS/Linux**: `ifconfig` or `ip addr`

Your device and computer must be **on the same Wi-Fi network**.

### 2. Start the RootTrace backend

```bash
# From the repo root
cd c:\Users\shrbk\Desktop\RootTrace
.venv\Scripts\uvicorn.exe backend.app.main:app --host 0.0.0.0 --port 8000
```

> Use `--host 0.0.0.0` so the backend binds to all interfaces (not just localhost).

### 3. Install and run

```bash
cd mobile
npm install
npx expo start
```

Scan the QR code with the **Expo Go** app on your device.

## Architecture

- `App.tsx` — Tab navigator (no external router dependency)
- `src/api.ts` — API client reading `EXPO_PUBLIC_API_BASE_URL`
- `src/theme.ts` — Design tokens
- `src/components/ui.tsx` — Shared primitive components
- `src/screens/` — Individual screen components
