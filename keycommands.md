# Agent Deployment Commands

This document contains the key commands for running and deploying the agent both locally and in Google Cloud.

## Running the Agent Locally

1. **Configure environment**: Set `AGENT_LOCATION=local` in the `.env` file

2. **Start the agent**: Run the following commands in 2 separate terminals:
   ```bash
   poetry run python app.py
   poetry run fast-local
   ```

## Running the Agent in Google Cloud

### 1. Deploy to Cloud Run

Run the following command to deploy to Cloud Run (assumes Google project is set up):

```bash
gcloud run deploy star-agent-service \
  --source . \
  --region us-central1 \
  --project refiner-agent \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=refiner-agent,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=true"

  OR
  gcloud run deploy star-agent-service --source . --region us-central1 --project refiner-agent --allow-unauthenticated --set-env-vars="GOOGLE_CLOUD_PROJECT=refiner-agent,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=true"


```

### 2. Configure and Start

1. **Configure environment**: Set `AGENT_LOCATION=cloud_run` in the `.env` file

2. **Start the agent**: Run the following commands in 2 separate terminals:
   ```bash
   poetry run python app.py
   poetry run fast-local
   ```

