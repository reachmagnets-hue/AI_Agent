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
2. **AI Screenshot Lead OCR (Gemini 2.5 Flash)**: Upload Google Ads CRM screenshots directly. Gemini parses the details (business name, poc, email, phone, CID) and automatically creates/merges leads.
3. **Multi-Channel Automation**: Confirms meetings, triggers follow-ups, and handles voice message outreach using Brevo (emails), Twilio (SMS), and WhatsApp wa.me click-to-chat links.
4. **Command Center UI**: A dark Navy/Glassmorphic Next.js dashboard featuring timeline logs, audio playback nodes, CSV bulk lead uploading, and live status updates over WebSockets.

---

## 🛠️ Technology Stack

### Backend
- **Core**: FastAPI (Python 3.11+)
- **ORM / Database**: SQLAlchemy, SQLite (with fallback)
- **APIs & SDKs**: Retell API, Google Generative AI (Gemini), Twilio SDK, sib-api-v3-sdk (Brevo)
- **Monitoring**: Structured logging (Structlog), slowapi (rate-limiting)

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
│   │   │   ├── core/          # Config, Database, WebSockets
│   │   │   ├── models/        # SQLAlchemy Models (Lead, Call, etc.)
│   │   │   ├── routers/       # REST Routes (Campaigns, Leads, Webhooks)
│   │   │   ├── services/      # Service Integrations (Retell, Email, SMS)
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

### 1. Backend Configuration
1. Navigate to the backend directory:
   ```bash
   cd apps/backend
   ```
2. Copy the environment variables template and customize:
   ```bash
   cp .env.example .env
   ```
3. Set your API credentials:
   - `RETELL_API_KEY` & `RETELL_AGENT_ID`
   - `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, and `TWILIO_PHONE_NUMBER`
   - `BREVO_API_KEY`, `SENDER_EMAIL`, and `SENDER_NAME`
   - `GEMINI_API_KEY`
   - `CALCOM_API_KEY` and `CALCOM_EVENT_TYPE_ID`
4. Run the development server:
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

### 2. Frontend Configuration
1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```
2. Set up environment variables:
   ```bash
   cp .env.example .env.local
   ```
3. Start the Next.js development server:
   ```bash
   npm install
   npm run dev
   ```

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

### Webhooks
- `POST /api/retell/webhook` - Standard Retell webhook tracking call states and analysis outcomes
- `POST /api/retell/book-appointment` - Mid-call AI slot scheduling hook

---

## 🔒 Security & Compliance
- **DNC Filtering**: All imported CSV lists are checked against the Do-Not-Call registry helper.
- **Timezone Safety**: Outbound calls verify timezone dialing window compliancy rules before calling.
- **Rate Limiting**: Built-in limit safety guards protect API routing from abuse.
