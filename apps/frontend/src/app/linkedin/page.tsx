'use client';

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Linkedin, Search, Sparkles, Send, RefreshCw, AlertCircle, CheckCircle, HelpCircle, Loader2, Play } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { API_BASE_URL } from '@/lib/api';

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

export default function LinkedInCampaigns() {
  const [selectedCampaignId, setSelectedCampaignId] = useState<string>('');
  const [industry, setIndustry] = useState<string>('automotive');
  const [location, setLocation] = useState<string>('');
  const [scrapeLimit, setScrapeLimit] = useState<number>(20);
  const [liAtCookie, setLiAtCookie] = useState<string>('');
  const [dailyLimit, setDailyLimit] = useState<number>(100);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' | null }>({ text: '', type: null });
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  
  // Autopilot States
  const [activeTab, setActiveTab] = useState<'autopilot' | 'manual'>('autopilot');
  const [autopilotIndustry, setAutopilotIndustry] = useState<string>('automotive');
  const [autopilotLocation, setAutopilotLocation] = useState<string>('');
  const [autopilotLimit, setAutopilotLimit] = useState<number>(10);
  const [autopilotLog, setAutopilotLog] = useState<string>('');
  const [autopilotStage, setAutopilotStage] = useState<string>('');
  
  const queryClient = useQueryClient();

  // Load campaigns
  const { data: campaigns, isLoading: isLoadingCampaigns } = useQuery<Campaign[]>({
    queryKey: ['linkedin-campaigns-list'],
    queryFn: async () => {
      const response = await fetch('/api/v1/campaigns/');
      if (!response.ok) throw new Error('Failed to fetch campaigns');
      return response.json();
    }
  });

  // Load stats for selected campaign
  const { data: stats, isLoading: isLoadingStats, refetch: refetchStats } = useQuery<LinkedInStats>({
    queryKey: ['linkedin-campaign-stats', selectedCampaignId],
    queryFn: async () => {
      if (!selectedCampaignId) return { total: 0, scraped: 0, pending_generation: 0, ready_to_send: 0, sent: 0 };
      const response = await fetch(`/api/v1/linkedin/stats?campaign_id=${selectedCampaignId}`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      return response.json();
    },
    enabled: !!selectedCampaignId,
    refetchInterval: 10000 // Refetch stats every 10 seconds for real-time progress logging
  });

  // Automatically select the first campaign if none selected
  useEffect(() => {
    if (campaigns && campaigns.length > 0 && !selectedCampaignId) {
      setSelectedCampaignId(campaigns[0].id);
    }
  }, [campaigns, selectedCampaignId]);

  // Mutations for LinkedIn campaign workflows
  const scrapeMutation = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams({
        industry,
        limit: scrapeLimit.toString(),
        campaign_id: selectedCampaignId
      });
      if (location) params.append('location', location);
      const response = await fetch(`/api/v1/linkedin/search?${params.toString()}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Scraper task initiation failed');
      return response.json();
    },
    onSuccess: (data) => {
      setStatusMessage({
        text: `Success! Lead discovery has started in the background: ${data.message}`,
        type: 'success'
      });
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaign-stats', selectedCampaignId] });
    },
    onError: (err: any) => {
      setStatusMessage({ text: `Failed to start lead discovery: ${err.message}`, type: 'error' });
    }
  });

  const generateMessagesMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`/api/v1/linkedin/generate-messages?campaign_id=${selectedCampaignId}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Gemini message generation failed');
      return response.json();
    },
    onSuccess: (data) => {
      setStatusMessage({
        text: `Success! Gemini has started message drafting in the background.`,
        type: 'success'
      });
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaign-stats', selectedCampaignId] });
    },
    onError: (err: any) => {
      setStatusMessage({ text: `Failed to trigger message generation: ${err.message}`, type: 'error' });
    }
  });

  const startOutreachMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch(`/api/v1/linkedin/start-campaign?campaign_id=${selectedCampaignId}&limit=${dailyLimit}`, {
        method: 'POST'
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start outreach campaign');
      }
      return response.json();
    },
    onSuccess: (data) => {
      setStatusMessage({
        text: `Campaign Run Active! ${data.message}`,
        type: 'success'
      });
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaign-stats', selectedCampaignId] });
    },
    onError: (err: any) => {
      setStatusMessage({ text: `Failed to initiate outreach: ${err.message}`, type: 'error' });
    }
  });

  const autopilotMutation = useMutation({
    mutationFn: async () => {
      const params = new URLSearchParams({
        industry: autopilotIndustry,
        limit: autopilotLimit.toString()
      });
      if (autopilotLocation) params.append('location', autopilotLocation);
      const response = await fetch(`/api/v1/linkedin/autopilot?${params.toString()}`, {
        method: 'POST'
      });
      if (!response.ok) throw new Error('Autopilot initialization failed');
      return response.json();
    },
    onSuccess: (data) => {
      setStatusMessage({
        text: `Autopilot initiated successfully! Created Campaign: "${data.campaign_name}".`,
        type: 'success'
      });
      setSelectedCampaignId(data.campaign_id);
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaigns-list'] });
      queryClient.invalidateQueries({ queryKey: ['linkedin-campaign-stats', data.campaign_id] });
    },
    onError: (err: any) => {
      setStatusMessage({ text: `Failed to start autopilot: ${err.message}`, type: 'error' });
    }
  });

  // WebSocket real-time autopilot logs
  useEffect(() => {
    if (!selectedCampaignId) return;
    const wsUrl = API_BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/live';
    const ws = new WebSocket(wsUrl);
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event === 'autopilot_status' && data.campaign_id === selectedCampaignId) {
          setAutopilotLog(data.message);
          setAutopilotStage(data.stage);
          refetchStats();
        }
      } catch (e) {
        console.error('Error parsing WebSocket log message:', e);
      }
    };
    
    return () => {
      ws.close();
    };
  }, [selectedCampaignId, refetchStats]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refetchStats();
    setIsRefreshing(false);
  };

  const handleSaveConfig = () => {
    setStatusMessage({
      text: "Settings saved successfully! These session values will override default configurations during automated Playwright runs.",
      type: 'success'
    });
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto p-4">
      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40 backdrop-blur-md p-6 rounded-2xl border border-white/60 shadow-sm">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-blue-600 via-indigo-600 to-sky-600 bg-clip-text text-transparent flex items-center gap-2">
            LinkedIn Auto Outreach <Linkedin className="h-8 w-8 text-blue-600 animate-pulse fill-current" />
          </h1>
          <p className="text-muted-foreground mt-1.5 text-sm font-medium">
            Find organizations by industry, write connection invitations with Gemini, and dispatch via Playwright.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-500/10 text-blue-600 rounded-full text-xs font-semibold uppercase tracking-wider border border-blue-500/20">
          <Sparkles className="h-3.5 w-3.5" /> Automations Panel
        </div>
      </div>

      {/* Status Alert Banner */}
      {statusMessage.text && (
        <div className={`p-4 rounded-xl border flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-300 ${
          statusMessage.type === 'success' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
          statusMessage.type === 'error' ? 'bg-rose-50 text-rose-800 border-rose-200' :
          'bg-blue-50 text-blue-800 border-blue-200'
        }`}>
          {statusMessage.type === 'success' ? <CheckCircle className="h-5 w-5 shrink-0 mt-0.5 text-emerald-600" /> :
           statusMessage.type === 'error' ? <AlertCircle className="h-5 w-5 shrink-0 mt-0.5 text-rose-600" /> :
           <HelpCircle className="h-5 w-5 shrink-0 mt-0.5 text-blue-600" />}
          <div className="text-sm font-semibold">{statusMessage.text}</div>
          <button onClick={() => setStatusMessage({ text: '', type: null })} className="ml-auto text-xs font-bold hover:underline shrink-0">Dismiss</button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Step-by-Step Campaign Management Card */}
        <div className="lg:col-span-2 space-y-8">
          
          <Card className="glass-card shadow-md border border-slate-200/60 overflow-hidden">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 pb-4">
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    LinkedIn Campaign Workflow
                  </CardTitle>
                  <CardDescription className="text-xs">Follow the steps sequentially to manage outreach campaigns.</CardDescription>
                </div>
                {selectedCampaignId && (
                  <Button 
                    variant="ghost" 
                    size="sm" 
                    onClick={handleRefresh}
                    disabled={isRefreshing}
                    className="h-8 text-xs font-bold flex items-center gap-1.5 text-indigo-600 hover:text-indigo-800"
                  >
                    <RefreshCw className={`h-3.5 w-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
                    Refresh Stats
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-6 space-y-8">
              {/* Mode Selection Tabs */}
              <div className="flex space-x-2 border-b border-slate-100 pb-4">
                <button
                  type="button"
                  onClick={() => setActiveTab('autopilot')}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-2 ${
                    activeTab === 'autopilot'
                      ? 'bg-blue-100 text-blue-700 border-b-2 border-blue-600'
                      : 'text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  Autopilot Mode (Unified)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab('manual')}
                  className={`px-4 py-2 text-xs font-bold rounded-lg transition-colors flex items-center gap-2 ${
                    activeTab === 'manual'
                      ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600'
                      : 'text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  <HelpCircle className="h-3.5 w-3.5" />
                  Manual Step-by-Step
                </button>
              </div>

              {activeTab === 'autopilot' ? (
                <div className="space-y-6">
                  <div>
                    <h3 className="font-bold text-sm text-slate-800">Launch Outreach Autopilot</h3>
                    <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">
                      Specify an industry. The system will automatically discover prospects, write connection notes with Gemini, and connect via Playwright sequentially.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-600">Industry / Keyword</label>
                      <Input
                        value={autopilotIndustry}
                        onChange={(e) => setAutopilotIndustry(e.target.value)}
                        placeholder="e.g. automotive, dentist"
                        className="bg-white/80 border-slate-200 text-sm h-9"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-600">Location (Optional)</label>
                      <Input
                        value={autopilotLocation}
                        onChange={(e) => setAutopilotLocation(e.target.value)}
                        placeholder="e.g. New York, CA"
                        className="bg-white/80 border-slate-200 text-sm h-9"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-slate-600">Max Lead Outreach Limit</label>
                      <Input
                        type="number"
                        value={autopilotLimit}
                        onChange={(e) => setAutopilotLimit(parseInt(e.target.value) || 10)}
                        className="bg-white/80 border-slate-200 text-sm h-9"
                      />
                    </div>
                  </div>

                  <Button
                    onClick={() => autopilotMutation.mutate()}
                    disabled={autopilotMutation.isPending}
                    className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm mt-2"
                  >
                    {autopilotMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4 fill-current" />
                    )}
                    Launch Autopilot Outreach Run
                  </Button>

                  {/* Realtime Autopilot Logs Card */}
                  {selectedCampaignId && (autopilotLog || autopilotStage) && (
                    <div className="bg-slate-50 border border-slate-100 rounded-xl p-4 mt-4 space-y-3">
                      <div className="flex justify-between items-center text-xs">
                        <span className="font-bold text-slate-600 uppercase tracking-wider flex items-center gap-1.5">
                          <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
                          Live Status: <span className="text-blue-600 font-extrabold">{autopilotStage.toUpperCase()}</span>
                        </span>
                      </div>
                      <p className="text-xs text-slate-700 font-mono bg-white p-3 border rounded-md shadow-inner whitespace-pre-wrap leading-relaxed">
                        {autopilotLog || 'Initializing autopilot pipeline...'}
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Select campaign */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold uppercase tracking-wider text-slate-500">Select Target CRM Campaign</label>
                    {isLoadingCampaigns ? (
                      <div className="h-10 bg-slate-100 rounded-md animate-pulse"></div>
                    ) : (
                      <Select value={selectedCampaignId} onValueChange={setSelectedCampaignId}>
                        <SelectTrigger className="w-full bg-white/80 border-slate-200">
                          <SelectValue placeholder="Choose a campaign" />
                        </SelectTrigger>
                        <SelectContent>
                          {campaigns?.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.name} ({c.status.toUpperCase()})
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>

                  <div className="border-l-2 border-indigo-200 pl-4 space-y-6">
                    
                    {/* Step 1: Search Scraper */}
                    <div className="space-y-3 relative">
                      <div className="absolute -left-[25px] top-1 h-5 w-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px] font-extrabold shadow-sm">1</div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-800">Scrape Industry Leads</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">Discovers CEOs, owners, and founders on LinkedIn in the target industry and adds them to this campaign.</p>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-1">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-slate-600">Industry / Keyword</label>
                          <Input 
                            value={industry} 
                            onChange={(e) => setIndustry(e.target.value)} 
                            placeholder="e.g. automotive, dentist"
                            className="bg-white/80 border-slate-200 text-sm h-9"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-slate-600">Location (Optional)</label>
                          <Input 
                            value={location} 
                            onChange={(e) => setLocation(e.target.value)} 
                            placeholder="e.g. London, UK"
                            className="bg-white/80 border-slate-200 text-sm h-9"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-slate-600">Lead limit to Scrape</label>
                          <Input 
                            type="number"
                            value={scrapeLimit} 
                            onChange={(e) => setScrapeLimit(parseInt(e.target.value) || 20)} 
                            className="bg-white/80 border-slate-200 text-sm h-9"
                          />
                        </div>
                      </div>
                      
                      <Button 
                        onClick={() => scrapeMutation.mutate()} 
                        disabled={scrapeMutation.isPending || !selectedCampaignId}
                        className="bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-9 text-xs flex items-center gap-1.5 shadow-sm mt-2"
                      >
                        {scrapeMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}
                        Scrape & Import Leads
                      </Button>
                    </div>

                    {/* Step 2: Message Generation */}
                    <div className="space-y-3 relative pt-4 border-t border-slate-100">
                      <div className="absolute -left-[25px] top-5 h-5 w-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px] font-extrabold shadow-sm">2</div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-800 mt-4">Draft Outreach Messages (Gemini AI)</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">Generates personalized connection invitations under 280 characters for all scraper leads with missing outreach text.</p>
                      </div>
                      
                      {stats && (
                        <div className="text-xs text-slate-500 font-semibold flex items-center gap-1">
                          <span>Leads pending message generation:</span>
                          <span className="text-indigo-600 font-extrabold">{stats.pending_generation}</span>
                        </div>
                      )}
                      
                      <Button 
                        onClick={() => generateMessagesMutation.mutate()} 
                        disabled={generateMessagesMutation.isPending || !selectedCampaignId || stats?.pending_generation === 0}
                        className="bg-blue-600 hover:bg-blue-700 text-white font-bold h-9 text-xs flex items-center gap-1.5 shadow-sm"
                      >
                        {generateMessagesMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                        Generate Messages
                      </Button>
                    </div>

                    {/* Step 3: Run Outreach */}
                    <div className="space-y-3 relative pt-4 border-t border-slate-100">
                      <div className="absolute -left-[25px] top-5 h-5 w-5 rounded-full bg-indigo-600 text-white flex items-center justify-center text-[10px] font-extrabold shadow-sm">3</div>
                      <div>
                        <h3 className="font-bold text-sm text-slate-800 mt-4">Execute Playwright Delivery</h3>
                        <p className="text-xs text-muted-foreground leading-relaxed mt-0.5">Launches the background browser task to log in, navigate to profiles, paste message drafts, and submit connection invitations.</p>
                      </div>
                      
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-1">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-slate-600">Daily Messaging Throttle Limit</label>
                          <Input 
                            type="number"
                            value={dailyLimit} 
                            onChange={(e) => setDailyLimit(parseInt(e.target.value) || 100)} 
                            className="bg-white/80 border-slate-200 text-sm h-9"
                          />
                        </div>
                      </div>

                      {stats && (
                        <div className="text-xs text-slate-500 font-semibold flex items-center gap-4">
                          <div>Ready to Send: <span className="text-emerald-600 font-extrabold">{stats.ready_to_send}</span></div>
                          <div>Sent Invitations: <span className="text-slate-700 font-extrabold">{stats.sent}</span></div>
                        </div>
                      )}
                      
                      <Button 
                        onClick={() => startOutreachMutation.mutate()} 
                        disabled={startOutreachMutation.isPending || !selectedCampaignId || stats?.ready_to_send === 0}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold h-9 text-xs flex items-center gap-1.5 shadow-sm"
                      >
                        {startOutreachMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                        Start Sending Messages
                      </Button>
                    </div>

                  </div>
                </div>
              )}

            </CardContent>
          </Card>
        </div>

        {/* Configurations Side Panel */}
        <div className="space-y-8">
          <Card className="glass-card shadow-md border border-slate-200/60">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                Outreach Telemetry
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {isLoadingStats ? (
                <div className="p-4 text-center text-slate-400 animate-pulse text-sm">Loading telemetry...</div>
              ) : !stats || stats.total === 0 ? (
                <p className="text-xs text-slate-400 text-center italic py-4">No LinkedIn leads discovered in this campaign yet.</p>
              ) : (
                <div className="space-y-4">
                  <div className="flex justify-between items-center text-xs font-semibold py-1.5 border-b border-slate-100">
                    <span className="text-slate-500">Total LinkedIn Leads</span>
                    <span className="text-slate-800 font-bold">{stats.total}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs font-semibold py-1.5 border-b border-slate-100">
                    <span className="text-slate-500">Scraped Prospects</span>
                    <span className="text-slate-800 font-bold">{stats.scraped}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs font-semibold py-1.5 border-b border-slate-100">
                    <span className="text-slate-500">Pending AI Drafts</span>
                    <span className="text-indigo-600 font-bold">{stats.pending_generation}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs font-semibold py-1.5 border-b border-slate-100">
                    <span className="text-slate-500">Ready for Playwright</span>
                    <span className="text-emerald-600 font-bold">{stats.ready_to_send}</span>
                  </div>
                  <div className="flex justify-between items-center text-xs font-semibold py-1.5">
                    <span className="text-slate-500">Sent Invitations</span>
                    <span className="text-slate-800 font-bold">{stats.sent}</span>
                  </div>

                  {/* Progress Ring / Bar representation */}
                  <div className="pt-4 border-t border-slate-100 space-y-2">
                    <div className="flex justify-between text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      <span>Outreach Progress</span>
                      <span>{Math.round((stats.sent / stats.total) * 100)}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden border p-0.5">
                      <div 
                        className="h-full bg-blue-600 rounded-full transition-all duration-500" 
                        style={{ width: `${Math.round((stats.sent / stats.total) * 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="glass-card shadow-md border border-slate-200/60">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800">
                Session Credentials
              </CardTitle>
              <CardDescription className="text-xs">Required credentials for Playwright connection scraping.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 space-y-4">
              
              <div className="space-y-1.5">
                <label className="text-[10px] font-bold text-slate-600 flex items-center gap-1">
                  LinkedIn Session Cookie (`li_at`)
                </label>
                <Input 
                  type="password"
                  value={liAtCookie} 
                  onChange={(e) => setLiAtCookie(e.target.value)} 
                  placeholder="Paste your li_at session cookie here"
                  className="bg-white/80 border-slate-200 text-xs h-9"
                />
              </div>

              <div className="bg-slate-50/50 p-3 rounded-xl border border-slate-100 space-y-2">
                <h4 className="text-[10px] font-bold text-slate-600 flex items-center gap-1">
                  <AlertCircle className="h-3.5 w-3.5 text-amber-500" /> Playwright Warning
                </h4>
                <p className="text-[10px] text-muted-foreground leading-relaxed">
                  If cookie values are left empty, tasks will execute in a simulated sandbox environment using predefined industry samples. Do not share your cookies publicly.
                </p>
              </div>

              <Button 
                onClick={handleSaveConfig}
                className="w-full bg-slate-800 hover:bg-slate-900 text-white font-bold h-9 text-xs shadow-sm"
              >
                Save Cookie Setting
              </Button>

            </CardContent>
          </Card>
        </div>

      </div>
    </div>
  );
}
