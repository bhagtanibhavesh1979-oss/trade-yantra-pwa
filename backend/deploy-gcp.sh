#!/bin/bash

# Trade Yantra - Google Cloud Run Deployment Script
# This script automates the deployment of the FastAPI backend to Google Cloud Run

set -e  # Exit on error

echo "🚀 Trade Yantra - Google Cloud Run Deployment"
echo "=============================================="

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
SERVICE_NAME="trade-yantra-api"
REGION="${GCP_REGION:-us-central1}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"  # Set to 1 for no cold starts (~$5/mo)
MAX_INSTANCES="${MAX_INSTANCES:-10}"
MEMORY="${MEMORY:-512Mi}"
CPU="${CPU:-1}"
TIMEOUT="${TIMEOUT:-3600}"  # 60 minutes for WebSocket support

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Get project ID if not set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}📝 No GCP_PROJECT_ID set. Please enter your Google Cloud Project ID:${NC}"
    read -p "Project ID: " PROJECT_ID
fi

if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}❌ Error: Project ID is required${NC}"
    exit 1
fi

# Set the project
echo -e "${GREEN}📦 Setting project to: $PROJECT_ID${NC}"
gcloud config set project "$PROJECT_ID"

# Enable required APIs (if not already enabled)
echo -e "${GREEN}🔌 Enabling required APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    --quiet

# Get environment variables
echo ""
echo -e "${YELLOW}📝 Environment Variables Setup${NC}"
echo "Please provide the following (press Enter to skip and set later):"

read -p "DATABASE_URL (Neon PostgreSQL): " DATABASE_URL
read -p "CORS_ORIGINS (frontend URL, e.g., https://your-app.com): " CORS_ORIGINS

# Build environment variables argument
ENV_VARS=""
if [ ! -z "$DATABASE_URL" ]; then
    ENV_VARS="DATABASE_URL=$DATABASE_URL"
fi
if [ ! -z "$CORS_ORIGINS" ]; then
    if [ ! -z "$ENV_VARS" ]; then
        ENV_VARS="$ENV_VARS,CORS_ORIGINS=$CORS_ORIGINS"
    else
        ENV_VARS="CORS_ORIGINS=$CORS_ORIGINS"
    fi
fi

# Deploy to Cloud Run
echo ""
echo -e "${GREEN}🚢 Deploying to Google Cloud Run...${NC}"
echo "Region: $REGION"
echo "Min instances: $MIN_INSTANCES"
echo "Max instances: $MAX_INSTANCES"
echo "Memory: $MEMORY"
echo "CPU: $CPU"
echo "Timeout: ${TIMEOUT}s"
echo ""

DEPLOY_CMD="gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --min-instances $MIN_INSTANCES \
    --max-instances $MAX_INSTANCES \
    --memory $MEMORY \
    --cpu $CPU \
    --timeout $TIMEOUT"

# Add environment variables if provided
if [ ! -z "$ENV_VARS" ]; then
    DEPLOY_CMD="$DEPLOY_CMD --set-env-vars \"$ENV_VARS\""
fi

# Execute deployment
eval $DEPLOY_CMD

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')

echo ""
echo -e "${GREEN}✅ Deployment successful!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 Your API is live at:${NC}"
echo -e "${YELLOW}$SERVICE_URL${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next steps:"
echo "1. Test the API: curl $SERVICE_URL/health"
echo "2. Update your frontend VITE_API_URL to: $SERVICE_URL"
echo "3. Test WebSocket connection for stability"
echo ""
echo "To set/update environment variables later:"
echo "gcloud run services update $SERVICE_NAME --region $REGION \\"
echo "  --set-env-vars DATABASE_URL=your_db_url,CORS_ORIGINS=your_frontend_url"
echo ""
echo "To view logs:"
echo "gcloud run services logs read $SERVICE_NAME --region $REGION --limit 50"
echo ""
