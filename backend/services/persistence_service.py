"""
Persistence Service (SQL)
Handles saving and loading session data to/from PostgreSQL (or local SQLite)
"""
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
from models import UserSession, WatchlistItem, AlertItem, LogItem, ScripMaster
from datetime import datetime
from typing import Dict, List, Optional
import threading

# Global instance
persistence_service = None

class PersistenceService:
    def __init__(self):
        self.lock = threading.Lock()
        # Initialize tables on startup
        try:
            Base.metadata.create_all(bind=engine)
            print("✅ SQL Database tables created/initialized")
        except Exception as e:
            print(f"❌ Failed to create database tables: {e}")
            import traceback
            traceback.print_exc()

    def save_session(self, session_id: str, session):
        """
        Save a single session to the database
        Optimized for SQLite
        """
        db = SessionLocal()
        try:
            # 1. Update/Create UserSession
            db_session = db.query(UserSession).filter(UserSession.id == session_id).first()
            if not db_session:
                db_session = UserSession(id=session_id)
                db.add(db_session)
            
            db_session.client_id = session.client_id
            db_session.jwt_token = session.jwt_token
            db_session.feed_token = session.feed_token
            db_session.api_key = session.api_key
            db_session.is_paused = session.is_paused
            db_session.last_activity = session.last_activity or datetime.utcnow()

            # 2. Sync Watchlist (Atomic)
            db.query(WatchlistItem).filter(WatchlistItem.session_id == session_id).delete()
            if session.watchlist:
                db.bulk_insert_mappings(WatchlistItem, [
                    {
                        "session_id": session_id,
                        "symbol": item['symbol'],
                        "token": item['token'],
                        "exch_seg": item['exch_seg'],
                        "pdc": item.get('pdc'),
                        "pdh": item.get('pdh'),
                        "pdl": item.get('pdl')
                    } for item in session.watchlist
                ])

            # 3. Sync Alerts (Atomic)
            db.query(AlertItem).filter(AlertItem.session_id == session_id).delete()
            if session.alerts:
                db.bulk_insert_mappings(AlertItem, [
                    {
                        "alert_id": alert.get('id', alert.get('alert_id')),
                        "session_id": session_id,
                        "symbol": alert['symbol'],
                        "token": alert['token'],
                        "condition": alert['condition'],
                        "price": alert['price'],
                        "active": alert.get('active', True),
                        "type": alert.get('type', 'MANUAL'),
                        "created_at": datetime.fromisoformat(alert['created_at'].replace('Z', '')) if 'created_at' in alert and alert['created_at'] else datetime.utcnow()
                    } for alert in session.alerts
                ])

            # 4. Sync Logs (Atomic, Keep last 50)
            db.query(LogItem).filter(LogItem.session_id == session_id).delete()
            if session.logs:
                db.bulk_insert_mappings(LogItem, [
                    {
                        "session_id": session_id,
                        "timestamp": datetime.fromisoformat(log['time'].replace('Z', '')) if isinstance(log['time'], str) else log['time'],
                        "symbol": log['symbol'],
                        "message": log['msg'],
                        "type": log.get('type', 'info'),
                        "current_price": log.get('current_price'),
                        "target_price": log.get('target_price')
                    } for log in session.logs[-50:]
                ])

            db.commit()
            print(f"✅ Persistence: Session {session_id} saved (W:{len(session.watchlist)} A:{len(session.alerts)})")
        except Exception as e:
            db.rollback()
            print(f"❌ Failed to save session {session_id} to Neon.tech: {e}")
            import traceback
            traceback.print_exc()
            # Re-raise to let caller know save failed
            raise
        finally:
            db.close()

    def save_sessions(self, sessions_data: Dict):
        """
        Save all sessions to the database (Maintenance/Legacy)
        """
        for session_id, session in sessions_data.items():
            self.save_session(session_id, session)

    def load_sessions(self) -> Dict:
        """
        Load all sessions from the database
        Optimized with joinedload to prevent N+1 query problem
        """
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        sessions_dict = {}
        try:
            # Delete sessions with no client_id (orphans) first
            db.query(UserSession).filter(UserSession.client_id == None).delete()
            db.commit()

            # Join all relations in one or two efficient queries
            db_sessions = db.query(UserSession).options(
                joinedload(UserSession.watchlist),
                joinedload(UserSession.alerts),
                joinedload(UserSession.logs)
            ).all()

            for db_session in db_sessions:
                s_data = {
                    "client_id": db_session.client_id,
                    "jwt_token": db_session.jwt_token,
                    "feed_token": db_session.feed_token,
                    "api_key": db_session.api_key,
                    "is_paused": db_session.is_paused,
                    "last_activity": db_session.last_activity.isoformat(),
                    "watchlist": [],
                    "alerts": [],
                    "logs": []
                }
                
                # Fetch related data (now pre-loaded)
                for item in db_session.watchlist:
                    s_data['watchlist'].append({
                        "symbol": item.symbol,
                        "token": item.token,
                        "exch_seg": item.exch_seg,
                        "pdc": item.pdc,
                        "pdh": item.pdh,
                        "pdl": item.pdl
                    })
                
                for alert in db_session.alerts:
                    s_data['alerts'].append({
                        "id": alert.alert_id, # Return UUID to frontend
                        "symbol": alert.symbol,
                        "token": alert.token,
                        "condition": alert.condition,
                        "price": alert.price,
                        "active": alert.active,
                        "type": alert.type,
                        "created_at": alert.created_at.isoformat() if alert.created_at else None
                    })
                
                for log in db_session.logs:
                    s_data['logs'].append({
                        "time": log.timestamp.isoformat(),
                        "symbol": log.symbol,
                        "msg": log.message,
                        "type": log.type,
                        "current_price": log.current_price,
                        "target_price": log.target_price
                    })
                
                sessions_dict[db_session.id] = s_data
            
            return sessions_dict
        except Exception as e:
            print(f"Failed to load sessions from SQL: {e}")
            return {}
        finally:
            db.close()

    def cleanup_old_sessions(self, days: int = 3):
        """Delete sessions older than N days to keep DB lean"""
        db = SessionLocal()
        try:
            from datetime import datetime, timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Get sessions to delete
            old_sessions = db.query(UserSession).filter(UserSession.last_activity < cutoff).all()
            
            if not old_sessions:
                print("✅ No old sessions to clean up")
                return
            
            # Delete each session manually to handle cascade properly
            deleted = 0
            for session in old_sessions:
                try:
                    # Manually delete related items first
                    db.query(WatchlistItem).filter(WatchlistItem.session_id == session.id).delete()
                    db.query(AlertItem).filter(AlertItem.session_id == session.id).delete()
                    db.query(LogItem).filter(LogItem.session_id == session.id).delete()
                    db.delete(session)
                    deleted += 1
                except Exception as e:
                    print(f"⚠️ Failed to delete session {session.id}: {e}")
                    continue
            
            db.commit()
            if deleted > 0:
                print(f"✅ Cleaned up {deleted} old sessions from database")
        except Exception as e:
            db.rollback()
            print(f"⚠️ Cleanup warning (non-critical): {e}")
            # Don't raise - this is not critical for startup
        finally:
            db.close()

    def get_session_by_client(self, client_id: str) -> Dict:
        """Get the most recent session data for a specific client_id"""
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            # Find the most recent session for this client
            db_session = db.query(UserSession).options(
                joinedload(UserSession.watchlist),
                joinedload(UserSession.alerts),
                joinedload(UserSession.logs)
            ).filter(UserSession.client_id == client_id).order_by(UserSession.last_activity.desc()).first()
            
            if not db_session:
                return {}
            
            s_data = {
                "watchlist": [],
                "alerts": [],
                "logs": [],
                "is_paused": db_session.is_paused
            }
            
            for item in db_session.watchlist:
                s_data['watchlist'].append({
                    "symbol": item.symbol,
                    "token": item.token,
                    "exch_seg": item.exch_seg,
                    "pdc": item.pdc,
                    "pdh": item.pdh,
                    "pdl": item.pdl
                })
            
            for alert in db_session.alerts:
                s_data['alerts'].append({
                    "id": alert.alert_id,
                    "symbol": alert.symbol,
                    "token": alert.token,
                    "condition": alert.condition,
                    "price": alert.price,
                    "active": alert.active,
                    "type": alert.type,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                })
            
            for log in db_session.logs:
                s_data['logs'].append({
                    "time": log.timestamp.isoformat(),
                    "symbol": log.symbol,
                    "msg": log.message,
                    "type": log.type,
                    "current_price": log.current_price,
                    "target_price": log.target_price
                })
            
            return s_data
        except Exception as e:
            print(f"Failed to load session for client {client_id}: {e}")
            return {}
        finally:
            db.close()

    def get_session_by_session_id(self, session_id: str) -> Dict:
        """Get session data for a specific session_id"""
        print(f"🔍 Querying database for session {session_id}")
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            # Find the session by ID
            db_session = db.query(UserSession).filter(UserSession.id == session_id).first()
            
            if not db_session:
                print(f"❌ Session {session_id} not found in database")
                return {}
            
            print(f"✅ Found session {session_id} in database for client {db_session.client_id}")
            
            # Get related data separately
            watchlist = db.query(WatchlistItem).filter(WatchlistItem.session_id == session_id).all()
            alerts = db.query(AlertItem).filter(AlertItem.session_id == session_id).all()
            logs = db.query(LogItem).filter(LogItem.session_id == session_id).all()
            s_data = {
                "client_id": db_session.client_id,
                "jwt_token": db_session.jwt_token,
                "feed_token": db_session.feed_token,
                "api_key": db_session.api_key,
                "watchlist": [],
                "alerts": [],
                "logs": [],
                "is_paused": db_session.is_paused
            }
            
            for item in watchlist:
                s_data['watchlist'].append({
                    "symbol": item.symbol,
                    "token": item.token,
                    "exch_seg": item.exch_seg,
                    "pdc": item.pdc,
                    "pdh": item.pdh,
                    "pdl": item.pdl
                })
            
            for alert in alerts:
                s_data['alerts'].append({
                    "id": alert.alert_id,
                    "symbol": alert.symbol,
                    "token": alert.token,
                    "condition": alert.condition,
                    "price": alert.price,
                    "active": alert.active,
                    "type": alert.type,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None
                })
            
            for log in logs:
                s_data['logs'].append({
                    "time": log.timestamp.isoformat(),
                    "symbol": log.symbol,
                    "msg": log.message,
                    "type": log.type,
                    "current_price": log.current_price,
                    "target_price": log.target_price
                })
            
            return s_data
        except Exception as e:
            print(f"Failed to load session {session_id}: {e}")
            return {}
        finally:
            db.close()

    def get_latest_session_by_client_id(self, client_id: str) -> Dict:
        """Find the most recent session for a client ID - Safety net for refreshes"""
        print(f"🔍 Searching for latest session for client {client_id}")
        db = SessionLocal()
        try:
            db_session = db.query(UserSession).filter(UserSession.client_id == client_id).order_by(UserSession.last_activity.desc()).first()
            if db_session:
                return self.get_session_by_session_id(db_session.id)
            return {}
        except Exception as e:
            print(f"❌ Error finding session by client: {e}")
            return {}
        finally:
            db.close()

# Global instance
persistence_service = PersistenceService()
