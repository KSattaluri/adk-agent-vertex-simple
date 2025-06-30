# Project Setup Guide

## 1. Google Cloud Setup (UI Steps) [Reference](https://cloud.google.com/vertex-ai/docs/start/cloud-environment)

### 1.1 Create Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click project dropdown → **New Project**
3. Enter project name and ID → **Create**

### 1.2 Enable APIs
1. Go to **APIs & Services** → **Library**
2. Search and enable each:
   - Vertex AI API
   - Cloud Run API
   - Cloud Build API
   - Artifact Registry API
   - Firebase Management API

## 2. Firebase Setup

### 2.1 Link Firebase Project
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **Add project** → Select your existing GCP project
3. Continue through setup (skip Analytics)

### 2.2 Enable Authentication
1. Go to **Authentication** → **Sign-in method**
2. Click **Google** → **Enable** → **Save**

### 2.3 Create Firestore Database
1. Go to **Firestore Database** → **Create database**
2. **Database ID**: Enter `refiner-agent` (NOT default)
3. Choose **Production mode** → Select location → **Create**

### 2.4 Get Firebase Credentials
1. Go to **Project Settings** → **Service accounts**
2. Click **Generate new private key** → **Generate key**
3. Save as `.firebase/refiner-agent-firebase-adminsdk-xxxxx.json`

### 2.5 Get Web Config
1. Go to **Project Settings** → **General**
2. Under "Your apps" → **Add app** → **Web**
3. Register app → Copy the config values

## 3. Google OAuth Setup

### 3.1 Create OAuth Client
1. In GCP Console → **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Add authorized redirect URIs:
   - `http://localhost:5005/auth/callback`
5. Click **Create** → Copy Client ID and Secret

## 4. Local Machine Setup

```bash
# Authenticate Google Cloud
gcloud auth login
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID

# Install and authenticate Firebase
npm install -g firebase-tools
firebase login
firebase use YOUR_PROJECT_ID

# Create directories
mkdir -p .firebase
```

## 5. Environment Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env and update these values:
```

Key values to update in `.env`:
- `GOOGLE_CLOUD_PROJECT` - Your GCP project ID
- `GOOGLE_CLOUD_LOCATION` - Your preferred region (e.g., us-central1)
- `FIREBASE_PROJECT_ID` - Same as GCP project ID
- `FIREBASE_CLIENT_API_KEY` - From Firebase web config
- `FIREBASE_CREDENTIALS_PATH` - Path to your Firebase service account JSON
- `GOOGLE_OAUTH_CLIENT_ID` - From OAuth client creation
- `GOOGLE_OAUTH_CLIENT_SECRET` - From OAuth client creation
- `AGENT_CLOUD_RUN_URL` - After deploying agent (if using cloud_run)

## 6. Install Dependencies

```bash
# Install dependencies
poetry install
```

## 7. Run Locally

1. Set `AGENT_LOCATION=local` in the `.env` file

2. Run in separate terminals:
   ```bash
   # Terminal 1: Start the agent
   poetry run python app.py
   
   # Terminal 2: Start the FastAPI backend
   poetry run fast-local
   ```

3. Login at http://localhost:5005/login

## 8. Deploy to Cloud Run 

1. Deploy the agent to Cloud Run:
   ```bash
   gcloud run deploy star-agent-service \
     --source . \
     --region us-central1 \
     --project refiner-agent \
     --allow-unauthenticated \
     --set-env-vars="GOOGLE_CLOUD_PROJECT=refiner-agent,GOOGLE_CLOUD_LOCATION=us-central1,GOOGLE_GENAI_USE_VERTEXAI=true"
   ```

2. Update `.env` file:
   - Set `AGENT_LOCATION=cloud_run`
   - Set `AGENT_CLOUD_RUN_URL` to the deployed service URL

3. Run the FastAPI backend locally:
   ```bash
   poetry run fast-local
   ```

4. Login at http://localhost:5005/login

## 9. Quick Checklist

### Google Cloud
- [ ] GCP project created
- [ ] APIs enabled (Vertex AI, Cloud Run, Cloud Build, Artifact Registry, Firebase)
- [ ] `gcloud auth` completed

### Firebase
- [ ] Firebase project linked to GCP project
- [ ] Google authentication enabled
- [ ] Firestore database `refiner-agent` created (NOT default)
- [ ] Firebase service account JSON downloaded
- [ ] `firebase login` completed

### OAuth & Environment
- [ ] OAuth client created with redirect URIs
- [ ] `.env.example` copied to `.env`
- [ ] All `.env` values updated

### Final Steps
- [ ] Dependencies installed (`poetry install`)
- [ ] Agent running (`poetry run python app.py`)
- [ ] Backend running (`poetry run fast-local`)
- [ ] Can login at http://localhost:5005/login