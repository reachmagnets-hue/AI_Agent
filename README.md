# 🎯 Reach Magnets AI Voice Calling Agent & CRM

A complete, production-ready monorepo implementing an outbound AI voice calling agent and CRM. The system imports local leads, groups them into calling campaigns, conducts automated consultative conversations via Retell AI, handles schedule slots, and automatically triggers post-call workflows (SMTP emails, Twilio SMS, WhatsApp follow-ups).

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph Frontend [Next.js 14 Dashboard]
        UI[Dashboard Command Center] --> APIClient[Axios Client & React Query]
    end

    subgraph Backend [FastAPI Server]
        API[REST Routing & Endpoints] --> DB[(SQLAlchemy Database)]
        API --> Websockets[Websocket Live Broadcaster]
        API --> WebhookRouter[Webhook Event Handler]
    end

    subgraph ExternalServices [Third-Party Services]
        Retell[Retell AI Voice Client]
        Gemini[Gemini 2.5 Flash OCR Scanner]
        Brevo[Brevo SMTP Transactional Emails]
        Twilio[Twilio SMS Services]
        CalCom[Cal.com Scheduler]
    end

    UI -- Live Status Broadcaster -- Websockets
    APIClient -- HTTP REST Requests -- API
    WebhookRouter -- Call Logs & Timeline -- DB
    WebhookRouter -- Dynamic Emails -- Brevo
    WebhookRouter -- Text Alerts -- Twilio
    WebhookRouter -- Appointment Bookings -- CalCom
    API -- Trigger Call -- Retell
    API -- OCR Screen Extraction -- Gemini
```

---

## 🚀 Key Features

1. **AI Voice Calling (Retell AI)**: Dynamic outbound agent calls with objection-handling loops, compliant hours check by timezone, and mid-call appointment scheduler tool mapping.
2. **Time-Gated Campaign Scheduling**: Restricts campaign runs to specific high-conversion hours (**8:00 PM – 10:00 PM**, **12:00 AM – 1:00 AM**, and **3:00 AM – 4:00 AM IST**). The system places dialers on standby outside these hours and auto-resumes them when the next window opens.
3. **Interactive Call History & Transcripts**: Premium activity logs dashboard allowing date filtering, MP3 call recording playback, and full interactive conversational transcripts mapped to custom side drawers.
4. **AI Screenshot Lead OCR (Gemini 2.5 Flash)**: Upload Google Ads CRM screenshots directly. Gemini parses the details (business name, poc, email, phone, CID) and automatically creates/merges leads.
5. **Niche-Specific Cold Email Outreach**: Automatically renders premium responsive HTML cards based on lead industry niches (such as a custom-tailored **Automotive** outreach layout focusing on local search visibility, map ranking, and mobile performance) with styled booking buttons linked directly to Cal.com calendar scheduling.
6. **Consultative LinkedIn outreach with AI Personalization**: Personalizes long-form consultative intro messages using Gemini 2.5 Flash (dynamically adjusting names, companies, and industries) sent automatically once connection invitations are accepted on LinkedIn.
7. **AI Inbox Reviewer & Periodic Sync**: Scrapes and reviews email and LinkedIn inbox messages, uses Gemini AI models to qualify responses (classifying leads into `booking_requested`, `interested`, `not_interested`), and automatically schedules appointments or records updates.
8. **Multi-Channel Automation**: Confirms meetings, triggers follow-ups, and handles voice message outreach using Brevo (emails), Twilio (SMS), and WhatsApp wa.me click-to-chat links.
9. **Command Center UI**: A dark Navy/Glassmorphic Next.js dashboard featuring timeline logs, audio playback nodes, CSV bulk lead uploading, and live status updates over WebSockets.

---

## 🛠️ Technology Stack

### Backend
- **Core**: FastAPI (Python 3.11+)
- **ORM / Database**: SQLAlchemy, SQLite (with fallback)
- **APIs & SDKs**: Retell API, Google Generative AI (Gemini), Twilio SDK, sib-api-v3-sdk (Brevo)
- **Monitoring & Scheduling**: Structured logging (Structlog), slowapi (rate-limiting), APScheduler (background sync tasks)

### Frontend
- **Framework**: Next.js 14 (App Router), TypeScript
- **Styling**: TailwindCSS, Shadcn UI
- **State/Caching**: React Query (`@tanstack/react-query`)
- **Icons**: Lucide React

---

## 📦 Project Structure

```
reachmagnets-caller/
├── apps/
│   ├── backend/               # FastAPI Application
│   │   ├── app/
│   │   │   ├── core/          # Config, Database, WebSockets, Scheduler
│   │   │   ├── models/        # SQLAlchemy Models (Lead, Call, etc.)
│   │   │   ├── routers/       # REST Routes (Campaigns, Leads, Emails, LinkedIn)
│   │   │   ├── services/      # Service Integrations (Retell, Email, LinkedIn, Gmeet)
│   │   │   └── utils/         # Automations, timezone compliance
│   │   ├── db/                # Initial SQL schemas
│   │   ├── requirements.txt   # Backend Dependencies
│   │   └── .env.example       # Backend Environment configuration
│   └── frontend/              # Next.js 14 Application
│       ├── src/
│       │   ├── app/           # Pages (Leads, Campaigns, Appointments)
│       │   ├── components/    # Common UI & Layouts
│       │   └── lib/           # Axios API wrapper with caching
│       ├── package.json       # Frontend Dependencies
│       └── .env.example       # Frontend Environment configuration
├── docker-compose.yml         # Container Orchestration
└── retell_agent_prompt.md     # Retell Agent configuration prompts
```

---

## ⚙️ Quick Start Setup

### Setup Configurations
1. Copy the backend environment variables template and customize:
   ```bash
   cp apps/backend/.env.example apps/backend/.env
   ```
2. Set your API credentials in `apps/backend/.env`:
   - `RETELL_API_KEY` & `RETELL_AGENT_ID`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER`
   - `BREVO_API_KEY`, `SENDER_EMAIL`, and `SENDER_NAME`
   - `GEMINI_API_KEY`
   - `CALCOM_API_KEY` and `CALCOM_EVENT_TYPE_ID`

### Running the Complete Stack (FastAPI + Next.js + Cloudflare Tunnels)
To easily run the frontend and backend servers together with dynamic Cloudflare tunnels:
1. Make sure you have python-dependencies installed in the backend virtualenv.
2. Run the master startup script:
   ```bash
   python apps/backend/scratch/run_and_tunnel.py
   ```
*This script will:*
- Launch a Cloudflare tunnel for the FastAPI backend (`http://localhost:8000`).
- Parse the dynamic Cloudflare URL and write it to `BASE_URL` in `apps/backend/.env`.
- Boot the backend uvicorn server (which dynamically registers the tunnel webhook URL with Retell).
- Configure the frontend's API variables in `apps/frontend/.env.local`.
- Start the Next.js development server on port `3001` and expose it via a second Cloudflare tunnel.
- Output the public dashboard URL!

---

## 📡 Key API Routes Map

### Leads
- `GET /api/v1/leads/` - Paginated lists with query filtering
- `POST /api/v1/leads/import` - CSV lead uploading (enforces DNC list filter and duplicate checks)
- `POST /api/v1/leads/extract-screenshots` - Gemini screenshot parsing and detail merge
- `GET /api/v1/leads/{id}` - Comprehensive lead profile activity timeline

### Campaigns
- `GET /api/v1/campaigns/` - List campaigns with aggregated counts
- `POST /api/v1/campaigns/{id}/start` - Launch background dialer queue
- `POST /api/v1/campaigns/{id}/pause` - Pause dialing outreach

### Emails & LinkedIn Sync
- `POST /api/v1/emails/sync-inbox` - Trigger secure email IMAP mailbox synchronization and qualify replies
- `POST /api/v1/linkedin/sync-inbox` - Check LinkedIn thread message replies and auto-schedule meetings

### Webhooks
- `POST /api/retell/webhook` - Standard Retell webhook tracking call states and analysis outcomes
- `POST /api/retell/book-appointment` - Mid-call AI slot scheduling hook

---

## 🔒 Security & Compliance
- **DNC Filtering**: All imported CSV lists are checked against the Do-Not-Call registry helper.
- **Campaign Windows Compliance**: Automatically enforces strict Indian Standard Time (IST) calling hour gates to run campaigns only during configured slots.
- **Timezone Safety**: Outbound calls verify lead-level local timezone dialing windows (8:00 AM – 9:00 PM local time) to prevent early/late night calls.
- **Rate Limiting**: Built-in limit safety guards (1.5-second call intervals) protect API routing from abuse and respect Retell limits.

