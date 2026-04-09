# Trade Yantra Frontend

React + Vite frontend for Trade Yantra trading alerts application.

## Quick Start

### 1. Install Dependencies

```bash
npm install
```

### 2. Configure Backend URL

Create `.env.local` file:

```env
VITE_API_URL=http://localhost:8002
```

For production, set to your Railway backend URL:

```env
VITE_API_URL=https://your-backend.railway.app
```

### 3. Run Development Server

```bash
npm run dev
```

Open `http://localhost:5173`

## Features

✅ Manual login with Angel One credentials  
✅ Real-time WebSocket price streaming  
✅ Watchlist with search, filters, and sorting  
✅ 3-6-9 auto-alert generation  
✅ Activity logs  
✅ Dark theme UI with TailwindCSS  

## Build for Production

```bash
npm run build
```

Output: `dist/` folder

## Deploy to Vercel

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel

# Set environment variable
vercel env add VITE_API_URL
```

## Technology Stack

- **React 19** - UI framework
- **Vite** - Build tool
- **TailwindCSS 4** - Styling
- **Axios** - HTTP client
- **WebSocket API** - Real-time streaming

## Project Structure

```
src/
├── components/
│   ├── LoginPage.jsx
│   ├── Dashboard.jsx
│   ├── WatchlistTab.jsx
│   ├── AlertsTab.jsx
│   └── LogsTab.jsx
├── services/
│   ├── api.js
│   └── websocket.js
├── App.jsx
├── main.jsx
└── index.css
```
