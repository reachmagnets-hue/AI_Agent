'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { 
  MapPin, Search, Sparkles, AlertCircle, CheckCircle, HelpCircle, Loader2, Play, 
  Download, Building2, Phone, Globe, Mail, Linkedin, Send, RefreshCw, Layers, Users, Zap, AlertTriangle
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
  directories?: Record<string, string>;
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

  // SECTION 1: Google Maps Scraper Form States
  const [gmapsIndustry, setGmapsIndustry] = useState<string>('Auto Body Shop');
  const [gmapsLocation, setGmapsLocation] = useState<string>('USA');
  const [gmapsLimit, setGmapsLimit] = useState<string>('50');
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [extractedLeads, setExtractedLeads] = useState<ExtractedLead[]>([]);
  const [gmapsProgressText, setGmapsProgressText] = useState<string>('');

  // SECTION 2: LinkedIn Prospecting Form States
  const [linkedinIndustry, setLinkedinIndustry] = useState<string>('Auto Body Shop');
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
  const [isAutopilotRunning, setIsAutopilotRunning] = useState<boolean>(false);
  const [isSendingTestConnection, setIsSendingTestConnection] = useState<boolean>(false);
  const [autopilotLog, setAutopilotLog] = useState<string>('');
  const [autopilotStage, setAutopilotStage] = useState<string>('');
  const [zeroLeadsWarning, setZeroLeadsWarning] = useState<string | null>(null);

  // Global Status Messages
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' | null }>({ text: '', type: null });

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
    refetchInterval: 8000
  });

  // Automatically select the first campaign if none selected
  useEffect(() => {
    if (campaigns && campaigns.length > 0 && !selectedCampaignId) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaigns, selectedCampaignId]);

  // WebSocket Listener for both Google Maps & LinkedIn Autopilot progress
  useEffect(() => {
    let wsUrl = '';
    if (typeof window !== 'undefined') {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.host;
      if (host.includes(':3000')) {
        wsUrl = `${protocol}//${window.location.hostname}:8000/ws/live`;
      } else {
        wsUrl = `${protocol}//${host}/ws/live`;
      }
    } else {
      wsUrl = 'ws://localhost:8000/ws/live';
    }
    
    let ws: WebSocket;
    try {
      ws = new WebSocket(wsUrl);
    } catch (err) {
      console.error('Failed to create WebSocket connection:', err);
      return;
    }
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        // Google Maps Events
        if (data.event === 'extraction_started') {
          setIsExtracting(true);
          setExtractedLeads([]);
          setGmapsProgressText(`[Google Maps] Scraping industry "${data.industry}" across target locations...`);
          setStatusMessage({ text: 'Google Maps extraction launched in background.', type: 'info' });
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
            setGmapsProgressText(`[In DB] ${lead.name}`);
          } else {
            setGmapsProgressText(`[Extracted #${data.current}/${data.total}] ${lead.name}`);
          }
        }
        else if (data.event === 'extraction_completed') {
          setIsExtracting(false);
          setGmapsProgressText('[Google Maps] Extraction complete! All leads saved to DB.');
          setStatusMessage({
            text: `Success! Local leads with social details saved in database.`,
            type: 'success'
          });
          queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
          queryClient.invalidateQueries({ queryKey: ['extracted-leads'] });
        }
        else if (data.event === 'extraction_failed') {
          setIsExtracting(false);
          setGmapsProgressText('[Google Maps] Scraping failed.');
          setStatusMessage({ text: `Google Maps error: ${data.error || 'Process failed'}`, type: 'error' });
        }

        // LinkedIn Autopilot Events
        if (data.event === 'autopilot_status') {
          setAutopilotLog(data.message);
          setAutopilotStage(data.stage);
          
          if (data.stage === 'zero_leads') {
            setIsAutopilotRunning(false);
            setZeroLeadsWarning(`0 leads found for Industry instruction '${linkedinIndustry}'. Please update your Industry keyword to find new leads.`);
            setStatusMessage({ text: `No leads found for Industry '${linkedinIndustry}'. Please update Industry instruction.`, type: 'error' });
          } else if (data.stage === 'completed') {
            setIsAutopilotRunning(false);
            setZeroLeadsWarning(null);
            setStatusMessage({ text: 'LinkedIn Autopilot outreach cycle completed successfully!', type: 'success' });
          }
          refetchStats();
          queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
        }

        if (data.event === 'lead_status_updated') {
          refetchStats();
          queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
        }
      } catch (e) {
        console.error('Error parsing live WebSocket message:', e);
      }
    };
    
    return () => {
      ws.close();
    };
  }, [linkedinIndustry, refetchStats, queryClient]);

  // Handle Google Maps Extraction Trigger
  const handleStartGmapsExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gmapsIndustry.trim()) {
      setStatusMessage({ text: 'Please enter Industry Instruction for Google Maps.', type: 'error' });
      return;
    }
    
    setIsExtracting(true);
    setStatusMessage({ text: `Sending Google Maps extraction request for ${gmapsIndustry} in ${gmapsLocation}...`, type: 'info' });
    
    try {
      const response = await fetch(`/api/v1/extraction/scrape`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          industry: gmapsIndustry,
          location: gmapsLocation || 'USA',
          limit: parseInt(gmapsLimit, 10) || 50
        })
      });
      
      if (!response.ok) throw new Error('Failed to initiate scraper task');
    } catch (err: any) {
      setIsExtracting(false);
      setStatusMessage({ text: err.message || 'Connection error starting extraction', type: 'error' });
    }
  };

  // Handle LinkedIn Autopilot Trigger
  const handleStartLinkedInAutopilot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!linkedinIndustry.trim()) {
      setStatusMessage({ text: 'Please enter Industry Instruction for LinkedIn.', type: 'error' });
      return;
    }

    setIsAutopilotRunning(true);
    setZeroLeadsWarning(null);
    setStatusMessage({ text: `Initializing LinkedIn Autopilot for Industry: ${linkedinIndustry}...`, type: 'info' });

    try {
      const params = new URLSearchParams({
        industry: linkedinIndustry,
        limit: '30',
        location: 'USA'
      });
      
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

  // Trigger Gemini AI Message Generation
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

  // Send 1 Test Connection Request on LinkedIn
  const handleSendOneTestConnection = async () => {
    if (!selectedCampaignId) {
      setStatusMessage({ text: 'Please select an active campaign first.', type: 'error' });
      return;
    }

    setIsSendingTestConnection(true);
    setStatusMessage({ text: 'Sending 1 test connection request on LinkedIn...', type: 'info' });

    try {
      const response = await fetch(`/api/v1/linkedin/start-campaign?campaign_id=${selectedCampaignId}&limit=1&simulate=true`, {
        method: 'POST'
      });

      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson.detail || 'Failed to dispatch test connection');
      }

      const data = await response.json();
      setStatusMessage({ text: `Success! Dispatch test connection initiated: ${data.message}`, type: 'success' });
      refetchStats();
    } catch (err: any) {
      setStatusMessage({ text: `Test connection error: ${err.message}`, type: 'error' });
    } finally {
      setIsSendingTestConnection(false);
    }
  };

  return (
    <div className="space-y-10 max-w-7xl mx-auto p-4 sm:p-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/50 backdrop-blur-md p-6 rounded-2xl border border-white/60 shadow-sm">
        <div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-3">
            Lead Sourcing & LinkedIn Automation Hub <Zap className="h-8 w-8 text-indigo-600 animate-pulse" />
          </h1>
          <p className="text-muted-foreground mt-1 text-sm font-medium">
            Dedicated Google Maps Business Extraction & LinkedIn Prospecting engines powered by automated target location rotation.
          </p>
        </div>
      </div>

      {/* Global Status Banner */}
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

      {/* SECTION 1: GOOGLE MAPS EXTRACTION */}
      <section className="space-y-6">
        <div className="flex items-center gap-2 border-b border-indigo-100 pb-3">
          <div className="h-8 w-8 bg-indigo-600 text-white rounded-lg flex items-center justify-center font-bold">1</div>
          <h2 className="text-xl font-extrabold text-slate-800 flex items-center gap-2">
            <MapPin className="h-5 w-5 text-indigo-600" /> Google Maps Local Business Scraper
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Controls Form */}
          <div className="lg:col-span-1 space-y-4">
            <Card className="glass-card shadow-md border border-slate-200/80">
              <CardHeader className="border-b border-slate-100 pb-3">
                <CardTitle className="text-base font-bold text-slate-800">Extraction Controls</CardTitle>
                <CardDescription className="text-xs">Specify target industry, location, and limit for automated extraction.</CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <form onSubmit={handleStartGmapsExtraction} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-700">Industry / Keyword Instruction</label>
                    <Input
                      value={gmapsIndustry}
                      onChange={(e) => setGmapsIndustry(e.target.value)}
                      placeholder="e.g. automotive, roofers, dentist"
                      required
                      disabled={isExtracting}
                      className="bg-white/90 border-slate-200 text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-700">Target Location / City / State</label>
                    <Input
                      value={gmapsLocation}
                      onChange={(e) => setGmapsLocation(e.target.value)}
                      placeholder="e.g. USA, New York, CA, Texas"
                      required
                      disabled={isExtracting}
                      className="bg-white/90 border-slate-200 text-xs"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-700">Lead Extraction Limit</label>
                    <select
                      value={gmapsLimit}
                      onChange={(e) => setGmapsLimit(e.target.value)}
                      disabled={isExtracting}
                      className="w-full bg-white/90 border border-slate-200 rounded-md p-2 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="20">20 leads</option>
                      <option value="50">50 leads</option>
                      <option value="100">100 leads</option>
                      <option value="250">250 leads</option>
                      <option value="500">500 leads</option>
                      <option value="0">⚡ Unlimited (All 70 Target Locations)</option>
                    </select>
                  </div>

                  <Button
                    type="submit"
                    disabled={isExtracting}
                    className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm"
                  >
                    {isExtracting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4 fill-current" />}
                    <span>Start Extraction</span>
                  </Button>
                </form>
              </CardContent>
            </Card>

            <Card className="glass-card border border-slate-200/60">
              <CardHeader className="pb-2 border-b border-slate-100">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">Live Scraper Progress</CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="text-xs text-slate-200 font-mono bg-slate-900 p-3.5 rounded-xl shadow-inner min-h-[90px] leading-relaxed break-all">
                  {gmapsProgressText || 'Ready. Enter Industry & Location and click "Start Extraction".'}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Results Listings */}
          <div className="lg:col-span-2">
            <Card className="glass-card shadow-md border border-slate-200/60 flex flex-col h-[520px] overflow-hidden">
              <CardHeader className="border-b border-slate-100 bg-slate-50/50 pb-3">
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle className="text-base font-bold text-slate-800">Extracted Listings & Social Media Details</CardTitle>
                    <CardDescription className="text-xs">Real-time stream of extracted businesses with contact info, social links & directories</CardDescription>
                  </div>
                  <span className="px-2.5 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold">
                    {extractedLeads.length} listings
                  </span>
                </div>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto p-4 space-y-3">
                {extractedLeads.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center p-8 text-slate-400">
                    <Building2 className="h-12 w-12 mb-3 text-slate-300" />
                    <p className="text-sm font-semibold">No businesses extracted yet</p>
                    <p className="text-xs text-slate-400 mt-1 max-w-sm">
                      Specify industry & location instructions on the left to launch extraction.
                    </p>
                  </div>
                ) : (
                  extractedLeads.map((lead, idx) => (
                    <div key={idx} className="p-3.5 rounded-xl border border-slate-200/60 bg-white/80 shadow-sm space-y-2.5">
                      <div className="flex items-start justify-between">
                        <div>
                          <h4 className="text-sm font-bold text-slate-800 flex items-center gap-1.5">
                            <Building2 className="h-4 w-4 text-indigo-600 shrink-0" /> {lead.name}
                          </h4>
                          {lead.rating && (
                            <span className="text-[11px] font-semibold text-amber-600 flex items-center gap-1 mt-0.5">
                              ⭐ {lead.rating}
                            </span>
                          )}
                        </div>
                        {lead.email ? (
                          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-bold">
                            ✉️ Email Found
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[10px]">
                            No Email
                          </span>
                        )}
                      </div>

                      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-slate-600">
                        {lead.phone && <div className="flex items-center gap-1"><Phone className="h-3 w-3 text-slate-400 shrink-0" /> {lead.phone}</div>}
                        {lead.website && (
                          <div className="flex items-center gap-1 truncate">
                            <Globe className="h-3 w-3 text-slate-400 shrink-0" />
                            <a href={lead.website} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline truncate">{lead.website}</a>
                          </div>
                        )}
                        {lead.address && (
                          <div className="col-span-1 md:col-span-2 flex items-center gap-1 text-[11px] text-slate-500 truncate">
                            <MapPin className="h-3 w-3 text-slate-400 shrink-0" /> {lead.address}
                          </div>
                        )}
                      </div>

                      {lead.description && (
                        <p className="text-[11px] text-slate-600 line-clamp-2 italic bg-slate-50 p-2 rounded border border-slate-100">
                          "{lead.description}"
                        </p>
                      )}

                      {lead.email && (
                        <div className="text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 p-1.5 rounded-md font-mono flex items-center gap-1.5">
                          <Mail className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
                          <span>{lead.email}</span>
                        </div>
                      )}

                      {/* Social Media & Directories Links */}
                      {(lead.facebook_url || lead.instagram_url || lead.linkedin_url || lead.twitter_url || lead.youtube_url || (lead.directories && Object.keys(lead.directories).length > 0)) && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-slate-100">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1">Socials & Profiles:</span>
                          {lead.facebook_url && (
                            <a href={lead.facebook_url} target="_blank" rel="noreferrer" className="px-2 py-0.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded text-[10px] font-semibold border border-blue-200 flex items-center gap-1">
                              📘 Facebook
                            </a>
                          )}
                          {lead.instagram_url && (
                            <a href={lead.instagram_url} target="_blank" rel="noreferrer" className="px-2 py-0.5 bg-pink-50 text-pink-700 hover:bg-pink-100 rounded text-[10px] font-semibold border border-pink-200 flex items-center gap-1">
                              📷 Instagram
                            </a>
                          )}
                          {lead.linkedin_url && (
                            <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="px-2 py-0.5 bg-sky-50 text-sky-700 hover:bg-sky-100 rounded text-[10px] font-semibold border border-sky-200 flex items-center gap-1">
                              💼 LinkedIn
                            </a>
                          )}
                          {lead.twitter_url && (
                            <a href={lead.twitter_url} target="_blank" rel="noreferrer" className="px-2 py-0.5 bg-slate-100 text-slate-800 hover:bg-slate-200 rounded text-[10px] font-semibold border border-slate-300 flex items-center gap-1">
                              🐦 Twitter/X
                            </a>
                          )}
                          {lead.youtube_url && (
                            <a href={lead.youtube_url} target="_blank" rel="noreferrer" className="px-2 py-0.5 bg-red-50 text-red-700 hover:bg-red-100 rounded text-[10px] font-semibold border border-red-200 flex items-center gap-1">
                              ▶️ YouTube
                            </a>
                          )}

                          {/* Directory Profiles */}
                          {lead.directories && Object.entries(lead.directories).map(([dName, dUrl], dIdx) => {
                            let badgeStyle = "bg-amber-50 text-amber-800 border-amber-200";
                            let icon = "🌐";
                            if (dName.toLowerCase().includes("yelp")) {
                              badgeStyle = "bg-red-50 text-red-700 border-red-200";
                              icon = "🔴 Yelp";
                            } else if (dName.toLowerCase().includes("nextdoor")) {
                              badgeStyle = "bg-emerald-50 text-emerald-700 border-emerald-200";
                              icon = "🟢 Nextdoor";
                            } else if (dName.toLowerCase().includes("yellowpages") || dName.toLowerCase().includes("yp")) {
                              badgeStyle = "bg-yellow-100 text-yellow-800 border-yellow-300";
                              icon = "🟡 YellowPages";
                            } else if (dName.toLowerCase().includes("bbb")) {
                              badgeStyle = "bg-blue-100 text-blue-800 border-blue-300";
                              icon = "🔵 BBB";
                            } else {
                              icon = `📌 ${dName}`;
                            }
                            return (
                              <a key={dIdx} href={dUrl} target="_blank" rel="noreferrer" className={`px-2 py-0.5 rounded text-[10px] font-semibold border flex items-center gap-1 hover:opacity-80 ${badgeStyle}`}>
                                {icon}
                              </a>
                            );
                          })}
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
      </section>

      {/* SECTION 2: LINKEDIN PROSPECTING & AUTOMATION */}
      <section className="space-y-6 pt-4">
        <div className="flex items-center gap-2 border-b border-sky-100 pb-3">
          <div className="h-8 w-8 bg-sky-600 text-white rounded-lg flex items-center justify-center font-bold">2</div>
          <h2 className="text-xl font-extrabold text-slate-800 flex items-center gap-2">
            <Linkedin className="h-5 w-5 text-sky-600" /> LinkedIn Automated Prospecting & Outreach
          </h2>
        </div>

        {/* Zero Leads Warning Banner */}
        {zeroLeadsWarning && (
          <div className="p-4 rounded-xl border border-amber-300 bg-amber-50 text-amber-900 flex items-start gap-3 animate-in fade-in duration-300 shadow-sm">
            <AlertTriangle className="h-6 w-6 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-extrabold text-amber-900">0 Leads Discovered</h4>
              <p className="text-xs font-medium text-amber-800 mt-0.5">{zeroLeadsWarning}</p>
            </div>
            <button onClick={() => setZeroLeadsWarning(null)} className="ml-auto text-xs font-bold text-amber-800 hover:underline shrink-0">Dismiss</button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Controls Form */}
          <div className="lg:col-span-1 space-y-4">
            <Card className="glass-card shadow-md border border-slate-200/80">
              <CardHeader className="border-b border-slate-100 pb-3">
                <CardTitle className="text-base font-bold text-slate-800">LinkedIn Target Industry</CardTitle>
                <CardDescription className="text-xs">Specify target industry instruction for decision-maker prospecting.</CardDescription>
              </CardHeader>
              <CardContent className="pt-4">
                <form onSubmit={handleStartLinkedInAutopilot} className="space-y-4">
                  <div className="space-y-1.5">
                    <label className="text-xs font-bold text-slate-700">Industry / Niche Instruction</label>
                    <Input
                      value={linkedinIndustry}
                      onChange={(e) => setLinkedinIndustry(e.target.value)}
                      placeholder="e.g. Automotive, Real Estate, SaaS Founder"
                      required
                      disabled={isAutopilotRunning}
                      className="bg-white/90 border-slate-200"
                    />
                  </div>

                  <div className="space-y-2 pt-1">
                    <Button
                      type="submit"
                      disabled={isAutopilotRunning}
                      className="w-full bg-gradient-to-r from-sky-600 to-blue-700 hover:from-sky-700 hover:to-blue-800 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      {isAutopilotRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Linkedin className="h-4 w-4" />}
                      <span>Launch LinkedIn Autopilot</span>
                    </Button>

                    <Button
                      type="button"
                      onClick={handleSendOneTestConnection}
                      disabled={isSendingTestConnection || !selectedCampaignId}
                      className="w-full bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-9 text-xs flex items-center justify-center gap-1.5 shadow-sm"
                    >
                      {isSendingTestConnection ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                      <span>Send 1 Test Connection Request</span>
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </div>

          {/* Metrics & Execution Console */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="glass-card shadow-md border border-slate-200/80">
              <CardHeader className="pb-3 border-b border-slate-100">
                <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                  <div>
                    <CardTitle className="text-base font-bold text-slate-800">Campaign Outreach Metrics</CardTitle>
                    <CardDescription className="text-xs">Live metric updates for selected LinkedIn campaign</CardDescription>
                  </div>
                  <div className="w-full sm:w-60">
                    <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
                      <SelectTrigger className="bg-white border-slate-200 text-xs font-bold">
                        <SelectValue placeholder="Select Campaign" />
                      </SelectTrigger>
                      <SelectContent>
                        {campaigns?.map((c) => (
                          <SelectItem key={c.id} value={c.id} className="text-xs">{c.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-4">
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="p-3 bg-slate-50 rounded-xl border text-center">
                    <div className="text-xl font-extrabold text-slate-800">{stats?.total || 0}</div>
                    <div className="text-[10px] font-bold text-slate-500 uppercase">Total Leads</div>
                  </div>
                  <div className="p-3 bg-sky-50 rounded-xl border text-center">
                    <div className="text-xl font-extrabold text-sky-800">{stats?.scraped || 0}</div>
                    <div className="text-[10px] font-bold text-sky-600 uppercase">Scraped</div>
                  </div>
                  <div className="p-3 bg-purple-50 rounded-xl border text-center">
                    <div className="text-xl font-extrabold text-purple-800">{stats?.pending_generation || 0}</div>
                    <div className="text-[10px] font-bold text-purple-600 uppercase">Pending AI</div>
                  </div>
                  <div className="p-3 bg-emerald-50 rounded-xl border text-center">
                    <div className="text-xl font-extrabold text-emerald-800">{stats?.ready_to_send || 0}</div>
                    <div className="text-[10px] font-bold text-emerald-600 uppercase">Ready Send</div>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-xl border text-center col-span-2 sm:col-span-1">
                    <div className="text-xl font-extrabold text-blue-800">{stats?.sent || 0}</div>
                    <div className="text-[10px] font-bold text-blue-600 uppercase">Connections Sent</div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-2.5 mt-4 pt-3 border-t border-slate-100">
                  <Button onClick={handleGenerateLinkedInMessages} className="bg-purple-600 hover:bg-purple-700 text-white font-bold text-xs h-8">
                    <Sparkles className="h-3.5 w-3.5 mr-1" /> Draft Gemini AI Messages
                  </Button>
                  <Button onClick={() => refetchStats()} variant="outline" className="text-xs font-bold h-8 ml-auto">
                    <RefreshCw className="h-3.5 w-3.5 mr-1" /> Refresh
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card className="glass-card border border-slate-200/60">
              <CardHeader className="pb-2 border-b border-slate-100">
                <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">LinkedIn Autopilot Real-time Stream</CardTitle>
              </CardHeader>
              <CardContent className="pt-3">
                <div className="text-xs text-sky-300 font-mono bg-slate-900 p-3.5 rounded-xl shadow-inner min-h-[100px] leading-relaxed break-all">
                  {autopilotLog || 'Ready. Enter Industry instruction and click "Launch LinkedIn Autopilot".'}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>
    </div>
  );
}
