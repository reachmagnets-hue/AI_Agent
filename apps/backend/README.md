# Reach Magnets AI Voice Calling Agent - Backend

## Overview
This is the backend service for the Reach Magnets AI Voice Calling Agent system. It provides a complete API for managing contacts, campaigns, and call logs with integration to Vapi.ai for AI-powered voice calling.

## Features
- **Contact Management**: CRUD operations for contact data with CSV import/export
- **Campaign Orchestration**: Create, start, pause, and monitor outbound calling campaigns  
- **Real-time Integration**: Webhook handlers for Vapi.ai events
- **Comprehensive Analytics**: Detailed call logs, statistics, and performance metrics
- **CSV Export**: Export contacts and call logs as CSV files
- **Supabase Integration**: Uses PostgreSQL via Supabase for data persistence

## Quick Start

### Prerequisites
- Python 3.11+
- Supabase account and database
- Vapi.ai API key
- pip (Python package manager)

### Setup

1. **Install dependencies:**
   ```bash
   cd reachmagnets-caller/apps/backend
   pip install -r requirements.txt
   ```

2. **Environment variables:**
   Copy `.env.example` to `.env` and configure:
   ```bash
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   VAPI_API_KEY=your_vapi_api_key
   TWILIO_PHONE_NUMBER=your_twilio_number
   FRONTEND_URL=http://localhost:3000
   ```

3. **Run the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

4. **Verify setup:**
   ```bash
   curl http://localhost:8000/health
   ```

### Docker Setup
```bash
docker build -t reach-magnets-backend .
docker run -p 8000:8000 \
  -e SUPABASE_URL=your_url \
  -e SUPABASE_KEY=your_key \
  -e VAPI_API_KEY=your_key \
  reach-magnets-backend
```

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive Swagger documentation.

### Key Endpoints

#### Contacts
- `POST /contacts` - Create contact
- `POST /contacts/bulk` - Import contacts bulk from CSV
- `GET /contacts` - List contacts with pagination
- `GET /contacts/export/csv` - Export contacts as CSV

#### Campaigns
- `POST /campaigns` - Create new campaign
- `POST /campaigns/{id}/start` - Start calling campaign
- `GET /campaigns/{id}/stats` - Get campaign statistics
- `POST /campaigns/{id}/pause` - Pause campaign

#### Calls
- `GET /calls` - List all calls with filters
- `GET /calls/dashboard/stats` - Dashboard statistics
- `GET /calls/export/csv` - Export call logs

#### Webhooks
- `POST /webhooks/vapi` - Vapi webhook handler

## Database Schema

The system uses three main tables:

- **contacts** - Phone contact information
- **campaigns** - Calling campaigns - call_logs** - Detailed call records

## Development

### Running Unit Tests
To be implemented as part of the testing phase.

### Contributing
1. Create feature branch
2. Test changes thoroughly
3. Ensure webhook handling is robust
4. Update documentation

### Security
- All API endpoints validate input data
- SQL injection prevention via Supabase
- Environment variables for secrets
- Webhook signature verification recommended for production