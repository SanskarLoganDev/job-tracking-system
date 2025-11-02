🧭 **Job Tracking System – HustleHUB**
Track jobs in targeted companies

**Team:**
Abhigna Kandala

Heena Khan

Krishnendra Singh Tomar

Sanskar Vidyarthi

📘 Overview
The Job Tracking System (HustleHUB) is a cloud-native web application designed to help users manage, filter, and verify job listings efficiently while minimizing fake or misleading postings.
It leverages Google Cloud Platform (GCP) services such as Cloud Functions, Pub/Sub, Cloud SQL, and Cloud Scheduler for backend automation — and a Vue.js / Vuetify frontend (Google-themed) for an interactive user experience.

🌐 Key Features
🎯 Core Functionality

- Job Listing & Tracking: Users can browse, filter, and track job applications easily.
- Fake Listing Detection: Filters misleading job postings using internal validation workflows.
- Automated Status Updates: Sends notifications or reminders about job status via Pub/Sub triggers.
- Search & Filtering: Search jobs by title, company, category, or posting date.
- Secure Data Flow: Uses Secret Manager and IAM policies for secure credentials and configuration.
  ☁️ GCP Integrations
  Service Purpose
  Cloud Scheduler Automates backend triggers to check new job data.
  Cloud Functions (HTTP Trigger) Executes logic to fetch, validate, and store job postings.
  SMTP Server Handles asynchronous messaging between services.
  Firestore Provides real-time sync for frontend components.
  🧱 Architecture Overview
  [Frontend - HustleHUB (Vue.js)]
  ↓
  [Cloud Function (HTTP Trigger)]
  ↓
  [SMTP Server Topic]
  ↓
  [Firestore]
  ↓
  [Scheduler → Function → SMTP Server → Notification System]
  Data Flow Summary:

1. Frontend calls a Cloud Function (HTTP endpoint).
2. Function publishes a message to SMTP Server with new or updated job data.
3. Subscriber function processes and stores the data in Firestore.
4. Cloud Scheduler triggers validation routines at scheduled intervals.
5. Email/Notification Service sends updates to users (via Gmail API / SendGrid / SMTP).

💻 Frontend (Vue + Vuetify)
The web interface is styled in Google Material Design, providing:

- Clean cards for job listings.
- Sidebar filters (e.g., category, location, experience).
- Login and tracking dashboards.
- Responsive design and animations using Vuetify components.

📦 Project Structure

<img width="808" height="404" alt="image" src="https://github.com/user-attachments/assets/77f0de8f-7815-4c4b-9a3d-ebdadbaa3bc8" />



⚙️ Setup Instructions
1️⃣ Backend Deployment (Google Cloud)

1. Enable the required GCP APIs:gcloud services enable cloudfunctions.googleapis.com pubsub.googleapis.com sqladmin.googleapis.com
2.
3. Deploy the function:gcloud functions deploy job-tracker-func \
4. --runtime python310 \
5. --trigger-http \
6. --allow-unauthenticated \
7. --region=us-central1
8.
9. Configure Pub/Sub topics:gcloud pubsub topics create job-updates
10. gcloud pubsub subscriptions create job-updates-sub --topic=job-updates
11.
12. Set environment variables or use Secret Manager for DB credentials.

2️⃣ Frontend Setup

1. Navigate to the frontend folder:cd frontend
2. npm install
3. npm run dev
4.
5. Access the app locally at http://localhost:5173 (Vite default).
6. For production build:npm run build
7.

🧠 Tech Stack
Layer Technology
Frontend Vue.js + Vuetify + Pinia + Axios
Backend Python (Flask/Cloud Function)
Database Google Cloud SQL (MySQL/PostgreSQL)
Messaging SMTP Server
Deployment Firebase Hosting
Storage Firestore

🔐 Security and Compliance

- Secrets managed with Google Secret Manager.
- IAM roles restricted by Principle of Least Privilege.
- Data encrypted in transit (HTTPS) and at rest (Cloud SQL AES-256).

🚀 Future Enhancements

- Integrate AI-based job verification using Vertex AI.
- Add User Dashboard for tracking application progress.
- Enable Admin Portal for job moderation.
- Integrate OAuth2 Sign-In with Google Identity Platform.
- Support Resume Upload via Cloud Storage.
