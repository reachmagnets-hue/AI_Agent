# Reach Magnets Frontend

A modern Next.js 14 dashboard for the Reach Magnets AI Voice Calling Agent.

## Features

- **Dark Theme**: Beautiful dark UI with shadcn/ui components
- **Responsive Design**: Fully responsive across desktop, tablet, and mobile
- **Real-time Data**: React Query for efficient data fetching and caching
- **Dashboard**: Overview with key metrics for contacts, campaigns, and calls
- **Contacts Management**: Import contacts via CSV, view, search, and manage
- **Campaigns**: Create, monitor, and manage AI voice calling campaigns
- **Call Logs**: Detailed call transcripts and analytics
- **Modern Stack**: Next.js 14, TypeScript, Tailwind CSS

## Tech Stack

- **Framework**: Next.js 14
- **Language**: TypeScript
- **Styling**: Tailwind CSS with dark theme
- **UI Components**: shadcn/ui
- **State Management**: React Query (TanStack Query)
- **Icons**: Lucide React
- **File Upload**: CSV import with parsing
- **API**: FastAPI backend integration

## Installation

1. Install dependencies:
```bash
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000) in your browser

## Environment Variables

Create a `.env.local` file:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

## Pages

- **Dashboard** (`/`) - Overview with statistics and metrics
- **Contacts** (`/contacts`) - Manage contact lists and CSV imports
- **Campaigns** (`/campaigns`) - Create and monitor AI calling campaigns
- **Call Logs** (`/calls`) - Detailed call records and transcripts

## Features

### Dashboard Features
- Real-time statistics
- Campaign performance metrics
- Contact and call activity tracking
- Success rate analytics

### Contacts Features
- CSV contact import functionality
- Search and filter capabilities
- Contact status management
- Tagging system for organization

### Campaigns Features
- Campaign creation and management
- Status tracking (active, paused, completed)
- Real-time campaign metrics
- Performance analytics

### Call Logs Features
- Detailed call transcripts
- Call duration and cost tracking
- Success/failure analysis
- Message-level detail view

## API Integration

All API requests are handled through React Query hooks that:
- Cache responses for better performance
- Automatically refetch data when needed
- Handle loading and error states
- Support real-time updates

## Responsive Design

The application is fully responsive with:
- Mobile-first approach
- Adaptive layouts for tablets
- Desktop-optimized experience
- Touch-friendly interfaces
- Collapsible mobile navigation

## Deployment

The application is ready for deployment with:
- Optimized build configuration
- Static generation support
- Environment variable support
- API proxy configuration for development

## Development

```bash
# Development server
npm run dev

# Build for production
npm run build

# Start production server
npm run start

# Lint code
npm run lint
```

## Project Structure

```
src/
├── components/
│   ├── ui/           # shadcn/ui components
│   └── layout/       # Navigation and layout components
├── app/
│   ├── globals.css   # Global styles and theme
│   ├── layout.tsx    # Root layout with navigation
│   ├── page.tsx      # Dashboard page
│   ├── contacts/
│   ├── campaigns/
│   └── calls/
├── lib/
│   └── utils.ts      # Utility functions
└── components.json   # shadcn/ui configuration
