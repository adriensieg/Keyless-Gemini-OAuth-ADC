#!/bin/bash

# Cloud Run Deployment Script for Gemini Web Server

set -e

# Configuration
PROJECT_ID=${1:-"your-project-id"}
SERVICE_NAME="gemini-web-server"
REGION=${2:-"us-central1"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Cloud Run deployment for Gemini Web Server${NC}"
echo "----------------------------------------"

# Check if project ID is provided
if [ "$PROJECT_ID" == "your-project-id" ]; then
    echo -e "${RED}Error: Please provide your Google Cloud Project ID${NC}"
    echo "Usage: ./deploy.sh YOUR_PROJECT_ID [REGION]"
    exit 1
fi

# Set the project
echo -e "${YELLOW}Setting project to: ${PROJECT_ID}${NC}"
gcloud config set project ${PROJECT_ID}

# Enable necessary APIs
echo -e "${YELLOW}Enabling necessary APIs...${NC}"
gcloud services enable containerregistry.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Build the Docker image
echo -e "${YELLOW}Building Docker image...${NC}"
docker build -t ${IMAGE_NAME} .

# Push to Container Registry
echo -e "${YELLOW}Pushing image to Container Registry...${NC}"
docker push ${IMAGE_NAME}

# Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --port 8080 \
    --set-env-vars="PYTHONUNBUFFERED=1"

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo "----------------------------------------"
echo -e "${GREEN}Deployment completed successfully!${NC}"
echo -e "${GREEN}Service URL: ${SERVICE_URL}${NC}"
echo "----------------------------------------"
echo ""
echo "Next steps:"
echo "1. Visit your service at: ${SERVICE_URL}"
echo "2. Monitor logs: gcloud run services logs read ${SERVICE_NAME} --region ${REGION}"
echo "3. Update service: Run this script again after making changes"
