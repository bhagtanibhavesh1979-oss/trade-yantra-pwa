# Rollback Instructions

## Quick Rollback to Render

If Google Cloud Run has issues, follow these steps to rollback:

---

## Step 1: Update Frontend URL

Change your frontend to point back to Render:

### Option A: Environment Variable
```bash
# frontend/.env or frontend/.env.production
VITE_API_URL=https://trade-yantra-api.onrender.com
```

### Option B: Direct Code Update
```javascript
// frontend/src/services/api.js
// Change line 9 to:
return isLocal ? 'http://localhost:8002' : 'https://trade-yantra-api.onrender.com';
```

---

## Step 2: Redeploy Frontend

```bash
cd frontend
npm run build
# Deploy to your hosting (Vercel/Netlify/etc.)
```

---

## Step 3: Verify Render is Still Running

Visit: https://trade-yantra-api.onrender.com/health

If it shows offline:
1. Go to Render dashboard
2. Find your service
3. Click "Manual Deploy" → "Deploy latest commit"

---

## Step 4: Delete Google Cloud Deployment (Optional)

Only if you're done testing:

```bash
gcloud run services delete trade-yantra-api --region us-central1
```

---

## Step 5: Test

- ✅ Login works
- ✅ Watchlist loads
- ✅ WebSocket connection stable
- ✅ Live prices update

---

## Keep Both Running (Recommended During Testing)

**Best practice:** Run both Render and Google Cloud for 1 week:
- Test Google Cloud thoroughly
- Keep Render as backup
- Switch between them by changing frontend URL
- Only delete Render after 100% confident in Google Cloud

---

## Cost of Running Both

- **Render Free:** $0
- **Google Cloud Run (min-instances=0):** $0
- **Total:** $0

No financial reason to rush!

---

## Need Help?

If you're stuck, keep using Render. Google Cloud migration is **completely optional** and can be done anytime.
