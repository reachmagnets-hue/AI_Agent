'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, Search, Plus, Filter, Upload, AlertCircle, Eye, Star, Sparkles, X, Loader2, FileImage, Download } from 'lucide-react';

async function fetchLeads({ search, status, priority, businessType, leadSource, page, leadTab }: { search: string; status: string; priority: string; businessType: string; leadSource: string; page: number; leadTab: string }) {
  let url = `/api/v1/leads/?page=${page}&limit=15`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (status && status !== 'all') url += `&status=${status}`;
  if (priority && priority !== 'all') url += `&priority=${priority}`;
  if (businessType && businessType !== 'all') url += `&business_type=${encodeURIComponent(businessType)}`;
  if (leadSource && leadSource !== 'all') url += `&source=${encodeURIComponent(leadSource)}`;
  
  if (leadTab === 'email') {
    url += '&has_email=true';
  } else if (leadTab === 'linkedin') {
    url += '&has_linkedin=true';
  } else if (leadTab === 'social') {
    url += '&has_social=true';
  } else if (leadTab === 'phone') {
    url += '&has_phone=true';
  }
  
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch leads');
  return res.json();
}

async function uploadLeadsCSV(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  
  const res = await fetch(`/api/v1/leads/import`, {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`Import failed (${res.status}): ${errText}`);
  }
  return res.json();
}

export default function LeadsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [priority, setPriority] = useState('all');
  const [businessType, setBusinessType] = useState('all');
  const [leadSource, setLeadSource] = useState('all');
  const [leadTab, setLeadTab] = useState<'all' | 'phone' | 'email' | 'linkedin' | 'social'>('all');
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const { data: industriesData } = useQuery<{ industries: string[] }>({
    queryKey: ['lead-industries-list'],
    queryFn: async () => {
      const res = await fetch('/api/v1/leads/industries');
      if (!res.ok) throw new Error('Failed to fetch industries');
      return res.json();
    }
  });

  const handleExportCSV = () => {
    let url = `/api/v1/leads/export/csv?`;
    const params = [];
    if (search) params.push(`search=${encodeURIComponent(search)}`);
    if (status && status !== 'all') params.push(`status=${status}`);
    if (priority && priority !== 'all') params.push(`priority=${priority}`);
    
    if (leadTab === 'email') {
      params.push('has_email=true');
    } else if (leadTab === 'linkedin') {
      params.push('has_linkedin=true');
    } else if (leadTab === 'social') {
      params.push('has_social=true');
    } else if (leadTab === 'phone') {
      params.push('has_phone=true');
    }
    
    url += params.join('&');
    window.open(url, '_blank');
  };

  // AI Screenshot Extraction State
  interface QueueItem {
    id: string;
    file: File;
    status: 'ready' | 'processing' | 'success_created' | 'success_merged' | 'error';
    businessName?: string;
    website?: string;
    email?: string;
    error?: string;
  }

  const [screenshotQueue, setScreenshotQueue] = useState<QueueItem[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const filesArray = Array.from(e.dataTransfer.files).filter(
        file => file.type.startsWith('image/')
      );
      
      const newItems: QueueItem[] = filesArray.map(file => ({
        id: Math.random().toString(36).substring(2, 9),
        file,
        status: 'ready'
      }));
      
      setScreenshotQueue(prev => [...prev, ...newItems]);
    }
  };

  const handleScreenshotChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files).filter(
        file => file.type.startsWith('image/')
      );
      
      const newItems: QueueItem[] = filesArray.map(file => ({
        id: Math.random().toString(36).substring(2, 9),
        file,
        status: 'ready'
      }));
      
      setScreenshotQueue(prev => [...prev, ...newItems]);
    }
  };

  const removeQueueItem = (id: string) => {
    setScreenshotQueue(prev => prev.filter(item => item.id !== id));
  };

  const clearQueue = () => {
    setScreenshotQueue([]);
  };

  const startScreenshotExtraction = async () => {
    if (screenshotQueue.length === 0 || isExtracting) return;
    
    setIsExtracting(true);
    
    // Process items sequentially
    for (let i = 0; i < screenshotQueue.length; i++) {
      const item = screenshotQueue[i];
      if (item.status === 'success_created' || item.status === 'success_merged') {
        continue;
      }
      
      setScreenshotQueue(prev => prev.map(q => q.id === item.id ? { ...q, status: 'processing' } : q));
      
      try {
        const formData = new FormData();
        formData.append('files', item.file);
        
        const res = await fetch('/api/v1/leads/extract-screenshots', {
          method: 'POST',
          body: formData
        });
        
        if (!res.ok) {
          const errText = await res.text();
          throw new Error(errText || 'Extraction failed');
        }
        
        const resData = await res.json();
        if (resData.success && resData.results && resData.results.length > 0) {
          const result = resData.results[0];
          const status = result.status === 'created' ? 'success_created' : 'success_merged';
          
          setScreenshotQueue(prev => prev.map(q => q.id === item.id ? { 
            ...q, 
            status, 
            businessName: result.business_name || item.file.name,
            website: result.website || '',
            email: result.email || ''
          } : q));
        } else {
          throw new Error('No details extracted from screenshot');
        }
      } catch (err: any) {
        console.error("Error processing screenshot:", err);
        setScreenshotQueue(prev => prev.map(q => q.id === item.id ? { 
          ...q, 
          status: 'error', 
          error: err.message || 'Error occurred' 
        } : q));
      }
    }
    
    setIsExtracting(false);
    queryClient.invalidateQueries({ queryKey: ['leads'] });
  };

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['leads', { search, status, priority, businessType, leadSource, page, leadTab }],
    queryFn: () => fetchLeads({ search, status, priority, businessType, leadSource, page, leadTab }),
  });

  const importMutation = useMutation({
    mutationFn: uploadLeadsCSV,
    onSuccess: (resData) => {
      if (resData.message) {
        // Backend provided a custom message (email-only import, mixed import, etc.)
        setImportStatus(resData.message);
      } else {
        const parts = [];
        if (resData.imported_phone > 0) parts.push(`${resData.imported_phone} callable leads`);
        if (resData.imported_email > 0) parts.push(`${resData.imported_email} email contacts`);
        const importedStr = parts.length > 0 ? parts.join(' + ') : `${resData.imported} leads`;
        setImportStatus(`✅ Imported ${importedStr}. (${resData.skipped_dnc ?? 0} DNC, ${resData.skipped_duplicate ?? 0} duplicates, ${resData.errors ?? 0} errors)`);
      }
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['lead_sources'] });
      queryClient.invalidateQueries({ queryKey: ['unassigned_leads'] });
      setFile(null);
    },
    onError: (err: any) => {
      setImportStatus(`❌ Import failed: ${err.message}`);
    }
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setImportStatus(null);
    }
  };

  const handleApproveLead = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/leads/${id}/approve`, { method: 'POST' });
      if (res.ok) {
        alert("Lead approved for LinkedIn outreach");
        refetch();
      } else {
        const errorData = await res.json();
        alert(`Error: ${errorData.detail || "Failed to approve lead"}`);
      }
    } catch (err) {
      alert("Failed to approve lead");
    }
  };

  const handleUpload = () => {
    if (file) {
      setImportStatus('Uploading and filtering against DNC registry...');
      importMutation.mutate(file);
    }
  };

  // Safe Fallback Leads data
  const leads = data?.leads || [];
  const total = data?.total || 0;
  const totalPages = data?.pages || 1;
  const stats = data?.stats || { total_pending: 0, total_interested: 0, total_booked: 0, total_not_interested: 0 };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending': return 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20';
      case 'calling': return 'bg-blue-500/10 text-blue-500 border border-blue-500/20';
      case 'interested': return 'bg-green-500/10 text-green-500 border border-green-500/20';
      case 'meeting_booked': return 'bg-purple-500/10 text-purple-500 border border-purple-500/20';
      case 'not_interested': return 'bg-red-500/10 text-red-500 border border-red-500/20';
      default: return 'bg-gray-500/10 text-gray-500 border border-gray-500/20';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'urgent': return 'text-red-500 font-semibold';
      case 'high': return 'text-orange-500';
      case 'normal': return 'text-gray-400';
      default: return 'text-gray-400';
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Users className="h-8 w-8 text-primary" /> Lead Profiles & CRM
        </h1>
        <p className="text-muted-foreground mt-1">Manage leads, track statuses, and audit calling outcomes.</p>
      </div>

      {/* Import & Extraction Hub */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* CSV Import */}
        <Card className="bg-card border-muted-foreground/10 flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Upload className="h-5 w-5 text-primary" /> Bulk Upload CSV Leads
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Import a list of leads using a standard CSV file. Validates and registers leads against the DNC registry automatically.
            </p>
          </CardHeader>
          <CardContent className="pt-2 flex flex-col justify-end flex-grow">
            <div className="flex flex-col gap-2">
              <div className="flex gap-2">
                <Input type="file" accept=".csv" onChange={handleFileChange} className="bg-background text-sm file:text-primary" />
                <Button onClick={handleUpload} disabled={!file || importMutation.isPending} size="sm">
                  {importMutation.isPending ? 'Importing...' : 'Upload'}
                </Button>
              </div>
              {importStatus && (
                <p className="text-xs text-primary mt-1.5 flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" /> {importStatus}
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* AI Screenshot Lead Extractor */}
        <Card className="bg-card border-muted-foreground/10 flex flex-col justify-between">
          <CardHeader>
            <CardTitle className="text-lg font-semibold flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" /> AI Screenshot Lead Extractor
            </CardTitle>
            <p className="text-xs text-muted-foreground">
              Drop Google Ads CRM screenshots here. Gemini will auto-extract client info, merge duplicates, and update calling lists.
            </p>
          </CardHeader>
          <CardContent className="pt-2 flex-grow">
            <div className="space-y-4">
              <div
                onDragEnter={handleDrag}
                onDragOver={handleDrag}
                onDragLeave={handleDrag}
                onDrop={handleDrop}
                onClick={() => document.getElementById('screenshot-file-input')?.click()}
                className={`relative border-2 border-dashed rounded-lg p-5 text-center cursor-pointer transition-all ${
                  dragActive 
                    ? 'border-primary bg-primary/5' 
                    : 'border-muted-foreground/20 hover:border-primary/40 bg-background/20'
                }`}
              >
                <input
                  id="screenshot-file-input"
                  type="file"
                  multiple
                  accept="image/*"
                  onChange={handleScreenshotChange}
                  className="hidden"
                />
                <div className="flex flex-col items-center justify-center gap-2">
                  <div className="p-2.5 rounded-full bg-primary/10 text-primary">
                    <FileImage className="h-5 w-5" />
                  </div>
                  <div>
                    <span className="text-sm font-semibold text-foreground">Click to upload</span>
                    <span className="text-sm text-muted-foreground"> or drag & drop</span>
                  </div>
                  <p className="text-xs text-muted-foreground">PNG, JPG, or WEBP (Max 10MB each)</p>
                </div>
              </div>

              {screenshotQueue.length > 0 && (
                <div className="space-y-3 mt-4">
                  <div className="flex justify-between items-center text-xs">
                    <span className="font-semibold text-muted-foreground">
                      Upload Queue ({screenshotQueue.filter(q => q.status === 'success_created' || q.status === 'success_merged').length}/{screenshotQueue.length})
                    </span>
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={clearQueue} 
                      disabled={isExtracting}
                      className="h-auto p-1 text-muted-foreground hover:text-red-500"
                    >
                      Clear All
                    </Button>
                  </div>
                  
                  <div className="max-h-36 overflow-y-auto space-y-1.5 pr-1 custom-scrollbar">
                    {screenshotQueue.map((item) => (
                      <div 
                        key={item.id} 
                        className="flex items-center justify-between p-2 rounded bg-background border border-muted-foreground/5 text-sm"
                      >
                        <div className="flex items-center gap-2 overflow-hidden mr-2">
                          <FileImage className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                          <span className="truncate text-xs font-medium" title={item.file.name}>
                            {item.file.name}
                          </span>
                        </div>
                        
                        <div className="flex items-center gap-2 shrink-0">
                          {item.status === 'ready' && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-secondary text-secondary-foreground font-semibold">
                              Ready
                            </span>
                          )}
                          {item.status === 'processing' && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-500 border border-blue-500/20 font-semibold flex items-center gap-1">
                              <Loader2 className="h-3 w-3 animate-spin" /> Processing
                            </span>
                          )}
                          {item.status === 'success_created' && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 font-semibold">
                              Created: {item.businessName || 'Lead'}
                            </span>
                          )}
                          {item.status === 'success_merged' && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-purple-500/10 text-purple-500 border border-purple-500/20 font-semibold">
                              Merged: {item.businessName || 'Lead'}
                            </span>
                          )}
                          {item.status === 'error' && (
                            <span 
                              className="text-[10px] px-2 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 font-semibold cursor-help"
                              title={item.error}
                            >
                              Failed
                            </span>
                          )}
                          
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => removeQueueItem(item.id)}
                            disabled={isExtracting}
                            className="h-5 w-5 text-muted-foreground hover:text-red-500"
                          >
                            <X className="h-3 w-3" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  <Button 
                    onClick={startScreenshotExtraction} 
                    disabled={isExtracting || !screenshotQueue.some(q => q.status === 'ready' || q.status === 'error')}
                    className="w-full flex items-center justify-center gap-1.5"
                    size="sm"
                  >
                    {isExtracting ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Extracting Details...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        Extract Lead Details
                      </>
                    )}
                  </Button>

                  {screenshotQueue.some(item => item.status === 'success_created' || item.status === 'success_merged') && (
                    <div className="mt-4 p-3 bg-secondary/20 rounded-lg border border-muted-foreground/10 space-y-2">
                      <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                        <Sparkles className="h-3 w-3 text-primary animate-pulse" /> Extracted E-Mail & Web Directory
                      </h4>
                      <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
                        {screenshotQueue
                          .filter(item => item.status === 'success_created' || item.status === 'success_merged')
                          .map((item) => (
                            <div key={item.id} className="p-2 bg-background/50 rounded border border-muted-foreground/5 text-xs flex flex-col gap-1">
                              <div className="flex justify-between items-center">
                                <span className="font-semibold text-foreground">{item.businessName || 'N/A'}</span>
                                <span className="text-[10px] uppercase font-bold text-primary px-1.5 py-0.2 rounded bg-primary/10">
                                  {item.status === 'success_created' ? 'Created' : 'Merged'}
                                </span>
                              </div>
                              {item.website && (
                                <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  <span className="font-medium text-slate-500">Website:</span>
                                  <a href={item.website.startsWith('http') ? item.website : `https://${item.website}`} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline truncate">
                                    {item.website}
                                  </a>
                                </div>
                              )}
                              {item.email && (
                                <div className="text-[10px] text-muted-foreground flex flex-col gap-0.5 mt-0.5">
                                  <span className="font-medium text-slate-500">Extracted Emails:</span>
                                  <div className="flex flex-wrap gap-1">
                                    {item.email.split(',').map((emailStr, idx) => (
                                      <a key={idx} href={`mailto:${emailStr.trim()}`} className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 font-mono text-[9px] hover:bg-emerald-500/20 transition-colors">
                                        {emailStr.trim()}
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* CRM Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{stats.total_pending}</div>
            <p className="text-xs text-muted-foreground mt-1">Uncalled Pending Leads</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-500">{stats.total_interested}</div>
            <p className="text-xs text-muted-foreground mt-1">Interested Leads</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-purple-500">{stats.total_booked}</div>
            <p className="text-xs text-muted-foreground mt-1">Discovery Meetings Booked</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{total}</div>
            <p className="text-xs text-muted-foreground mt-1">Total System Leads</p>
          </CardContent>
        </Card>
      </div>

      {/* Lead Source Category Selector */}
      <div className="bg-card/40 backdrop-blur-md p-4 rounded-2xl border border-muted-foreground/10 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-extrabold text-foreground flex items-center gap-2">
            <Filter className="h-4 w-4 text-primary" /> Separate Leads by Extraction Source
          </h3>
          <span className="text-xs font-semibold text-muted-foreground">
            Filter by Google Maps, AI Screenshots, CSVs, or LinkedIn
          </span>
        </div>

        <div className="flex flex-wrap gap-2 text-xs font-bold">
          <button
            type="button"
            onClick={() => { setLeadSource('all'); setPage(1); }}
            className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 shadow-sm ${
              leadSource === 'all'
                ? 'bg-primary text-primary-foreground border-primary'
                : 'bg-background text-muted-foreground border-muted-foreground/15 hover:bg-accent'
            }`}
          >
            🌐 All System Leads
          </button>

          <button
            type="button"
            onClick={() => { setLeadSource('gmaps'); setPage(1); }}
            className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 shadow-sm ${
              leadSource === 'gmaps'
                ? 'bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-500/20'
                : 'bg-indigo-50/50 text-indigo-700 border-indigo-200 hover:bg-indigo-100'
            }`}
          >
            📍 Google Maps Extracted
          </button>

          <button
            type="button"
            onClick={() => { setLeadSource('screenshot'); setPage(1); }}
            className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 shadow-sm ${
              leadSource === 'screenshot'
                ? 'bg-purple-600 text-white border-purple-600 ring-2 ring-purple-500/20'
                : 'bg-purple-50/50 text-purple-700 border-purple-200 hover:bg-purple-100'
            }`}
          >
            📸 AI Screenshot Extracted
          </button>

          <button
            type="button"
            onClick={() => { setLeadSource('csv'); setPage(1); }}
            className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 shadow-sm ${
              leadSource === 'csv'
                ? 'bg-emerald-600 text-white border-emerald-600 ring-2 ring-emerald-500/20'
                : 'bg-emerald-50/50 text-emerald-700 border-emerald-200 hover:bg-emerald-100'
            }`}
          >
            📄 CSV Imported
          </button>

          <button
            type="button"
            onClick={() => { setLeadSource('linkedin'); setPage(1); }}
            className={`px-3 py-1.5 rounded-xl border transition-all flex items-center gap-1.5 shadow-sm ${
              leadSource === 'linkedin'
                ? 'bg-sky-600 text-white border-sky-600 ring-2 ring-sky-500/20'
                : 'bg-sky-50/50 text-sky-700 border-sky-200 hover:bg-sky-100'
            }`}
          >
            💼 LinkedIn Prospecting
          </button>
        </div>
      </div>

      {/* Industry Folders Hub */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-extrabold text-foreground flex items-center gap-2">
            <span className="text-lg">📁</span> Industry Lead Folders
          </h3>
          <span className="text-xs font-semibold text-muted-foreground">
            Click any folder to view stored leads for that industry
          </span>
        </div>

        <div className="flex flex-wrap gap-2.5">
          <button
            type="button"
            onClick={() => { setBusinessType('all'); setPage(1); }}
            className={`px-3.5 py-2 rounded-xl border text-xs font-bold transition-all flex items-center gap-2 shadow-sm ${
              businessType === 'all'
                ? 'bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-500/30'
                : 'bg-card text-foreground border-muted-foreground/15 hover:bg-accent/50'
            }`}
          >
            <span>📁 All Industry Folders</span>
            <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-white/20">All</span>
          </button>

          {industriesData?.industries?.map((ind, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => { setBusinessType(ind); setPage(1); }}
              className={`px-3.5 py-2 rounded-xl border text-xs font-bold transition-all flex items-center gap-2 shadow-sm ${
                businessType === ind
                  ? 'bg-indigo-600 text-white border-indigo-600 ring-2 ring-indigo-500/30'
                  : 'bg-card text-foreground border-muted-foreground/15 hover:bg-accent/50'
              }`}
            >
              <span>📁 {ind}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Subsections/Tabs */}
      <div className="flex space-x-2 border-b border-muted-foreground/10 pb-2">
        {(['all', 'phone', 'email', 'linkedin', 'social'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setLeadTab(tab); setPage(1); }}
            className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors border-b-2 capitalize whitespace-nowrap ${
              leadTab === tab 
                ? 'bg-primary/10 text-primary border-primary' 
                : 'text-muted-foreground hover:bg-muted/10 hover:text-foreground border-transparent'
            }`}
          >
            {tab} Leads
          </button>
        ))}
      </div>

      {/* Filter and Table Card */}
      <Card className="bg-card/30 backdrop-blur border-muted-foreground/10">
        <CardHeader>
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="relative w-full md:w-96">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search leads by name, phone, email..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="pl-9 bg-background"
              />
            </div>
            
            <div className="flex gap-4 w-full md:w-auto justify-end">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-muted-foreground" />
                <select
                  value={status}
                  onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                  className="bg-background border rounded px-2.5 py-1.5 text-sm"
                >
                  <option value="all">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="calling">Calling</option>
                  <option value="interested">Interested</option>
                  <option value="meeting_booked">Meeting Booked</option>
                  <option value="not_interested">Not Interested</option>
                  <option value="no_answer">No Answer</option>
                  <option value="voicemail">Voicemail</option>
                  <option value="follow_up">Follow Up</option>
                  <option value="closed_won">Closed Won</option>
                  <option value="closed_lost">Closed Lost</option>
                </select>
              </div>

              <select
                value={priority}
                onChange={(e) => { setPriority(e.target.value); setPage(1); }}
                className="bg-background border rounded px-2.5 py-1.5 text-sm font-medium"
              >
                <option value="all">All Priorities</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>

              {/* Industry Filter Dropdown */}
              <select
                value={businessType}
                onChange={(e) => { setBusinessType(e.target.value); setPage(1); }}
                className="bg-background border rounded px-2.5 py-1.5 text-sm font-medium capitalize"
              >
                <option value="all">All Industries</option>
                {industriesData?.industries?.map((ind, idx) => (
                  <option key={idx} value={ind}>{ind}</option>
                ))}
              </select>

              <Button
                variant="outline"
                onClick={handleExportCSV}
                className="flex items-center gap-1.5 bg-background font-bold text-xs h-[38px] hover:bg-muted/10 transition-colors"
              >
                <Download className="h-4 w-4" /> Export CSV
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center p-8 text-muted-foreground">Loading leads list...</div>
          ) : error ? (
            <div className="flex justify-center p-8 text-red-500">Error loading leads.</div>
          ) : leads.length === 0 ? (
            <div className="flex flex-col justify-center items-center p-12 text-muted-foreground gap-2">
              <AlertCircle className="h-8 w-8 text-primary" /> No leads found matching the filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prospect Name</TableHead>
                    <TableHead>Business Name</TableHead>
                    <TableHead>Campaign</TableHead>
                    <TableHead>Website</TableHead>
                    <TableHead>Phone</TableHead>
                    <TableHead>Email</TableHead>
                    <TableHead>Email Status</TableHead>
                    <TableHead>Social Media Profiles</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>LI Status</TableHead>
                    <TableHead>Priority</TableHead>
                    <TableHead>Decision Maker</TableHead>
                    <TableHead>Score</TableHead>
                    <TableHead>Last Contacted</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {leads.map((lead: any) => (
                    <TableRow key={lead.id} className="hover:bg-accent/40 transition-colors">
                      <TableCell className="font-semibold">{lead.full_name || 'N/A'}</TableCell>
                      <TableCell>{lead.business_name || 'N/A'}</TableCell>
                      <TableCell>
                        {lead.campaign_name ? (
                          <span className="font-medium text-slate-700 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded text-xs">
                            {lead.campaign_name}
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-xs italic">Unassigned</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {lead.website ? (
                          <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline font-medium text-xs truncate max-w-[120px]" title={lead.website}>
                            {lead.website}
                          </a>
                        ) : (
                          <span className="text-muted-foreground text-xs">--</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm font-mono whitespace-nowrap">
                        {lead.phone || <span className="text-muted-foreground italic text-xs">No Phone</span>}
                      </TableCell>
                      <TableCell className="text-xs font-mono">
                        {lead.email ? (
                          <a href={`mailto:${lead.email}`} className="text-primary hover:underline truncate max-w-[120px] block" title={lead.email}>
                            {lead.email}
                          </a>
                        ) : (
                          <span className="text-muted-foreground italic text-xs">No Email</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {lead.email_status ? (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border whitespace-nowrap ${
                            lead.email_status === 'opened' ? 'bg-purple-500/10 text-purple-500 border-purple-500/20' : 
                            lead.email_status === 'clicked' ? 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20' :
                            lead.email_status === 'delivered' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                            lead.email_status === 'sent' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' :
                            lead.email_status === 'bounced' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                            'bg-red-500/10 text-red-500 border-red-500/20'
                          }`}>
                            {lead.email_status}
                          </span>
                        ) : lead.email ? (
                          <span className="text-muted-foreground text-xs italic">Not Sent</span>
                        ) : (
                          <span className="text-muted-foreground text-xs">--</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap items-center gap-1 min-w-[130px]">
                          {lead.facebook_url && (
                            <a href={lead.facebook_url} target="_blank" rel="noopener noreferrer" title={`Facebook: ${lead.facebook_url}`} className="p-1 rounded bg-blue-500/10 text-blue-600 hover:bg-blue-500/20 text-xs font-bold transition-colors">
                              📘 FB
                            </a>
                          )}
                          {lead.instagram_url && (
                            <a href={lead.instagram_url} target="_blank" rel="noopener noreferrer" title={`Instagram: ${lead.instagram_url}`} className="p-1 rounded bg-pink-500/10 text-pink-600 hover:bg-pink-500/20 text-xs font-bold transition-colors">
                              📷 IG
                            </a>
                          )}
                          {lead.linkedin_url && (
                            <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" title={`LinkedIn: ${lead.linkedin_url}`} className="p-1 rounded bg-sky-500/10 text-sky-600 hover:bg-sky-500/20 text-xs font-bold transition-colors">
                              💼 LI
                            </a>
                          )}
                          {lead.twitter_url && (
                            <a href={lead.twitter_url} target="_blank" rel="noopener noreferrer" title={`Twitter/X: ${lead.twitter_url}`} className="p-1 rounded bg-slate-500/10 text-slate-700 dark:text-slate-300 hover:bg-slate-500/20 text-xs font-bold transition-colors">
                              𝕏 TW
                            </a>
                          )}
                          {lead.youtube_url && (
                            <a href={lead.youtube_url} target="_blank" rel="noopener noreferrer" title={`YouTube: ${lead.youtube_url}`} className="p-1 rounded bg-red-500/10 text-red-600 hover:bg-red-500/20 text-xs font-bold transition-colors">
                              ▶️ YT
                            </a>
                          )}
                          {(() => {
                            if (!lead.internal_notes || !lead.internal_notes.includes("[Directories]")) return null;
                            try {
                              const raw = lead.internal_notes.split("[Directories]")[1].split("\n")[0];
                              return raw.split("|").map((item: string, idx: number) => {
                                const [dName, ...uParts] = item.split(":");
                                const dUrl = uParts.join(":").trim();
                                if (!dName || !dUrl.startsWith("http")) return null;
                                return (
                                  <a key={idx} href={dUrl} target="_blank" rel="noopener noreferrer" title={`${dName.trim()}: ${dUrl}`} className="p-1 rounded bg-amber-500/10 text-amber-600 hover:bg-amber-500/20 text-xs font-bold transition-colors border border-amber-500/20">
                                    ⭐ {dName.trim().slice(0, 4)}
                                  </a>
                                );
                              });
                            } catch (e) {
                              return null;
                            }
                          })()}
                          {!lead.facebook_url && !lead.instagram_url && !lead.linkedin_url && !lead.twitter_url && !lead.youtube_url && (!lead.internal_notes || !lead.internal_notes.includes("[Directories]")) && (
                            <span className="text-muted-foreground text-xs">--</span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColor(lead.status || 'pending')}`}>
                          {(lead.status || 'pending').replace('_', ' ')}
                        </span>
                      </TableCell>
                      <TableCell>
                        {lead.linkedin_url && lead.linkedin_status ? (
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider border whitespace-nowrap ${
                            lead.linkedin_status === 'approved' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 
                            lead.linkedin_status === 'pending_approval' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' :
                            lead.linkedin_status === 'connected' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' :
                            lead.linkedin_status === 'message_sent' ? 'bg-purple-500/10 text-purple-500 border-purple-500/20' :
                            'bg-gray-500/10 text-gray-400 border-gray-500/20'
                          }`}>
                            {lead.linkedin_status.replace('_', ' ')}
                          </span>
                        ) : (
                          <span className="text-muted-foreground text-xs">--</span>
                        )}
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className={getPriorityColor(lead.priority)}>{lead.priority}</span>
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const isDM = lead.internal_notes?.includes("Decision Maker: Yes") ? "Yes" : 
                                       lead.internal_notes?.includes("Decision Maker: No") ? "No" : "Uncertain";
                          if (isDM === "Yes") return <span className="px-2 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 text-xs font-semibold">Yes</span>;
                          if (isDM === "No") return <span className="px-2 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-xs font-semibold">No</span>;
                          return <span className="text-gray-400 text-xs font-medium">Uncertain</span>;
                        })()}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col gap-1">
                          <div className="flex items-center gap-1 text-yellow-500">
                            <Star className="h-3.5 w-3.5 fill-current" />
                            <span className="text-sm font-bold">{lead.lead_score || 0}</span>
                          </div>
                          {lead.lead_score > 0 && (
                            <span className={`text-[10px] px-1.5 py-0.2 rounded font-bold uppercase w-max ${
                              lead.lead_score >= 80 ? 'bg-green-100 text-green-800' :
                              lead.lead_score >= 40 ? 'bg-amber-100 text-amber-800' : 'bg-slate-100 text-slate-700'
                            }`}>
                              {lead.lead_score >= 80 ? 'Hot' : lead.lead_score >= 40 ? 'Warm' : 'Cold'}
                            </span>
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {lead.last_called_at ? new Date(lead.last_called_at).toLocaleString() : 'Never'}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {lead.linkedin_status === 'pending_approval' && lead.linkedin_url && (
                            <Button size="sm" variant="outline" className="h-8 border-blue-500/50 text-blue-500 hover:bg-blue-500/10 hover:text-blue-400" onClick={() => handleApproveLead(lead.id)}>
                              Approve LinkedIn
                            </Button>
                          )}
                          <Link href={`/leads/${lead.id}`}>
                            <Button size="sm" variant="ghost" className="flex items-center gap-1 hover:text-primary">
                              <Eye className="h-4 w-4" /> Profile
                            </Button>
                          </Link>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex justify-between items-center mt-6">
              <span className="text-xs text-muted-foreground">Showing page {page} of {totalPages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setPage(p => Math.max(p - 1, 1))} disabled={page === 1}>Previous</Button>
                <Button size="sm" variant="outline" onClick={() => setPage(p => Math.min(p + 1, totalPages))} disabled={page === totalPages}>Next</Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
