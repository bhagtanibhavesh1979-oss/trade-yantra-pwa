# Trade Yantra - Google Cloud Run Deployment Script (PowerShell)
# This script automates the deployment of the FastAPI backend to Google Cloud Run

$ErrorActionPreference = "Stop"

Write-Host "🚀 Trade Yantra - Google Cloud Run Deployment" -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan

# Configuration
$PROJECT_ID = $env:GCP_PROJECT_ID
$SERVICE_NAME = "trade-yantra-api"
$REGION = if ($env:GCP_REGION) { $env:GCP_REGION } else { "us-central1" }
$MIN_INSTANCES = if ($env:MIN_INSTANCES) { $env:MIN_INSTANCES } else { "0" }
$MAX_INSTANCES = if ($env:MAX_INSTANCES) { $env:MAX_INSTANCES } else { "10" }
$MEMORY = if ($env:MEMORY) { $env:MEMORY } else { "512Mi" }
$CPU = if ($env:CPU) { $env:CPU } else { "1" }
$TIMEOUT = if ($env:TIMEOUT) { $env:TIMEOUT } else { "3600" }

# Check if gcloud is installed
try {
    $null = Get-Command gcloud -ErrorAction Stop
} catch {
    Write-Host "❌ Error: gcloud CLI is not installed" -ForegroundColor Red
    Write-Host "Please install it from: https://cloud.google.com/sdk/docs/install" -ForegroundColor Yellow
    exit 1
}

# Get project ID if not set
if (-not $PROJECT_ID) {
    $PROJECT_ID = Read-Host "📝 Please enter your Google Cloud Project ID"
}

if (-not $PROJECT_ID) {
    Write-Host "❌ Error: Project ID is required" -ForegroundColor Red
    exit 1
}

# Set the project
Write-Host "📦 Setting project to: $PROJECT_ID" -ForegroundColor Green
gcloud config set project $PROJECT_ID

# Enable required APIs
Write-Host "🔌 Enabling required APIs..." -ForegroundColor Green
gcloud services enable cloudbuild.googleapis.com run.googleapis.com containerregistry.googleapis.com --quiet

# Get environment variables
Write-Host ""
Write-Host "📝 Environment Variables Setup" -ForegroundColor Yellow
Write-Host "Please provide the following (press Enter to skip and set later):"

$DATABASE_URL = Read-Host "DATABASE_URL (Neon PostgreSQL)"
$CORS_ORIGINS = Read-Host "CORS_ORIGINS (frontend URL, e.g., https://your-app.com)"

# Build environment variables argument
$ENV_VARS = @()
if ($DATABASE_URL) {
    $ENV_VARS += "DATABASE_URL=$DATABASE_URL"
}
if ($CORS_ORIGINS) {
    $ENV_VARS += "CORS_ORIGINS=$CORS_ORIGINS"
}

# Deploy to Cloud Run
Write-Host ""
Write-Host "🚢 Deploying to Google Cloud Run..." -ForegroundColor Green
Write-Host "Region: $REGION"
Write-Host "Min instances: $MIN_INSTANCES"
Write-Host "Max instances: $MAX_INSTANCES"
Write-Host "Memory: $MEMORY"
Write-Host "CPU: $CPU"
Write-Host "Timeout: ${TIMEOUT}s"
Write-Host ""

$deployArgs = @(
    "run", "deploy", $SERVICE_NAME,
    "--source", ".",
    "--platform", "managed",
    "--region", $REGION,
    "--allow-unauthenticated",
    "--port", "8080",
    "--min-instances", $MIN_INSTANCES,
    "--max-instances", $MAX_INSTANCES,
    "--memory", $MEMORY,
    "--cpu", $CPU,
    "--timeout", $TIMEOUT
)

# Add environment variables if provided
if ($ENV_VARS.Count -gt 0) {
    $deployArgs += "--set-env-vars"
    $deployArgs += ($ENV_VARS -join ",")
}

# Execute deployment
& gcloud @deployArgs

# Get the service URL
$SERVICE_URL = gcloud run services describe $SERVICE_NAME --region $REGION --format "value(status.url)"

Write-Host ""
Write-Host "✅ Deployment successful!" -ForegroundColor Green
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🎉 Your API is live at:" -ForegroundColor Green
Write-Host $SERVICE_URL -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Test the API: curl $SERVICE_URL/health"
Write-Host "2. Update your frontend VITE_API_URL to: $SERVICE_URL"
Write-Host "3. Test WebSocket connection for stability"
Write-Host ""
Write-Host "To set/update environment variables later:"
Write-Host "gcloud run services update $SERVICE_NAME --region $REGION ``" -ForegroundColor Yellow
Write-Host "  --set-env-vars DATABASE_URL=your_db_url,CORS_ORIGINS=your_frontend_url" -ForegroundColor Yellow
Write-Host ""
Write-Host "To view logs:"
Write-Host "gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50" -ForegroundColor Yellow
Write-Host ""
