import sys
print("STEP 1: Starting Diagnostic")

try:
    print("STEP 2: Importing session_manager")
    from services.session_manager import session_manager
    print("STEP 3: SUCCESS - session_manager loaded")
    
    print("STEP 4: Importing angel_service")
    from services.angel_service import angel_service
    print("STEP 5: SUCCESS - angel_service loaded")
    
    print("STEP 6: Importing routes/auth")
    from routes import auth
    print("STEP 7: SUCCESS - auth loaded")
    
    print("STEP 8: Importing routes/paper")
    from routes import paper
    print("STEP 9: SUCCESS - paper loaded")
    
    print("STEP 10: Importing routes/live")
    from routes import live
    print("STEP 11: SUCCESS - live loaded")

    print("STEP 12: Importing routes/watchlist")
    from routes import watchlist
    print("STEP 13: SUCCESS - watchlist loaded")

    print("STEP 14: Importing routes/alerts")
    from routes import alerts
    print("STEP 15: SUCCESS - alerts loaded")
    
    print("STEP 16: Importing routes/indices")
    from routes import indices
    print("STEP 17: SUCCESS - indices loaded")

    print("STEP 18: Importing routes/stream")
    from routes import stream
    print("STEP 19: SUCCESS - stream loaded")

except Exception as e:
    import traceback
    print(f"FAILED AT STEP {sys.exc_info()[-1].tb_lineno if sys.exc_info()[-1] else 'unknown'}")
    traceback.print_exc()
