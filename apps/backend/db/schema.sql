-- Create custom types for ENUMs
CREATE TYPE contact_status AS ENUM ('pending', 'called', 'failed', 'interested', 'not_interested');
CREATE TYPE campaign_status AS ENUM ('draft', 'running', 'paused', 'completed');
CREATE TYPE call_status AS ENUM ('initiated', 'ringing', 'answered', 'completed', 'failed', 'no_answer');

-- Create contacts table
CREATE TABLE contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number VARCHAR NOT NULL,
    name VARCHAR,
    company VARCHAR,
    status contact_status DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create campaigns table
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR NOT NULL,
    total_contacts INT DEFAULT 0,
    calls_made INT DEFAULT 0,
    calls_answered INT DEFAULT 0,
    status campaign_status DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create call_logs table
CREATE TABLE call_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    vapi_call_id VARCHAR UNIQUE,
    duration_seconds INT,
    status call_status DEFAULT 'initiated',
    transcript TEXT,
    recording_url VARCHAR,
    started_at TIMESTAMP WITH TIME ZONE,
    ended_at TIMESTAMP WITH TIME ZONE
);

-- Create campaign_contacts join table
CREATE TABLE campaign_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES contacts(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(campaign_id, contact_id)
);

-- Create indexes
CREATE INDEX idx_contacts_phone_number ON contacts(phone_number);
CREATE INDEX idx_contacts_status ON contacts(status);
CREATE INDEX idx_call_logs_campaign_id ON call_logs(campaign_id);
CREATE INDEX idx_call_logs_status ON call_logs(status);
CREATE INDEX idx_campaigns_status ON campaigns(status);
CREATE INDEX idx_campaign_contacts_campaign_id ON campaign_contacts(campaign_id);
CREATE INDEX idx_campaign_contacts_contact_id ON campaign_contacts(contact_id);
