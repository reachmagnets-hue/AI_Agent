'use client';

import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { MapPin, Search, Sparkles, AlertCircle, CheckCircle, HelpCircle, Loader2, Play, Download, Building2, Phone, Globe, Mail } from 'lucide-react';
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

export default function DataExtractionPage() {
  const [industry, setIndustry] = useState<string>('automotive');
  const [location, setLocation] = useState<string>('');
  const [limit, setLimit] = useState<number>(10);
  const [isExtracting, setIsExtracting] = useState<boolean>(false);
  const [extractedLeads, setExtractedLeads] = useState<ExtractedLead[]>([]);
  const [progressText, setProgressText] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' | 'info' | null }>({ text: '', type: null });
  
  const leadsEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll list as new leads are added
  useEffect(() => {
    if (extractedLeads.length > 0) {
      leadsEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
  }, [extractedLeads]);

  // WebSocket Live Stream Listener
  useEffect(() => {
    const rawApiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const wsUrl = rawApiUrl.replace('http://', 'ws://').replace('https://', 'wss://') + '/ws/live';
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      console.log('Connected to live progress WebSockets');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.event === 'extraction_started') {
          setIsExtracting(true);
          setExtractedLeads([]);
          setProgressText(`Launching search for "${data.industry}" in "${data.location}" (Target: ${data.limit} shops)...`);
          setStatusMessage({ text: 'Google Maps scraping has started in the background.', type: 'info' });
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
            setProgressText(`[Listing Already in DB] ${lead.name}`);
          } else {
            setProgressText(`[Extracted Lead #${data.current}/${data.total}] ${lead.name}`);
          }
        }
        
        else if (data.event === 'extraction_completed') {
          setIsExtracting(false);
          setProgressText('Extraction complete!');
          setStatusMessage({
            text: `Success! Local leads with social details saved in database under campaign: "Extracted - ${data.industry.toUpperCase()} in ${data.location.toUpperCase()}"`,
            type: 'success'
          });
        }
        
        else if (data.event === 'extraction_failed') {
          setIsExtracting(false);
          setProgressText('Extraction failed.');
          setStatusMessage({ text: `Failed: ${data.error || 'Scraping process encountered an error'}`, type: 'error' });
        }
      } catch (e) {
        console.error('Error parsing live extraction stream:', e);
      }
    };
    
    return () => {
      ws.close();
    };
  }, []);

  const handleStartExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!industry.trim() || !location.trim()) {
      setStatusMessage({ text: 'Please fill out both Industry and Place/Location filters.', type: 'error' });
      return;
    }
    
    setIsExtracting(true);
    setStatusMessage({ text: 'Sending extraction request to server...', type: 'info' });
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/extraction/scrape`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          industry,
          location,
          limit
        })
      });
      
      if (!response.ok) {
        throw new Error('Failed to initiate scraper task on server');
      }
    } catch (err: any) {
      setIsExtracting(false);
      setStatusMessage({ text: err.message || 'Connection error starting extraction', type: 'error' });
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto p-4">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40 backdrop-blur-md p-6 rounded-2xl border border-white/60 shadow-sm">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-violet-600 via-indigo-600 to-purple-600 bg-clip-text text-transparent flex items-center gap-2.5">
            Google Maps Data Extraction <MapPin className="h-8 w-8 text-indigo-600 animate-bounce" />
          </h1>
          <p className="text-muted-foreground mt-1.5 text-sm font-medium">
            Scrape shops directly from Google Maps with deep enrichment: ratings, business summary, website emails, and social media profiles (Facebook, Instagram, LinkedIn, Twitter, YouTube).
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-indigo-500/10 text-indigo-600 rounded-full text-xs font-semibold uppercase tracking-wider border border-indigo-500/20">
          <Download className="h-3.5 w-3.5" /> Deep Scraper
        </div>
      </div>

      {/* Alert Banners */}
      {statusMessage.text && (
        <div className={`p-4 rounded-xl border flex items-start gap-3 animate-in fade-in slide-in-from-top-2 duration-300 ${
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

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Scraper Control panel */}
        <div className="lg:col-span-1 space-y-6">
          <Card className="glass-card shadow-md border border-slate-200/60">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800">Scrape Parameters</CardTitle>
              <CardDescription className="text-xs">Define search targets for lead extraction.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleStartExtraction} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-600">Industry / Shop Type</label>
                  <Input
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    placeholder="e.g. roofers, dentist, salon"
                    required
                    disabled={isExtracting}
                    className="bg-white/80 border-slate-200"
                  />
                </div>
                
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-600">Place / Location</label>
                  <Input
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Dallas TX, Nelamangala"
                    required
                    disabled={isExtracting}
                    className="bg-white/80 border-slate-200"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-slate-600">Max Results to Extract</label>
                  <Input
                    type="number"
                    value={limit}
                    onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                    required
                    min={1}
                    max={500}
                    disabled={isExtracting}
                    className="bg-white/80 border-slate-200"
                  />
                </div>

                <Button
                  type="submit"
                  disabled={isExtracting}
                  className="w-full bg-indigo-600 hover:bg-indigo-700 text-white font-bold h-10 text-xs flex items-center justify-center gap-1.5 shadow-sm pt-2"
                >
                  {isExtracting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Running Deep Scraper...</span>
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 fill-current" />
                      <span>Start Google Maps Scrape</span>
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
          
          <Card className="glass-card border border-slate-200/50">
            <CardHeader className="pb-3 border-b border-slate-100">
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">Live Status Console</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="text-xs text-slate-600 font-mono bg-slate-900 text-slate-200 p-4 rounded-xl shadow-inner min-h-[100px] leading-relaxed break-all">
                {progressText || 'Ready to start. Enter parameters and launch scraper.'}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Real-time Extracted Leads List card */}
        <div className="lg:col-span-2">
          <Card className="glass-card shadow-md border border-slate-200/60 flex flex-col h-[650px] overflow-hidden">
            <CardHeader className="border-b border-slate-100 bg-slate-50/50 pb-4">
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="text-lg font-bold text-slate-800">Live Extracted Listings & Social Profiles</CardTitle>
                  <CardDescription className="text-xs">Real-time stream of extracted details from Google Maps & Web Pages</CardDescription>
                </div>
                <span className="px-2.5 py-1 bg-indigo-100 text-indigo-700 rounded-full text-xs font-bold">
                  {extractedLeads.length} listings found
                </span>
              </div>
            </CardHeader>
            <CardContent className="flex-1 overflow-y-auto p-6 space-y-4">
              {extractedLeads.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8 text-slate-400">
                  <Building2 className="h-16 w-16 mb-4 text-slate-300" />
                  <p className="text-sm font-semibold">No shops extracted yet</p>
                  <p className="text-xs text-slate-400 mt-1 max-w-sm">
                    Specify industry and location on the left panel to launch the automated crawler.
                  </p>
                </div>
              ) : (
                extractedLeads.map((lead, idx) => (
                  <div 
                    key={idx} 
                    className="p-4 rounded-xl border border-slate-200/60 bg-white/70 shadow-sm flex flex-col gap-2.5 hover:border-indigo-300 transition-colors animate-in fade-in slide-in-from-bottom-2 duration-300"
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
                            In Database
                          </span>
                        )}
                        {lead.email ? (
                          <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 rounded-full text-[10px] font-bold flex items-center gap-1">
                            <Mail className="h-3 w-3" /> Email Discovered
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 bg-slate-100 text-slate-500 rounded-full text-[10px] font-medium">
                            No Email
                          </span>
                        )}
                      </div>
                    </div>

                    {lead.description && (
                      <div className="text-xs text-slate-600 bg-slate-50 p-2.5 rounded-lg border border-slate-100 line-clamp-2">
                        <span className="font-semibold text-slate-700">About Shop: </span>
                        {lead.description}
                      </div>
                    )}

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
                          <a 
                            href={lead.website} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="text-indigo-600 hover:underline font-medium"
                          >
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

                    {/* Social Media & Business Directories Row */}
                    {((lead.facebook_url || lead.instagram_url || lead.linkedin_url || lead.twitter_url || lead.youtube_url) || (lead.internal_notes && lead.internal_notes.includes("[Directories]"))) && (
                      <div className="border-t border-slate-100 pt-2.5 flex flex-wrap items-center gap-2">
                        <span className="text-[11px] font-bold text-slate-500 mr-1">Profiles & Directories:</span>
                        {lead.facebook_url && (
                          <a href={lead.facebook_url} target="_blank" rel="noreferrer" className="px-2 py-1 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-md text-[10px] font-bold transition-colors">
                            📘 Facebook
                          </a>
                        )}
                        {lead.instagram_url && (
                          <a href={lead.instagram_url} target="_blank" rel="noreferrer" className="px-2 py-1 bg-pink-50 text-pink-700 hover:bg-pink-100 rounded-md text-[10px] font-bold transition-colors">
                            📷 Instagram
                          </a>
                        )}
                        {lead.linkedin_url && (
                          <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="px-2 py-1 bg-sky-50 text-sky-700 hover:bg-sky-100 rounded-md text-[10px] font-bold transition-colors">
                            💼 LinkedIn
                          </a>
                        )}
                        {lead.twitter_url && (
                          <a href={lead.twitter_url} target="_blank" rel="noreferrer" className="px-2 py-1 bg-slate-100 text-slate-800 hover:bg-slate-200 rounded-md text-[10px] font-bold transition-colors">
                            𝕏 Twitter / X
                          </a>
                        )}
                        {lead.youtube_url && (
                          <a href={lead.youtube_url} target="_blank" rel="noreferrer" className="px-2 py-1 bg-red-50 text-red-700 hover:bg-red-100 rounded-md text-[10px] font-bold transition-colors">
                            ▶️ YouTube
                          </a>
                        )}

                        {/* Directory Badges */}
                        {(() => {
                          if (!lead.internal_notes || !lead.internal_notes.includes("[Directories]")) return null;
                          try {
                            const raw = lead.internal_notes.split("[Directories]")[1].split("\n")[0];
                            return raw.split("|").map((item: string, idx: number) => {
                              const [dName, ...uParts] = item.split(":");
                              const dUrl = uParts.join(":").trim();
                              if (!dName || !dUrl.startsWith("http")) return null;
                              return (
                                <a key={idx} href={dUrl} target="_blank" rel="noreferrer" className="px-2 py-1 bg-amber-50 text-amber-800 hover:bg-amber-100 rounded-md text-[10px] font-bold transition-colors border border-amber-200/60">
                                  ⭐ {dName.trim()}
                                </a>
                              );
                            });
                          } catch (e) {
                            return null;
                          }
                        })()}
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
    </div>
  );
}
