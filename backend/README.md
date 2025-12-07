# Trade Yantra - FastAPI Backend

Progressive Web App Trading Backend with Angel One SmartAPI Integration

## Features
- ✅ Manual login (no credential storage)
- ✅ Real-time WebSocket streaming
- ✅ Watchlist management
- ✅ 3-6-9 alert system
- ✅ Auto-reconnect on Railway sleep
- ✅ In-memory session storage

## Local Development

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Server
```bash
uvicorn main:app --reload
```

Server will start at: `http://localhost:8000`

## API Documentation

Once running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Endpoints

### Authentication
- `POST /api/auth/login` - Login with Angel One credentials
- `POST /api/auth/logout` - Logout and clear session
- `GET /api/auth/session/{session_id}` - Check session validity

### Watchlist
- `GET /api/watchlist/{session_id}` - Get watchlist
- `POST /api/watchlist/add` - Add stock to watchlist
- `DELETE /api/watchlist/remove` - Remove stock
- `POST /api/watchlist/refresh` - Refresh LTP and weekly close
- `GET /api/watchlist/search/{query}` - Search symbols

### Alerts
- `GET /api/alerts/{session_id}` - Get all alerts
- `POST /api/alerts/create` - Create manual alert
- `POST /api/alerts/generate` - Auto-generate 3-6-9 alerts
- `DELETE /api/alerts/delete` - Delete alert
- `POST /api/alerts/pause` - Pause/resume monitoring
- `GET /api/alerts/logs/{session_id}` - Get alert logs

### WebSocket
- `WS /ws/stream/{session_id}` - Real-time data stream

## Deployment on Railway

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Backend ready for deployment"
   git push
   ```

2. **Connect to Railway**
   - Login to [railway.app](https://railway.app)
   - Create new project from GitHub repo
   - Select `backend` folder as root directory

3. **Set Environment Variables**
   ```
   CORS_ORIGINS=https://your-frontend.vercel.app
   ```

4. **Deploy**
   - Railway will automatically deploy using `Procfile`

## Important Notes

⚠️ **No Credential Storage**: API credentials are never stored. Users must login manually each time.

⚠️ **Railway Free Tier**: Backend sleeps after 10-15 minutes of inactivity. Cold start takes 15-40 seconds.

⚠️ **Session Storage**: All sessions are stored in RAM only. They are deleted on server restart.

## Architecture

```
Frontend (React PWA)
        ↓
    WebSocket
        ↓
FastAPI Backend
        ↓
Angel One SmartAPI
```

## License

MIT
