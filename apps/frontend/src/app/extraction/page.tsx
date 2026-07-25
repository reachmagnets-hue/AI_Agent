'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  MapPin, Search, Sparkles, AlertCircle, CheckCircle, HelpCircle, Loader2, Play, 
  Download, Building2, Phone, Globe, Mail, Linkedin, Send, RefreshCw, Layers, Users, Zap
} from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API_BASE_URL } from '@/lib/api';

interface ExtractedLead {
  name: string;
  phone: string | null;
  website: string | null;
  address: string | null;
  email: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  linkedin_url?: string | null;
  twitter_url?: string | null;
  youtube_url?: string | null;
  rating?: string | null;
  description?: string | null;
  internal_notes?: string | null;
  is_duplicate?: boolean;
}

interface Campaign {
  id: string;
  name: string;
  status: string;
}

interface LinkedInStats {
  total: number;
  scraped: number;
  pending_generation: number;
  ready_to_send: number;
  sent: number;
}

export default function UnifiedLeadSourcingPage() {
  const queryClient = useQueryClient();

  // Shared Master Parameters
  const [industry, setIndustry] = useState<string>('automotive');
  const [location, setLocation] = useState<string>('');
  const [limit, setLimit] = useState<number>(10);
  
  // Navigation Tabs inside Page
  const [activeView, setActiveView] = useState<'gmaps' | 'linkedin' | 'combined'>('gmaps');

  // Google Maps Scraper States
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [extractedLeads, setExtractedLeads] = useState<ExtractedLead[]>([]);
  const [progressText, setProgressText] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' | null }>({ text: '', type: null });

  // LinkedIn Automation States
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
  const [dailyLimit, setDailyLimit] = useState<number>(100);
  const [simulate, setSimulate] = useState<boolean>(true);
  const [autopilotLog, setAutopilotLog] = useState<string>('');
  const [autopilotStage, setAutopilotStage] = useState<string>('');
  const [isAutopilotRunning, setIsAutopilotRunning] = useState<boolean>(false);

  const leadsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll list as new leads are added
  useEffect(() => {
    if (extractedLeads.length > 0) {
      leadsEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [extractedLeads]);

  // Load LinkedIn Campaigns
  const { data: campaigns } = useQuery<Campaign[]>({
    queryKey: ['linkedin-campaigns-list'],
    queryFn: async () => {
      const response = await fetch('/api/v1/campaigns/');
      if (!response.ok) throw new Error('Failed to fetch campaigns');
      return response.json();
    }
  });

  // Load stats for selected campaign
  const { data: stats, refetch: refetchStats } = useQuery<LinkedInStats>({
    queryKey: ['linkedin-campaign-stats', selectedCampaignId],
    queryFn: async () => {
      if (!selectedCampaignId) return { total: 0, scraped: 0, pending_generation: 0, ready_to_send: 0, sent: 0 };
      const response = await fetch(`/api/v1/linkedin/stats?campaign_id=${selectedCampaignId}`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      return response.json();
    },
    enabled: !!selectedCampaignId,
    refetchInterval: 10000
  });

  // Automatically select the first campaign if none selected
  useEffect(() => {
    if (campaigns && campaigns.length > 0 && !selectedCampaignId) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaigns, selectedCampaignId]);

  // WebSocket Listener for both Google Maps & LinkedIn Autopilot progress
  useEffect(() => {
    const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsUrl = rawApiUrl.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/live';
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Google Maps Events
        if (data.event === 'extraction_started') {
          setIsExtracting(true);
          setExtractedLeads([]);
          setProgressText(`[Google Maps] Launching search for "${data.industry}" in "${data.location}" (Target: ${data.limit} shops)...`);
          setStatusMessage({ text: 'Google Maps extraction started in background.', type: 'info' });
        }
        else if (data.event === 'extraction_progress') {
          const lead = data.lead as ExtractedLead;
          setExtractedLeads(prev => {
            const index = prev.findIndex(item => item.name === lead.name);
            if (index !== -1) {
              const updated = [...prev];
              updated[index] = { ...updated[index], ...lead };
              return updated;
            }
            return [...prev, lead];
          });
          if (lead.is_duplicate) {
            setProgressText(`[In DB] ${lead.name}`);
          } else {
            setProgressText(`[Google Maps #${data.current}/${data.total}] Extracted ${lead.name}`);
          }
        }
        else if (data.event === 'extraction_completed') {
          setIsExtracting(false);
          setProgressText('[Google Maps] Extraction complete! All leads saved to DB.');
          setStatusMessage({
            text: `Success! Local leads with social details saved under campaign: "Extracted - ${data.industry.toUpperCase()} in ${data.location.toUpperCase()}"`,
            type: 'success'
          });
        }
        else if (data.event === 'extraction_failed') {
          setIsExtracting(false);
          setProgressText('[Google Maps] Scraping failed.');
          setStatusMessage({ text: `Google Maps error: ${data.error || 'Process failed'}`, type: 'error' });
        }

        // LinkedIn Autopilot Events
        if (data.event === 'autopilot_status') {
          setAutopilotLog(data.message);
          setAutopilotStage(data.stage);
          if (data.stage === 'completed') {
            setIsAutopilotRunning(false);
            setStatusMessage({ text: 'LinkedIn Autopilot cycle completed successfully!', type: 'success' });
          }
          refetchStats();
        }
      } catch (e) {
        console.error('Error parsing live WebSocket message:', e);
      }
    };
    
    return () => {
      ws.close();
    };
  }, [refetchStats]);

  // Google Maps Extraction Trigger
  const handleStartExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!industry.trim() || !location.trim()) {
      setStatusMessage({ text: 'Please specify both Industry Instruction and Location.', type: 'error' });
      return;
    }
    
    setIsExtracting(true);
    setStatusMessage({ text: 'Initiating Google Maps scraper on server...', type: 'info' });
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/extraction/scrape`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ industry, location, limit })
      });
      
      if (!response.ok) throw new Error('Failed to start scraper task');
    } catch (err: any) {
      setIsExtracting(false);
      setStatusMessage({ text: err.message || 'Connection error starting extraction', type: 'error' });
    }
  };

  // LinkedIn Autopilot Trigger
  const handleStartLinkedInAutopilot = async () => {
    if (!industry.trim()) {
      setStatusMessage({ text: 'Please enter an Industry / Category instruction.', type: 'error' });
      return;
    }

    setIsAutopilotRunning(true);
    setStatusMessage({ text: 'Initializing LinkedIn Autopilot Pipeline...', type: 'info' });

    try {
      const params = new URLSearchParams({
        industry,
        limit: limit.toString()
      });
      if (location) params.append('location', location);
      
      const response = await fetch(`/api/v1/linkedin/autopilot?${params.toString()}`, {
        method: 'POST'
      });

      if (!response.ok) throw new Error('LinkedIn Autopilot launch failed');

      const data = await response.json();
      setStatusMessage({
        text: `LinkedIn Autopilot Launched! Created campaign: "${data.campaign_name}".`,
        type: 'success'
      });
      setSelectedCampaignId(data.campaign_id);
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaigns-list'] });
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaign-stats', data.campaign_id] });
    } catch (err: any) {
      setIsAutopilotRunning(false);
      setStatusMessage({ text: `Failed to start LinkedIn Autopilot: ${err.message}`, type: 'error' });
    }
  };

  // LinkedIn Gemini AI Message Generation Trigger
  const handleGenerateLinkedInMessages = async () => {
    if (!selectedCampaignId) return;
    setStatusMessage({ text: 'Triggering Gemini AI message drafting...', type: 'info' });

    try {
      const response = await fetch(`/api/v1/linkedin/generate-messages?campaign_id=${selectedCampaignId}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('AI drafting failed');
      setStatusMessage({ text: 'Gemini AI has started drafting connection messages in the background.', type: 'success' });
      refetchStats();
    } catch (err: any) {
      setStatusMessage({ text: `Error generating AI messages: ${err.message}`, type: 'error' });
    }
  };

  // LinkedIn Connection Request Dispatcher
  const handleStartLinkedInOutreach = async () => {
    if (!selectedCampaignId) return;
    setStatusMessage({ text: 'Launching LinkedIn connection dispatcher...', type: 'info' });

    try {
      const response = await fetch(`/api/v1/linkedin/start-campaign?campaign_id=${selectedCampaignId}&limit=${dailyLimit}&simulate=${simulate}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Failed to launch connection dispatcher');
      const data = await response.json();
      setStatusMessage({ text: `Connection Outreach Active: ${data.message}`, type: 'success' });
      refetchStats();
    } catch (err: any) {
      setStatusMessage({ text: `Outreach failure: ${err.message}`, type: 'error' });
    }
  };

  return (
    <div className="space-y-8 max-w-7xl mx-auto p-4 sm:p-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/50 backdrop-blur-md p-6 rounded-2xl border border-white/60 shadow-sm">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-3">
            Lead Sourcing & LinkedIn Automation <Zap className="h-8 w-8 text-indigo-600 animate-pulse" />
          </h1>
          <p className="text-muted-foreground mt-1 text-sm font-medium">
            Unified Lead Prospecting & Autonomous Outreach Engine. Extract local business listings, email contacts, and target decision-makers on LinkedIn with automated AI message drafting.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-3 py-1.5 bg-indigo-500/10 text-indigo-600 rounded-full text-xs font-bold uppercase tracking-wider border border-indigo-500/20 flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5" /> Full Automation Hub
          </span>
        </div>
      </div>

      {/* Alert Banners */}
      {statusMessage.text && (
        <div className={`p-4 rounded-xl border flex items-start gap-3 animate-in fade-in duration-300 ${
          statusMessage.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
          statusMessage.type === 'error' ? 'bg-rose-50 text-rose-800 border-rose-200' :
          'bg-indigo-50 text-indigo-800 border-indigo-200'
        }`}>
          {statusMessage.type === 'success' ? <CheckCircle className="h-5 w-5 shrink-0 mt-0.5 text-emerald-600" /> :
           statusMessage.type === 'error' ? <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-rose-600" /> :
           <Sparkles className="h-5 w-5 shrink-0 mt-0.5 text-indigo-600 animate-spin" />}
          <div className="text-sm font-semibold">{statusMessage.text}</div>
          <button onClick={() => setStatusMessage({ text: '', type: null })} className="ml-auto text-xs font-bold hover:underline shrink-0">Dismiss</button>
        </div>
      )}

      {/* Master Targeting & Parameter Form */}
      <Card className="glass-card shadow-md border border-slate-200/80">
        <CardHeader className="border-b border-slate-100 pb-4">
          <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
            <Search className="h-5 w-5 text-indigo-600" /> Master Target Instruction & Industry Filters
          </CardTitle>
          <CardDescription className="text-xs">
            Enter your target Industry / Niche instruction and location. This powers both Google Maps business extraction and LinkedIn decision-maker prospecting.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-6">
          <form onSubmit={handleStartExtraction} className="grid grid-cols-1 md:grid-cols-4 gap-4 items-end">
            <div className="space-y-1.5 md:col-span-1">
              <label className="text-xs font-bold text-slate-700">Industry / Niche Instruction</label>
              <Input
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                placeholder="e.g. Automotive, Roofers, Dentists, IT Founder"
                required
                className="bg-white/90 border-slate-200"
              />
            </div>

            <div className="space-y-1.5 md:col-span-1">
              <label className="text-xs font-bold text-slate-700">Location / City / Metro</label>
              <Input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="e.g. Dallas TX, Chicago, London"
                required
                className="bg-white/90 border-slate-200"
              />
            </div>

            <div className="space-y-1.5 md:col-span-1">
              <label className="text-xs font-bold text-slate-700">Max Extraction Limit</label>
              <Input
                type="number"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                required
                min={1}
                max={500}
                className="bg-white/90 border-slate-200"
              />
            </div>

            <div className="flex gap-2 md:col-span-1">
              <Button
                type="submit"
                disabled={isExtracting}
                className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm"
              >
                {isExtracting ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapPin className="h-4 w-4" />}
                <span>Scrape G-Maps</span>
              </Button>

              <Button
                type="button"
                onClick={handleStartLinkedInAutopilot}
                disabled={isAutopilotRunning}
                className="flex-1 bg-gradient-to-r from-sky-600 to-blue-700 hover:from-sky-700 hover:to-blue-800 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm"
              >
                {isAutopilotRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Linkedin className="h-4 w-4" />}
                <span>LinkedIn Autopilot</span>
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Main Mode Navigation Tabs */}
      <div className="flex border-b border-slate-200 gap-2">
        <button
          onClick={() => setActiveView('gmaps')}
          className={`px-4 py-2.5 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${
            activeView === 'gmaps'
              ? 'border-indigo-600 text-indigo-600 bg-indigo-50/50 rounded-t-lg'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <MapPin className="h-4 w-4" /> Google Maps Live Listings ({extractedLeads.length})
        </button>

        <button
          onClick={() => setActiveView('linkedin')}
          className={`px-4 py-2.5 text-sm font-bold border-b-2 transition-colors flex items-center gap-2 ${
            activeView === 'linkedin'
              ? 'border-sky-600 text-sky-600 bg-sky-50/50 rounded-t-lg'
              : 'border-transparent text-slate-500 hover:text-slate-800'
          }`}
        >
          <Linkedin className="h-4 w-4" /> LinkedIn Campaign & AI Outreach
        </button>
      </div>

      {/* VIEW 1: Google Maps Live Extracted Stream */}
      {activeView === 'gmaps' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-1 space-y-6">
            <Card className="glass-card border border-slate-200/60">
              <CardHeader className="pb-3 border-b border-slate-100">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">Live Scraper Output Console</CardTitle>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="text-xs text-slate-200 font-mono bg-slate-900 p-4 rounded-xl shadow-inner min-h-[140px] leading-relaxed break-all">
                  {progressText || 'Ready to scrape. Enter Industry and Location above and click "Scrape G-Maps".'}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="lg:col-span-2">
            <Card className="glass-card shadow-md border border-slate-200/60 flex flex-col h-[600px] overflow-hidden">
              <CardHeader className="border-b border-slate-100 bg-slate-50/50 pb-4">
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="text-lg font-bold text-slate-800">Extracted Businesses & Contact Data</CardTitle>
                    <CardDescription className="text-xs">Extracted emails, website domains, ratings, and directory profiles</CardDescription>
                  </div>
                  <span className="px-2.5 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold">
                    {extractedLeads.length} items
                  </span>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-6 space-y-4">
                {extractedLeads.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 text-slate-400">
                    <Building2 className="h-16 w-16 mb-4 text-slate-300" />
                    <p className="text-sm font-semibold">No shops extracted yet</p>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm">
                      Specify industry instruction and location to launch the automated Google Maps crawler.
                    </p>
                  </div>
                ) : (
                  extractedLeads.map((lead, idx) => (
                    <div 
                      key={idx} 
                      className="p-4 rounded-xl border border-slate-200/60 bg-white/70 shadow-sm flex flex-col gap-2 hover:border-indigo-300 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="space-y-0.5">
                          <h4 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                            <Building2 className="h-4 w-4 text-indigo-600" /> {lead.name}
                          </h4>
                          {lead.rating && (
                            <div className="text-[11px] text-amber-700 font-semibold flex items-center gap-1">
                              <span>⭐ {lead.rating}</span>
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {lead.is_duplicate && (
                            <span className="px-2 py-0.5 bg-amber-100 text-amber-800 rounded-full text-[10px] font-bold">
                              In DB
                            </span>
                          )}
                          {lead.email ? (
                            <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-bold flex items-center gap-1">
                              <Mail className="h-3 w-3" /> Email Found
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[10px] font-medium">
                              No Email
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-600 pt-1">
                        {lead.phone && (
                          <div className="flex items-center gap-1.5">
                            <Phone className="h-3.5 w-3.5 text-slate-400" />
                            <span>{lead.phone}</span>
                          </div>
                        )}
                        {lead.website && (
                          <div className="flex items-center gap-1.5 break-all">
                            <Globe className="h-3.5 w-3.5 text-slate-400" />
                            <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-indigo-600 hover:underline font-medium">
                              {lead.website}
                            </a>
                          </div>
                        )}
                      </div>

                      {lead.address && (
                        <div className="text-xs text-slate-500 border-t border-slate-100 pt-2 flex items-start gap-1">
                          <MapPin className="h-3.5 w-3.5 text-slate-400 mt-0.5 shrink-0" />
                          <span className="italic">{lead.address}</span>
                        </div>
                      )}

                      {lead.email && (
                        <div className="text-xs text-emerald-800 bg-emerald-500/5 border border-emerald-500/10 p-2 rounded-lg flex items-center gap-1.5">
                          <Mail className="h-3.5 w-3.5 text-emerald-600" />
                          <span className="font-semibold font-mono">{lead.email}</span>
                        </div>
                      )}
                    </div>
                  ))
                )}
                <div ref={leadsEndRef} />
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {/* VIEW 2: LinkedIn Campaign & AI Outreach Controls */}
      {activeView === 'linkedin' && (
        <div className="space-y-6">
          {/* Campaign Selector & Metric Badges */}
          <Card className="glass-card shadow-md border border-slate-200/80">
            <CardHeader className="pb-4 border-b border-slate-100">
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div>
                  <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Linkedin className="h-5 w-5 text-sky-600" /> LinkedIn Outreach Campaign Controls
                  </CardTitle>
                  <CardDescription className="text-xs">Manage active campaigns, generate AI connection notes, and dispatch connection requests.</CardDescription>
                </div>

                <div className="w-full sm:w-64">
                  <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
                    <SelectTrigger className="bg-white border-slate-200 text-xs font-bold">
                      <SelectValue placeholder="Select a Campaign" />
                    </SelectTrigger>
                    <SelectContent>
                      {campaigns?.map((c) => (
                        <SelectItem key={c.id} value={c.id} className="text-xs">
                          {c.name} ({c.status})
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
                <div className="p-4 bg-slate-50 rounded-xl border border-slate-200/60 text-center">
                  <div className="text-2xl font-black text-slate-800">{stats?.total || 0}</div>
                  <div className="text-[11px] font-bold text-slate-500 uppercase mt-1">Total Leads</div>
                </div>

                <div className="p-4 bg-sky-50 rounded-xl border border-sky-200/60 text-center">
                  <div className="text-2xl font-black text-sky-800">{stats?.scraped || 0}</div>
                  <div className="text-[11px] font-bold text-sky-600 uppercase mt-1">Profiles Scraped</div>
                </div>

                <div className="p-4 bg-purple-50 rounded-xl border border-purple-200/60 text-center">
                  <div className="text-2xl font-black text-purple-800">{stats?.pending_generation || 0}</div>
                  <div className="text-[11px] font-bold text-purple-600 uppercase mt-1">Pending AI Draft</div>
                </div>

                <div className="p-4 bg-emerald-50 rounded-xl border border-emerald-200/60 text-center">
                  <div className="text-2xl font-black text-emerald-800">{stats?.ready_to_send || 0}</div>
                  <div className="text-[11px] font-bold text-emerald-600 uppercase mt-1">Ready to Send</div>
                </div>

                <div className="p-4 bg-blue-50 rounded-xl border border-blue-200/60 text-center col-span-2 sm:col-span-1">
                  <div className="text-2xl font-black text-blue-800">{stats?.sent || 0}</div>
                  <div className="text-[11px] font-bold text-blue-600 uppercase mt-1">Connections Sent</div>
                </div>
              </div>

              {/* Action Buttons Row */}
              <div className="flex flex-wrap gap-3 mt-6 pt-4 border-t border-slate-100">
                <Button
                  onClick={handleGenerateLinkedInMessages}
                  className="bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs h-9 flex items-center gap-1.5"
                >
                  <Sparkles className="h-4 w-4" /> Draft AI Messages (Gemini)
                </Button>

                <Button
                  onClick={handleStartLinkedInOutreach}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs h-9 flex items-center gap-1.5"
                >
                  <Send className="h-4 w-4" /> Start Connection Outreach
                </Button>

                <Button
                  onClick={() => refetchStats()}
                  variant="outline"
                  className="text-xs font-bold h-9 flex items-center gap-1.5 ml-auto"
                >
                  <RefreshCw className="h-3.5 w-3.5" /> Refresh Metrics
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Autopilot Real-time Console */}
          <Card className="glass-card border border-slate-200/60">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">LinkedIn Autopilot Execution Log</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="text-xs text-sky-300 font-mono bg-slate-900 p-4 rounded-xl shadow-inner min-h-[120px] leading-relaxed break-all">
                {autopilotLog || 'No active autopilot run. Select a campaign or click "LinkedIn Autopilot" above.'}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
