# Run this to update Google Cloud with the correct Vercel URLs

# PowerShell version
gcloud run services update trade-yantra-api --region us-central1 --update-env-vars "CORS_ORIGINS=https://frontend-eight-chi-33.vercel.app,https://trade-yantra-pwa.vercel.app,http://localhost:5173"
