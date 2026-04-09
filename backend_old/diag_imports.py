
print("Step 1: Importing os, sys")
import os, sys
print("Step 2: Importing fastapi")
from fastapi import FastAPI
print("Step 3: Loading dotenv")
from dotenv import load_dotenv
load_dotenv()
print("Step 4: Importing session_manager")
from services.session_manager import session_manager
print("Step 5: Importing paper_service")
from services.paper_service import paper_service
print("Step 6: Importing auth router")
from routes import auth
print("Step 7: Importing watchlist router")
from routes import watchlist
print("Step 8: Importing alerts router")
from routes import alerts
print("Step 9: Importing stream router")
from routes import stream
print("Step 10: Importing indices router")
from routes import indices
print("Step 11: Importing paper router")
from routes import paper
print("Success! All imports worked.")
