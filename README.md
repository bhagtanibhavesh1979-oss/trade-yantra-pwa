# Trade Yantra PWA

Progressive Web App for Real-Time Stock Price Alerts with Angel One SmartAPI Integration

## 🎯 Features

- ✅ Real-time price streaming via WebSocket
- ✅ Smart 3-6-9 alert system
- ✅ Watchlist management with persistence
- ✅ Live market indices tracking
- ✅ Browser notifications
- ✅ Mobile PWA support (works offline)
- ✅ Dark theme UI

## 🏗️ Architecture

```
Frontend (React PWA - Vercel)
         ↓
    WebSocket
         ↓
FastAPI Backend (Railway)
         ↓
Angel One SmartAPI
```

## 🚀 Quick Start

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

Backend runs at: http://localhost:8002

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

## 📱 Mobile Access

This is a Progressive Web App (PWA) that works great on mobile:

1. Open the deployed URL on your phone
2. Tap "Add to Home Screen"
3. Use it like a native app!

## 🔧 Environment Variables

### Backend

Optional (auto-configured on Railway):
```
PORT=8002
CORS_ORIGINS=*
```

### Frontend

Required in `.env.local`:
```
VITE_API_URL=http://localhost:8002
```

For production, set to your Railway backend URL.

## 📚 Documentation

- [Testing Guide](TESTING.md) - Local testing instructions
- [Backend README](backend/README.md) - API documentation
- [Frontend README](frontend/README.md) - Frontend documentation

## 🚀 Deployment

**Backend**: Deployed on Railway  
**Frontend**: Deployed on Vercel

See individual README files for deployment details.

## ⚠️ Important Notes

- No credentials are stored on the server
- Sessions are in-memory only (cleared on restart)
- Railway free tier sleeps after inactivity (15-30s cold start)
- Market hours: 9:15 AM - 3:30 PM IST, Monday-Friday

## 📄 License

MIT
