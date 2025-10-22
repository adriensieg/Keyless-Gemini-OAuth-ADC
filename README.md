# Keyless-Gemini-OAuth-ADC
Cloud Run securely calls the Gemini API by using its service account identity to obtain short-lived OAuth 2.0 access tokens from the metadata server, eliminating the need for exposed API keys.

## Layout of the project

```
. 
├── app.py              # FastAPI backend server
├── requirements.txt    # Python dependencies
├── static/
│   ├── index.html     # Frontend HTML
│   └── script.js      # Frontend JavaScript
├─ Dockerfile
├─ cloudbuild.yaml
├─ .dockerignore
├─  deploy.sh
└── README.md          # This file
```

## Variables
```
PROJECT_ID="your-project-id"
REGION="us-central1"
REPO_NAME="query-gemini-securely"
LOCATION="$REGION"  # artifact registry region
SERVICE_SA_NAME="cloudrun-app-sa"
SERVICE_SA="$SERVICE_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
```

## Authentication
```
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION
```

## Enable required APIs
```
gcloud services enable run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com
```

## Create an Artifact Registry repository (for Docker images)
```
gcloud artifacts repositories create $REPO_NAME \
    --repository-format=docker \
    --location=$LOCATION \
    --description="Docker repo for Cloud Run images"
```

## Create the Cloud Run runtime service account (the account the service will run as)
```
gcloud iam service-accounts create $SERVICE_SA_NAME \
  --display-name="Cloud Run runtime service account for my app"
```

## Grant typical runtime roles (adjust to your needs)
```
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_SA" \
  --role="roles/logging.logWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_SA" \
  --role="roles/monitoring.metricWriter"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_SA" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_SA" \
  --role="roles/aiplatform.serviceAgent"
```

## Determine the Cloud Build service account and grant it permissions to push and deploy
```
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')
CLOUDBUILD_SA="$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"
echo "Cloud Build SA: $CLOUDBUILD_SA"
```

Grant the Cloud Build SA the permissions it needs:
- `roles/artifactregistry.writer`— to push images to Artifact Registry.
- `roles/run.admin` — to create/update Cloud Run services.
- `roles/iam.serviceAccountUser` — to allow gcloud run deploy --service-account to attach the runtime service account to the service.
- (Optionally) `roles/storage.admin` or narrower perms if you need Cloud Build to access GCS buckets.

```
# Artifact Registry writer
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUDBUILD_SA" \
  --role="roles/artifactregistry.writer"

# Cloud Run admin (allows create/update/delete of services)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUDBUILD_SA" \
  --role="roles/run.admin"

# necessary to deploy as a specific service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$CLOUDBUILD_SA" \
  --role="roles/iam.serviceAccountUser"
```

## Commands to Push to New Branch

```
git init
git remote add origin https://github.com/adriensieg/Keyless-Gemini-OAuth-ADC.git
git fetch origin
git checkout -b gemini-sa-sts-private
git add .
git commit -m "Add Gemini Web Server with Cloud Run deployment setup"
git push -u origin gemini-sa-sts-private
```
