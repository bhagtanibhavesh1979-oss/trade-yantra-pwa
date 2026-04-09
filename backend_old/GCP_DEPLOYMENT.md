# Google Cloud Run Deployment Guide

Complete guide for deploying Trade Yantra FastAPI backend to Google Cloud Run.

---

## Prerequisites

### 1. Google Cloud Account
- Create account at [cloud.google.com](https://cloud.google.com)
- New users get **$300 free credit** (90 days)
- Enable billing (required even for free tier)

### 2. Install Google Cloud CLI

**Windows (PowerShell):**
```powershell
# Download and run the installer
# https://cloud.google.com/sdk/docs/install#windows

# After installation, initialize
gcloud init
```

**Mac/Linux:**
```bash
# Install gcloud CLI
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Initialize
gcloud init
```

### 3. Authenticate
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

---

## Quick Deployment (Recommended)

### Windows Users:
```powershell
cd backend
.\deploy-gcp.ps1
```

### Mac/Linux Users:
```bash
cd backend
chmod +x deploy-gcp.sh
./deploy-gcp.sh
```

The script will:
- ✅ Enable required Google Cloud APIs
- ✅ Prompt for environment variables
- ✅ Build and deploy your container
- ✅ Provide the live API URL

---

## Manual Deployment

If you prefer manual control:

### 1. Set Project ID
```bash
export GCP_PROJECT_ID="your-project-id"
gcloud config set project $GCP_PROJECT_ID
```

### 2. Enable APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 3. Deploy
```bash
cd backend

gcloud run deploy trade-yantra-api \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --min-instances 0 \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 3600 \
  --set-env-vars "DATABASE_URL=your_neon_db_url,CORS_ORIGINS=https://your-frontend.com"
```

### 4. Get Service URL
```bash
gcloud run services describe trade-yantra-api \
  --region us-central1 \
  --format 'value(status.url)'
```

---

## Environment Variables

Set these during deployment or update later:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | Neon PostgreSQL connection string | `postgresql://user:pass@host/db` |
| `CORS_ORIGINS` | Allowed frontend URLs (comma-separated) | `https://your-app.com,http://localhost:5173` |

### Update Environment Variables
```bash
gcloud run services update trade-yantra-api \
  --region us-central1 \
  --set-env-vars DATABASE_URL=new_value,CORS_ORIGINS=new_value
```

---

## Configuration Options

### Free Tier (Recommended for Testing)
```bash
--min-instances 0      # Scales to zero when idle (FREE)
--max-instances 10     # Auto-scale up to 10 instances
--memory 512Mi         # 512 MB RAM
--cpu 1                # 1 vCPU
```

**Pros:** Free for low traffic  
**Cons:** 1-2 second cold start

### Always-On ($5-8/month)
```bash
--min-instances 1      # Always 1 instance running (NO cold starts)
--max-instances 10
--memory 512Mi
--cpu 1
```

**Pros:** No cold starts, instant response  
**Cons:** ~$5-8/month

---

## Update Your Frontend

After deployment, update your frontend to use the new URL:

### Option 1: Environment Variable (Recommended)
```bash
# frontend/.env.production
VITE_API_URL=https://trade-yantra-api-<hash>.run.app
```

### Option 2: Direct Code Change
```javascript
// frontend/src/services/api.js
const API_BASE_URL = 'https://trade-yantra-api-<hash>.run.app';
```

Redeploy your frontend after making changes.

---

## Testing Your Deployment

### 1. Health Check
```bash
curl https://your-service-url.run.app/health
```

Expected response:
```json
{
  "status": "healthy",
  "active_sessions": 0,
  "scrip_master_loaded": true
}
```

### 2. WebSocket Connection
Open your frontend and:
- ✅ Login successfully
- ✅ Add a stock to watchlist
- ✅ Verify live prices update
- ✅ **Monitor for 5+ minutes** - connection should stay stable (no dropouts)
- ✅ Test alert triggering

### 3. Monitor Logs
```bash
# View recent logs
gcloud run services logs read trade-yantra-api \
  --region us-central1 \
  --limit 50

# Tail logs (follow)
gcloud run services logs tail trade-yantra-api \
  --region us-central1
```

---

## Rollback to Render

If you need to rollback:

### 1. Keep Using Render URL
```bash
# frontend/.env.production
VITE_API_URL=https://trade-yantra-api.onrender.com
```

### 2. Delete Google Cloud Deployment (Optional)
```bash
gcloud run services delete trade-yantra-api \
  --region us-central1
```

**Your Render deployment is unaffected** - just update frontend URL back.

---

## Cost Estimation

### Free Tier (min-instances=0)
- **2 million requests/month** - FREE
- **360,000 GB-seconds** - FREE
- **180,000 vCPU-seconds** - FREE

**Your expected usage:** $0/month (well within free tier)

### Always-On (min-instances=1)
- **1 instance running 24/7:** ~$5-8/month
- **Additional requests:** FREE (within limits)

**Recommended:** Start with free tier, upgrade if cold starts are an issue.

---

## Useful Commands

### View Service Details
```bash
gcloud run services describe trade-yantra-api --region us-central1
```

### Update Service
```bash
gcloud run services update trade-yantra-api \
  --region us-central1 \
  --min-instances 1  # Example: remove cold starts
```

### List All Services
```bash
gcloud run services list
```

### Delete Service
```bash
gcloud run services delete trade-yantra-api --region us-central1
```

---

## Troubleshooting

### Issue: "Permission denied"
**Solution:** Ensure billing is enabled on your Google Cloud project.

### Issue: "Service unavailable"
**Solution:** Check deployment logs:
```bash
gcloud run services logs read trade-yantra-api --region us-central1 --limit 50
```

### Issue: "CORS errors in frontend"
**Solution:** Update CORS_ORIGINS environment variable:
```bash
gcloud run services update trade-yantra-api \
  --region us-central1 \
  --set-env-vars CORS_ORIGINS=https://your-frontend.com
```

### Issue: "WebSocket connection fails"
**Solution:** 
1. Verify `--timeout 3600` is set (60 minutes)
2. Check frontend WebSocket URL uses `wss://` (not `ws://`)

### Issue: "Cold starts too slow"
**Solution:** Upgrade to min-instances=1:
```bash
gcloud run services update trade-yantra-api \
  --region us-central1 \
  --min-instances 1
```

---

## Next Steps

1. ✅ Deploy to Google Cloud Run
2. ✅ Test thoroughly (especially WebSocket stability)
3. ✅ Update frontend URL
4. ✅ Monitor for 48 hours
5. ✅ If successful, delete Render deployment (optional)

---

## Support

- **Google Cloud Docs:** https://cloud.google.com/run/docs
- **Pricing Calculator:** https://cloud.google.com/products/calculator

---

**Questions?** Check the logs first:
```bash
gcloud run services logs read trade-yantra-api --region us-central1 --limit 100
```
