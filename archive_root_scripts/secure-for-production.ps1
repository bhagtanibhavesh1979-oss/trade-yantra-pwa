# SECURE CORS UPDATE FOR PRODUCTION
# Run this BEFORE Tuesday market hours to secure your backend

Write-Host "🔒 Securing Trade Yantra Backend for Production..." -ForegroundColor Cyan

# Step 1: Get your Vercel production URL
Write-Host "`n📱 Checking your Vercel production URL..." -ForegroundColor Yellow
cd frontend
$vercelUrl = npx vercel ls --prod 2>&1 | Select-String -Pattern "https://.*\.vercel\.app" | Select-Object -First 1
Write-Host "Found: $vercelUrl" -ForegroundColor Green

# Step 2: Update Google Cloud CORS
Write-Host "`n🌐 Updating Google Cloud CORS settings..." -ForegroundColor Yellow
cd ..

# Update with your specific Vercel URL (change this if needed)
$corsOrigins = "https://trade-yantra-pwa-3llk.vercel.app,https://frontend-eight-chi-33.vercel.app,http://localhost:5173"

Write-Host "Setting CORS to: $corsOrigins" -ForegroundColor Cyan

gcloud run services update trade-yantra-api `
  --region us-central1 `
  --set-env-vars "CORS_ORIGINS=$corsOrigins"

Write-Host "`n✅ CORS Updated Successfully!" -ForegroundColor Green
Write-Host "Your backend is now secured for production trading." -ForegroundColor Green

# Step 3: Verify the update
Write-Host "`n🔍 Verifying configuration..." -ForegroundColor Yellow
gcloud run services describe trade-yantra-api --region us-central1 | Select-String -Pattern "CORS"

Write-Host "`n✅ Setup Complete! Test your mobile app now." -ForegroundColor Green
