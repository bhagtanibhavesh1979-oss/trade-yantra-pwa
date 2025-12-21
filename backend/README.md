# Trade Yantra - FastAPI Backend

Progressive Web App Trading Backend with Angel One SmartAPI Integration

## Features
- ✅ Manual login (no credential storage)
- ✅ Real-time WebSocket streaming
- ✅ Watchlist management
- ✅ High/Low based Alert system
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
- `POST /api/watchlist/refresh` - Refresh LTP, High/Low and PDC
- `GET /api/watchlist/search/{query}` - Search symbols

### Alerts
- `GET /api/alerts/{session_id}` - Get all alerts
- `POST /api/alerts/create` - Create manual alert
- `POST /api/alerts/generate` - Auto-generate High/Low alerts
- `DELETE /api/alerts/delete` - Delete alert
- `POST /api/alerts/pause` - Pause/resume monitoring
- `GET /api/alerts/logs/{session_id}` - Get alert logs

### WebSocket
- `WS /ws/stream/{session_id}` - Real-time data stream

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
