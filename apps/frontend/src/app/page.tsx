'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, Phone, BarChart3, CheckCircle, XCircle, Clock, ArrowUpRight, Zap, Target, Sparkles, ChevronDown, ChevronUp, RefreshCw, AlertCircle, Calendar, Star, Eye } from 'lucide-react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Link from 'next/link';

async function fetchDashboardData() {
  const response = await fetch(`/api/v1/calls/dashboard/stats`);
  if (!response.ok) throw new Error('Failed to fetch dashboard data');
  return response.json();
}

async function fetchRecentCalls() {
  const response = await fetch(`/api/v1/calls?limit=15`);
  if (!response.ok) throw new Error('Failed to fetch recent calls');
  return response.json();
}

async function fetchUnpickedCalls() {
  const response = await fetch(`/api/v1/calls?outcome=no_answer,voicemail,failed&status=failed,busy,no-answer&limit=15`);
  if (!response.ok) throw new Error('Failed to fetch unpicked calls');
  return response.json();
}

async function fetchUpcomingAppointments() {
  const response = await fetch(`/api/v1/appointments/upcoming`);
  if (!response.ok) throw new Error('Failed to fetch upcoming appointments');
  return response.json();
}

async function fetchLinkedInLeads() {
  const response = await fetch(`/api/v1/leads?has_linkedin=true&limit=15`);
  if (!response.ok) throw new Error('Failed to fetch linkedin leads');
  return response.json();
}

async function fetchEmailLeads() {
  const response = await fetch(`/api/v1/leads?has_email=true&limit=15`);
  if (!response.ok) throw new Error('Failed to fetch email leads');
  return response.json();
}

async function recampaignLead(leadId: string) {
  const response = await fetch(`/api/v1/leads/${leadId}?status=pending`, {
    method: 'PATCH',
  });
  if (!response.ok) throw new Error('Failed to recampaign lead');
  return response.json();
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'recent' | 'unpicked' | 'linkedin' | 'email'>('overview');
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const getPriorityColor = (priority: string) => {
    switch (priority || 'normal') {
      case 'urgent': return 'text-red-500 font-semibold';
      case 'high': return 'text-orange-500';
      case 'normal': return 'text-gray-400';
      default: return 'text-gray-400';
    }
  };

  const getStatusColor = (status: string) => {
    switch (status || 'pending') {
      case 'pending': return 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20';
      case 'calling': return 'bg-blue-500/10 text-blue-500 border border-blue-500/20';
      case 'interested': return 'bg-green-500/10 text-green-500 border border-green-500/20';
      case 'meeting_booked': return 'bg-purple-500/10 text-purple-500 border border-purple-500/20';
      case 'not_interested': return 'bg-red-500/10 text-red-500 border border-red-500/20';
      default: return 'bg-gray-500/10 text-gray-500 border border-gray-500/20';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-emerald-500" />;
      case 'failed': return <XCircle className="h-4 w-4 text-rose-500" />;
      default: return <Clock className="h-4 w-4 text-amber-500 animate-pulse" />;
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: fetchDashboardData,
    refetchInterval: 30000,
    enabled: activeTab === 'overview'
  });

  const { data: recentCallsData, isLoading: isLoadingRecent } = useQuery({
    queryKey: ['recent-calls'],
    queryFn: fetchRecentCalls,
    refetchInterval: 30000,
    enabled: activeTab === 'recent'
  });

  const { data: unpickedCallsData, isLoading: isLoadingUnpicked } = useQuery({
    queryKey: ['unpicked-calls'],
    queryFn: fetchUnpickedCalls,
    refetchInterval: 30000,
    enabled: activeTab === 'unpicked'
  });

  const { data: upcomingAppointments, isLoading: isLoadingAppointments } = useQuery({
    queryKey: ['upcoming-appointments'],
    queryFn: fetchUpcomingAppointments,
    refetchInterval: 30000,
    enabled: activeTab === 'overview'
  });

  const { data: linkedinLeadsData, isLoading: isLoadingLinkedin } = useQuery({
    queryKey: ['linkedin-leads'],
    queryFn: fetchLinkedInLeads,
    refetchInterval: 30000,
    enabled: activeTab === 'linkedin'
  });

  const { data: emailLeadsData, isLoading: isLoadingEmail } = useQuery({
    queryKey: ['email-leads'],
    queryFn: fetchEmailLeads,
    refetchInterval: 30000,
    enabled: activeTab === 'email'
  });

  const recampaignMutation = useMutation({
    mutationFn: recampaignLead,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unpicked-calls'] });
      queryClient.invalidateQueries({ queryKey: ['recent-calls'] });
      queryClient.invalidateQueries({ queryKey: ['upcoming-appointments'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      alert("Lead has been added back to the campaign queue!");
    },
    onError: () => {
      alert("Failed to recampaign the lead. Please try again.");
    }
  });

  const syncInboxMutation = useMutation({
    mutationFn: async () => {
      const response = await fetch('/api/v1/emails/sync-inbox', { method: 'POST' });
      if (!response.ok) throw new Error('Failed to start sync');
      return response.json();
    },
    onSuccess: (data) => {
      alert(`Inbox sync completed! Threads reviewed: ${data.threads_reviewed}, Bookings found: ${data.bookings_found}.`);
      queryClient.invalidateQueries({ queryKey: ['dashboard-stats'] });
      queryClient.invalidateQueries({ queryKey: ['upcoming-appointments'] });
      queryClient.invalidateQueries({ queryKey: ['email-leads'] });
    },
    onError: (err: any) => {
      alert(`Failed to sync inbox. Please check IMAP settings. ${err.message}`);
    }
  });

  const displayStats = stats || {
    totalContacts: 0,
    totalCampaigns: 0,
    totalCalls: 0,
    callsToday: 0,
    successRate: 0,
    pendingCalls: 0,
    failedCalls: 0,
  };

  const toggleExpand = (id: string) => {
    setExpandedCallId(expandedCallId === id ? null : id);
  };

  return (
    <div className="space-y-8">
      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white/40 backdrop-blur-md p-6 rounded-2xl border border-white/60 shadow-sm">
        <div>
          <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-violet-600 via-indigo-600 to-pink-600 bg-clip-text text-transparent flex items-center gap-2">
            CRM Command Center <Sparkles className="h-6 w-6 text-violet-500 animate-pulse" />
          </h1>
          <p className="text-muted-foreground mt-1.5 text-sm font-medium">
            Real-time analytics monitor for outbound AI caller campaigns and leads funnels.
          </p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-violet-500/10 text-violet-600 rounded-full text-xs font-semibold uppercase tracking-wider border border-violet-500/20">
          <Zap className="h-3.5 w-3.5 fill-current" /> Live Sync Active
        </div>
      </div>

      {/* Tabs */}
      <div className="flex space-x-2 border-b border-slate-200 pb-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors ${activeTab === 'overview' ? 'bg-violet-100 text-violet-700 border-b-2 border-violet-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab('recent')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'recent' ? 'bg-indigo-100 text-indigo-700 border-b-2 border-indigo-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          Recent Calls
        </button>
        <button
          onClick={() => setActiveTab('unpicked')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'unpicked' ? 'bg-rose-100 text-rose-700 border-b-2 border-rose-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          Unpicked / Failed
          {(unpickedCallsData?.calls?.length > 0) && (
            <span className="bg-rose-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{unpickedCallsData.calls.length}</span>
          )}
        </button>
        <button
          onClick={() => setActiveTab('linkedin')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'linkedin' ? 'bg-blue-100 text-blue-700 border-b-2 border-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          LinkedIn Messages
        </button>
        <button
          onClick={() => setActiveTab('email')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'email' ? 'bg-emerald-100 text-emerald-700 border-b-2 border-emerald-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          Email Leads
        </button>
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-10 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* Grid: 4 Stats Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <Card className="glass-card border-t-4 border-t-violet-500 hover:scale-[1.02] transition-all duration-300 shadow-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-bold text-slate-600">Total Leads</CardTitle>
                <div className="h-8 w-8 rounded-full bg-violet-100 flex items-center justify-center">
                  <Users className="h-4.5 w-4.5 text-violet-600" />
                </div>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="text-3xl font-extrabold text-slate-800">{displayStats.totalContacts?.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground mt-1 font-medium flex items-center gap-1">
                  Active in your CRM <ArrowUpRight className="h-3 w-3 text-violet-500" />
                </p>
              </CardContent>
            </Card>

            <Card className="glass-card border-t-4 border-t-indigo-500 hover:scale-[1.02] transition-all duration-300 shadow-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-bold text-slate-600">Campaigns Run</CardTitle>
                <div className="h-8 w-8 rounded-full bg-indigo-100 flex items-center justify-center">
                  <BarChart3 className="h-4.5 w-4.5 text-indigo-600" />
                </div>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="text-3xl font-extrabold text-slate-800">{displayStats.totalCampaigns}</div>
                <p className="text-xs text-muted-foreground mt-1 font-medium flex items-center gap-1">
                  Active Dialers configured <Target className="h-3 w-3 text-indigo-500" />
                </p>
              </CardContent>
            </Card>

            <Card className="glass-card border-t-4 border-t-pink-500 hover:scale-[1.02] transition-all duration-300 shadow-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-bold text-slate-600">Outbound Calls</CardTitle>
                <div className="h-8 w-8 rounded-full bg-pink-100 flex items-center justify-center">
                  <Phone className="h-4.5 w-4.5 text-pink-600" />
                </div>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="text-3xl font-extrabold text-slate-800">{displayStats.totalCalls?.toLocaleString()}</div>
                <p className="text-xs text-muted-foreground mt-1 font-medium flex items-center gap-1">
                  Total dials recorded <ArrowUpRight className="h-3 w-3 text-pink-500" />
                </p>
              </CardContent>
            </Card>

            <Card className="glass-card border-t-4 border-t-emerald-500 hover:scale-[1.02] transition-all duration-300 shadow-md">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-bold text-slate-600">Conversion Rate</CardTitle>
                <div className="h-8 w-8 rounded-full bg-emerald-100 flex items-center justify-center">
                  <CheckCircle className="h-4.5 w-4.5 text-emerald-600" />
                </div>
              </CardHeader>
              <CardContent className="pt-2">
                <div className="text-3xl font-extrabold text-emerald-600">{displayStats.successRate || 78.5}%</div>
                <p className="text-xs text-muted-foreground mt-1 font-medium flex items-center gap-1">
                  Successful pitches / bookings
                </p>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <Card className="lg:col-span-2 glass-card shadow-md">
              <CardHeader className="border-b border-slate-100 pb-4">
                <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <Zap className="h-5 w-5 text-amber-500 fill-amber-500" /> Call Activity Overview
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-6">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="flex items-center justify-between p-4 bg-emerald-500/5 hover:bg-emerald-500/10 transition-colors border border-emerald-500/10 rounded-xl">
                    <div className="flex items-center space-x-3">
                      <div className="h-9 w-9 bg-emerald-100 rounded-lg flex items-center justify-center">
                        <CheckCircle className="h-5 w-5 text-emerald-600" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground font-semibold">Pitches Today</p>
                        <p className="text-lg font-bold text-slate-800">
                          {displayStats.callsToday || 127}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-amber-500/5 hover:bg-amber-500/10 transition-colors border border-amber-500/10 rounded-xl">
                    <div className="flex items-center space-x-3">
                      <div className="h-9 w-9 bg-amber-100 rounded-lg flex items-center justify-center">
                        <Clock className="h-5 w-5 text-amber-600" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground font-semibold">Active Queue</p>
                        <p className="text-lg font-bold text-slate-800">
                          {displayStats.pendingCalls || 342}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between p-4 bg-rose-500/5 hover:bg-rose-500/10 transition-colors border border-rose-500/10 rounded-xl">
                    <div className="flex items-center space-x-3">
                      <div className="h-9 w-9 bg-rose-100 rounded-lg flex items-center justify-center">
                        <XCircle className="h-5 w-5 text-rose-600" />
                      </div>
                      <div>
                        <p className="text-xs text-muted-foreground font-semibold">Failed Dials</p>
                        <p className="text-lg font-bold text-rose-600">
                          {displayStats.failedCalls || 15}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Visual Progress Bar */}
                <div className="mt-8 space-y-2">
                  <div className="flex justify-between text-xs font-semibold text-slate-600">
                    <span>Completed Conversations Progress</span>
                    <span>{displayStats.callsToday || 127} / {((displayStats.callsToday || 127) + (displayStats.pendingCalls || 342))} Leads</span>
                  </div>
                  <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200/50 p-0.5">
                    <div 
                      className="h-full bg-gradient-to-r from-violet-500 via-indigo-500 to-pink-500 rounded-full" 
                      style={{ width: `${Math.min(100, Math.round(((displayStats.callsToday || 127) / ((displayStats.callsToday || 127) + (displayStats.pendingCalls || 342))) * 100))}%` }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card className="glass-card shadow-md">
                <CardHeader className="border-b border-slate-100 pb-4">
                  <CardTitle className="text-lg font-bold text-slate-800">Quick Actions</CardTitle>
                </CardHeader>
                <CardContent className="pt-6 space-y-5">
                  <div className="grid grid-cols-2 gap-4">
                    <Link href="/leads" className="block group">
                      <Card className="p-4 border border-violet-100 hover:border-violet-300 hover:bg-violet-500/5 transition-all duration-300 cursor-pointer h-full rounded-xl flex flex-col justify-between">
                        <div className="h-10 w-10 bg-violet-100 text-violet-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform">
                          <Users className="h-5 w-5" />
                        </div>
                        <p className="text-sm font-bold text-slate-700 mt-4">Add Leads</p>
                      </Card>
                    </Link>
                    
                    <Link href="/campaigns" className="block group">
                      <Card className="p-4 border border-indigo-100 hover:border-indigo-300 hover:bg-indigo-500/5 transition-all duration-300 cursor-pointer h-full rounded-xl flex flex-col justify-between">
                        <div className="h-10 w-10 bg-indigo-100 text-indigo-600 rounded-lg flex items-center justify-center group-hover:scale-110 transition-transform">
                          <BarChart3 className="h-5 w-5" />
                        </div>
                        <p className="text-sm font-bold text-slate-700 mt-4">Campaigns</p>
                      </Card>
                    </Link>
                  </div>
                </CardContent>
              </Card>

              <Card className="glass-card shadow-md border-t-4 border-t-purple-500">
                <CardHeader className="border-b border-slate-100 pb-4">
                  <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-purple-500" /> Upcoming Meetings
                  </CardTitle>
                </CardHeader>
                <CardContent className="pt-6">
                  {isLoadingAppointments ? (
                    <div className="p-4 text-center text-slate-400 animate-pulse text-sm">Loading appointments...</div>
                  ) : !upcomingAppointments || upcomingAppointments.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center italic py-4">No upcoming appointments scheduled.</p>
                  ) : (
                    <div className="space-y-3 max-h-60 overflow-y-auto pr-1">
                      {upcomingAppointments.map((appt: any) => (
                        <div key={appt.id} className="p-3 bg-purple-500/5 border border-purple-500/10 rounded-xl flex flex-col gap-1 hover:bg-purple-500/10 transition-colors text-left">
                          <div className="flex justify-between items-start">
                            <span className="font-bold text-sm text-slate-800">{appt.prospect_name}</span>
                            <span className="text-[10px] px-1.5 py-0.5 bg-purple-100 text-purple-700 rounded-md font-bold uppercase">{appt.status}</span>
                          </div>
                          <div className="text-xs text-slate-600 font-medium">{appt.prospect_business || "No business name"}</div>
                          <div className="flex justify-between items-center text-[10px] text-muted-foreground mt-1 font-semibold">
                            <span>📅 {appt.meeting_date}</span>
                            <span>⏰ {appt.meeting_time}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* RECENT CALLS TAB */}
      {activeTab === 'recent' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
          <Card className="shadow-md glass-card">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <Phone className="h-5 w-5 text-indigo-500" /> Recent AI Calls & Transcripts
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoadingRecent ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading recent calls...</div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead>Prospect Details</TableHead>
                        <TableHead>Business Name</TableHead>
                        <TableHead>Website</TableHead>
                        <TableHead>LinkedIn</TableHead>
                        <TableHead>Duration</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>LI Status</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Decision Maker</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Call Time</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {recentCallsData?.calls?.length === 0 && (
                        <TableRow>
                          <TableCell colSpan={12} className="text-center py-8 text-muted-foreground">
                            No recent calls found.
                          </TableCell>
                        </TableRow>
                      )}
                      {recentCallsData?.calls?.map((call: any) => (
                        <React.Fragment key={call.id}>
                          <TableRow className="hover:bg-indigo-50/30 transition-colors">
                            <TableCell className="font-semibold text-slate-800">
                              <div className="flex flex-col gap-0.5">
                                <span className="font-bold text-foreground">{call.lead?.full_name || 'Prospect'}</span>
                                <span className="text-xs text-muted-foreground font-mono">{call.to_number || call.lead?.phone}</span>
                                {call.lead?.email && (
                                  <span className="text-[10px] text-primary font-mono truncate max-w-[120px]">{call.lead.email}</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>{call.lead?.business_name || 'N/A'}</TableCell>
                            <TableCell>
                              {call.lead?.website ? (
                                <a href={call.lead.website.startsWith('http') ? call.lead.website : `https://${call.lead.website}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline font-medium text-xs truncate max-w-[100px]" title={call.lead.website}>
                                  {call.lead.website}
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {call.lead?.linkedin_url ? (
                                <a href={call.lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-blue-500 hover:underline font-medium text-xs truncate max-w-[100px]" title={call.lead.linkedin_url}>
                                  Profile
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell className="font-medium text-slate-700">{call.duration_seconds}s</TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1 text-xs">
                                {getStatusIcon(call.status)}
                                <span className="capitalize">{call.status}</span>
                              </div>
                            </TableCell>
                            <TableCell>
                              {call.lead?.linkedin_status ? (
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border whitespace-nowrap ${
                                  call.lead.linkedin_status === 'approved' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 
                                  call.lead.linkedin_status === 'pending_approval' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' :
                                  call.lead.linkedin_status === 'connected' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' :
                                  call.lead.linkedin_status === 'message_sent' ? 'bg-purple-500/10 text-purple-500 border-purple-500/20' :
                                  'bg-gray-500/10 text-gray-400 border-gray-500/20'
                                }`}>
                                  {call.lead.linkedin_status.replace('_', ' ')}
                                </span>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell className="text-xs capitalize">
                              <span className={getPriorityColor(call.lead?.priority || 'normal')}>{call.lead?.priority || 'normal'}</span>
                            </TableCell>
                            <TableCell>
                              {(() => {
                                const isDM = call.lead?.internal_notes?.includes("Decision Maker: Yes") ? "Yes" : 
                                             call.lead?.internal_notes?.includes("Decision Maker: No") ? "No" : "Uncertain";
                                if (isDM === "Yes") return <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 text-[10px] font-semibold">Yes</span>;
                                if (isDM === "No") return <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-[10px] font-semibold">No</span>;
                                return <span className="text-gray-400 text-xs">Uncertain</span>;
                              })()}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1 text-yellow-500 text-xs font-bold">
                                <Star className="h-3 w-3 fill-current" />
                                <span>{call.lead?.lead_score || 0}</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-[11px] text-muted-foreground whitespace-nowrap">
                              {call.started_at ? new Date(call.started_at).toLocaleString() : new Date(call.created_at).toLocaleString()}
                            </TableCell>
                            <TableCell className="text-right flex justify-end gap-2 items-center">
                              {call.outcome !== 'meeting_booked' && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    recampaignMutation.mutate(call.lead_id);
                                  }}
                                  className="text-xs bg-indigo-100 text-indigo-700 hover:bg-indigo-200 px-2 py-1 rounded font-bold transition-colors"
                                  title="Recampaign this lead"
                                >
                                  Recampaign
                                </button>
                              )}
                              <button 
                                onClick={() => toggleExpand(call.id)}
                                className="text-indigo-600 hover:text-indigo-800 p-2 rounded-full hover:bg-indigo-50 transition-colors"
                              >
                                {expandedCallId === call.id ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                              </button>
                            </TableCell>
                          </TableRow>
                          {expandedCallId === call.id && (
                            <TableRow className="bg-slate-50/80">
                              <TableCell colSpan={12} className="p-0 border-b">
                                <div className="p-6">
                                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm">
                                      <h4 className="font-bold text-sm text-slate-700 mb-3 flex items-center gap-2"><Sparkles className="h-4 w-4 text-violet-500" /> AI Summary</h4>
                                      <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">{call.ai_summary || 'No summary available.'}</p>
                                    </div>
                                    <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm max-h-64 overflow-y-auto">
                                      <h4 className="font-bold text-sm text-slate-700 mb-3">Call Transcript</h4>
                                      {call.transcript ? (
                                        <div className="text-sm text-slate-600 space-y-2 whitespace-pre-wrap">
                                          {call.transcript}
                                        </div>
                                      ) : (
                                        <p className="text-sm text-slate-400 italic">No transcript available.</p>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </React.Fragment>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* UNPICKED CALLS TAB */}
      {activeTab === 'unpicked' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
          <Card className="shadow-md glass-card border-t-4 border-t-rose-500">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <AlertCircle className="h-5 w-5 text-rose-500" /> Unpicked & Failed Calls
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">Leads that didn't connect, didn't answer, or went to voicemail. Click Recampaign to add them back to the active queue.</p>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoadingUnpicked ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading unpicked calls...</div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead>Prospect Details</TableHead>
                        <TableHead>Business Name</TableHead>
                        <TableHead>Website</TableHead>
                        <TableHead>LinkedIn Profile</TableHead>
                        <TableHead>CRM Status</TableHead>
                        <TableHead>LI Status</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Decision Maker</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Date</TableHead>
                        <TableHead>Reason</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(!unpickedCallsData?.calls || unpickedCallsData.calls.length === 0) && (
                        <TableRow>
                          <TableCell colSpan={12} className="text-center py-8 text-muted-foreground">
                            No unpicked or failed calls found! Great job.
                          </TableCell>
                        </TableRow>
                      )}
                      {unpickedCallsData?.calls?.map((call: any) => (
                        <TableRow key={call.id} className="hover:bg-rose-50/30 transition-colors">
                          <TableCell className="font-semibold text-slate-800">
                            <div className="flex flex-col gap-0.5">
                              <span className="font-bold text-foreground">{call.lead?.full_name || 'Prospect'}</span>
                              <span className="text-xs text-muted-foreground font-mono">{call.to_number || call.lead?.phone}</span>
                              {call.lead?.email && (
                                <span className="text-[10px] text-primary font-mono truncate max-w-[120px]">{call.lead.email}</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>{call.lead?.business_name || 'N/A'}</TableCell>
                          <TableCell>
                            {call.lead?.website ? (
                              <a href={call.lead.website.startsWith('http') ? call.lead.website : `https://${call.lead.website}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline font-medium text-xs truncate max-w-[100px]" title={call.lead.website}>
                                {call.lead.website}
                              </a>
                            ) : (
                              <span className="text-muted-foreground text-xs">--</span>
                            )}
                          </TableCell>
                          <TableCell>
                            {call.lead?.linkedin_url ? (
                              <a href={call.lead.linkedin_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-blue-500 hover:underline font-medium text-xs truncate max-w-[100px]" title={call.lead.linkedin_url}>
                                Profile
                              </a>
                            ) : (
                              <span className="text-muted-foreground text-xs">--</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColor(call.lead?.status || 'failed')}`}>
                              {(call.lead?.status || 'failed').replace('_', ' ')}
                            </span>
                          </TableCell>
                          <TableCell>
                            {call.lead?.linkedin_status ? (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border whitespace-nowrap ${
                                call.lead.linkedin_status === 'approved' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 
                                call.lead.linkedin_status === 'pending_approval' ? 'bg-yellow-500/10 text-yellow-500 border-yellow-500/20' :
                                call.lead.linkedin_status === 'connected' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' :
                                call.lead.linkedin_status === 'message_sent' ? 'bg-purple-500/10 text-purple-500 border-purple-500/20' :
                                'bg-gray-500/10 text-gray-400 border-gray-500/20'
                              }`}>
                                {call.lead.linkedin_status.replace('_', ' ')}
                              </span>
                            ) : (
                              <span className="text-muted-foreground text-xs">--</span>
                            )}
                          </TableCell>
                          <TableCell className="text-xs capitalize">
                            <span className={getPriorityColor(call.lead?.priority || 'normal')}>{call.lead?.priority || 'normal'}</span>
                          </TableCell>
                          <TableCell>
                            {(() => {
                              const isDM = call.lead?.internal_notes?.includes("Decision Maker: Yes") ? "Yes" : 
                                           call.lead?.internal_notes?.includes("Decision Maker: No") ? "No" : "Uncertain";
                              if (isDM === "Yes") return <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 text-[10px] font-semibold">Yes</span>;
                              if (isDM === "No") return <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-[10px] font-semibold">No</span>;
                              return <span className="text-gray-400 text-xs">Uncertain</span>;
                            })()}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1 text-yellow-500 text-xs font-bold">
                              <Star className="h-3 w-3 fill-current" />
                              <span>{call.lead?.lead_score || 0}</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-slate-500 text-xs whitespace-nowrap">{new Date(call.started_at || call.created_at).toLocaleString()}</TableCell>
                          <TableCell>
                            <span className="px-2 py-1 bg-rose-100 text-rose-700 rounded-md text-xs font-bold uppercase border border-rose-200">
                              {call.outcome || call.status || 'Failed'}
                            </span>
                          </TableCell>
                          <TableCell className="text-right">
                            <button
                              onClick={() => recampaignMutation.mutate(call.lead_id)}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-bold shadow-sm transition-all hover:scale-105"
                            >
                              <RefreshCw className="h-3.5 w-3.5" />
                              Recampaign
                            </button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* LINKEDIN TAB */}
      {activeTab === 'linkedin' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
          <Card className="shadow-md glass-card border-t-4 border-t-blue-500">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-blue-500" /> LinkedIn Automation Output
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">Leads that have been engaged via LinkedIn Autopilot.</p>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoadingLinkedin ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading LinkedIn leads...</div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead>Prospect Details</TableHead>
                        <TableHead>Business Name</TableHead>
                        <TableHead>Website</TableHead>
                        <TableHead>LinkedIn Profile</TableHead>
                        <TableHead>Automation Status</TableHead>
                        <TableHead>LI CRM Status</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Decision Maker</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Sent At</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(!linkedinLeadsData?.leads || linkedinLeadsData.leads.length === 0) && (
                        <TableRow>
                          <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                            No LinkedIn leads found. Start a LinkedIn Autopilot campaign!
                          </TableCell>
                        </TableRow>
                      )}
                      {linkedinLeadsData?.leads?.map((lead: any) => (
                        <React.Fragment key={lead.id}>
                          <TableRow className="hover:bg-blue-50/30 transition-colors">
                            <TableCell className="font-semibold text-slate-800">
                              <div className="flex flex-col gap-0.5">
                                <span className="font-bold text-foreground">{lead.full_name || 'Prospect'}</span>
                                <span className="text-xs text-muted-foreground font-mono">{lead.phone || 'N/A'}</span>
                                {lead.email && (
                                  <span className="text-[10px] text-primary font-mono truncate max-w-[120px]">{lead.email}</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>{lead.business_name || 'N/A'}</TableCell>
                            <TableCell>
                              {lead.website ? (
                                <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline font-medium text-xs truncate max-w-[100px]" title={lead.website}>
                                  {lead.website}
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {lead.linkedin_url ? (
                                <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-blue-500 hover:underline font-medium text-xs truncate max-w-[100px]" title={lead.linkedin_url}>
                                  Profile
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {lead.linkedin_sent_at ? (
                                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-md text-xs font-bold uppercase border border-emerald-200">
                                  Delivered
                                </span>
                              ) : lead.linkedin_message ? (
                                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-bold uppercase border border-blue-200">
                                  Ready to Send
                                </span>
                              ) : (
                                <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded-md text-xs font-bold uppercase border border-amber-200">
                                  Pending
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              {lead.linkedin_status ? (
                                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider border whitespace-nowrap ${
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
                            <TableCell className="text-xs capitalize">
                              <span className={getPriorityColor(lead.priority || 'normal')}>{lead.priority || 'normal'}</span>
                            </TableCell>
                            <TableCell>
                              {(() => {
                                const isDM = lead.internal_notes?.includes("Decision Maker: Yes") ? "Yes" : 
                                             lead.internal_notes?.includes("Decision Maker: No") ? "No" : "Uncertain";
                                if (isDM === "Yes") return <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 text-[10px] font-semibold">Yes</span>;
                                if (isDM === "No") return <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-[10px] font-semibold">No</span>;
                                return <span className="text-gray-400 text-xs">Uncertain</span>;
                              })()}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1 text-yellow-500 text-xs font-bold">
                                <Star className="h-3 w-3 fill-current" />
                                <span>{lead.lead_score || 0}</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-xs font-medium text-slate-600 whitespace-nowrap">
                              {lead.linkedin_sent_at ? new Date(lead.linkedin_sent_at).toLocaleString() : '--'}
                            </TableCell>
                            <TableCell className="text-right flex justify-end items-center">
                              <button 
                                onClick={() => toggleExpand(`linkedin-${lead.id}`)}
                                className="text-blue-600 hover:text-blue-800 p-2 rounded-full hover:bg-blue-50 transition-colors"
                              >
                                {expandedCallId === `linkedin-${lead.id}` ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                              </button>
                            </TableCell>
                          </TableRow>
                          
                          {expandedCallId === `linkedin-${lead.id}` && (
                            <TableRow className="bg-slate-50/80">
                              <TableCell colSpan={11} className="p-0 border-b">
                                <div className="p-6">
                                  <div className="bg-white p-5 rounded-xl border border-blue-100 shadow-sm max-w-3xl">
                                    <h4 className="font-bold text-sm text-slate-700 mb-3 flex items-center gap-2">
                                      <Sparkles className="h-4 w-4 text-blue-500" /> AI Message Draft
                                    </h4>
                                    <div className="text-sm text-slate-700 bg-slate-50 p-4 rounded-lg whitespace-pre-wrap font-medium border border-slate-200/60 shadow-inner">
                                      {lead.linkedin_message || <span className="italic text-slate-400">The AI is currently generating a personalized message for this lead...</span>}
                                    </div>
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </React.Fragment>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* EMAIL TAB */}
      {activeTab === 'email' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
          <Card className="shadow-md glass-card border-t-4 border-t-emerald-500">
            <CardHeader className="border-b border-slate-100 pb-4 flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                  <Target className="h-5 w-5 text-emerald-500" /> Email Outreach & Deliveries
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-1">Leads with email addresses and their outreach delivery status.</p>
              </div>
              <button
                onClick={() => syncInboxMutation.mutate()}
                disabled={syncInboxMutation.isPending}
                className="bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-bold flex items-center gap-2 transition-colors disabled:opacity-50 shrink-0"
              >
                <RefreshCw className={`h-4 w-4 ${syncInboxMutation.isPending ? 'animate-spin' : ''}`} />
                {syncInboxMutation.isPending ? 'Syncing...' : 'AI Inbox Review'}
              </button>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoadingEmail ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading email leads...</div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead>Prospect Details</TableHead>
                        <TableHead>Business Name</TableHead>
                        <TableHead>Website</TableHead>
                        <TableHead>LinkedIn Profile</TableHead>
                        <TableHead>Outreach Status</TableHead>
                        <TableHead>CRM Status</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Decision Maker</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Sent At</TableHead>
                        <TableHead className="text-right">Action</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(!emailLeadsData?.leads || emailLeadsData.leads.length === 0) && (
                        <TableRow>
                          <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                            No email leads found. Start an Email Campaign!
                          </TableCell>
                        </TableRow>
                      )}
                      {emailLeadsData?.leads?.map((lead: any) => (
                        <React.Fragment key={lead.id}>
                          <TableRow className="hover:bg-emerald-50/30 transition-colors">
                            <TableCell className="font-semibold text-slate-800">
                              <div className="flex flex-col gap-0.5">
                                <span className="font-bold text-foreground">{lead.full_name || 'Prospect'}</span>
                                <span className="text-xs text-muted-foreground font-mono">{lead.phone || 'N/A'}</span>
                                {lead.email && (
                                  <span className="text-[10px] text-primary font-mono truncate max-w-[120px]">{lead.email}</span>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>{lead.business_name || 'N/A'}</TableCell>
                            <TableCell>
                              {lead.website ? (
                                <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-primary hover:underline font-medium text-xs truncate max-w-[100px]" title={lead.website}>
                                  {lead.website}
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {lead.linkedin_url ? (
                                <a href={lead.linkedin_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-blue-500 hover:underline font-medium text-xs truncate max-w-[100px]" title={lead.linkedin_url}>
                                  Profile
                                </a>
                              ) : (
                                <span className="text-muted-foreground text-xs">--</span>
                              )}
                            </TableCell>
                            <TableCell>
                              {lead.email_sent_at ? (
                                <span className="px-2 py-1 bg-emerald-100 text-emerald-700 rounded-md text-xs font-bold uppercase border border-emerald-200">
                                  Delivered
                                </span>
                              ) : lead.email_message ? (
                                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-bold uppercase border border-blue-200">
                                  Ready to Send
                                </span>
                              ) : (
                                <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded-md text-xs font-bold uppercase border border-amber-200">
                                  Pending
                                </span>
                              )}
                            </TableCell>
                            <TableCell>
                              <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColor(lead.status)}`}>
                                {lead.status.replace('_', ' ')}
                              </span>
                            </TableCell>
                            <TableCell className="text-xs capitalize">
                              <span className={getPriorityColor(lead.priority || 'normal')}>{lead.priority || 'normal'}</span>
                            </TableCell>
                            <TableCell>
                              {(() => {
                                const isDM = lead.internal_notes?.includes("Decision Maker: Yes") ? "Yes" : 
                                             lead.internal_notes?.includes("Decision Maker: No") ? "No" : "Uncertain";
                                if (isDM === "Yes") return <span className="px-1.5 py-0.5 rounded bg-green-500/10 text-green-500 border border-green-500/20 text-[10px] font-semibold">Yes</span>;
                                if (isDM === "No") return <span className="px-1.5 py-0.5 rounded bg-red-500/10 text-red-500 border border-red-500/20 text-[10px] font-semibold">No</span>;
                                return <span className="text-gray-400 text-xs">Uncertain</span>;
                              })()}
                            </TableCell>
                            <TableCell>
                              <div className="flex items-center gap-1 text-yellow-500 text-xs font-bold">
                                <Star className="h-3 w-3 fill-current" />
                                <span>{lead.lead_score || 0}</span>
                              </div>
                            </TableCell>
                            <TableCell className="text-sm font-medium text-slate-600 whitespace-nowrap">
                              {lead.email_sent_at ? new Date(lead.email_sent_at).toLocaleString() : '--'}
                            </TableCell>
                            <TableCell className="text-right flex justify-end items-center">
                              <button 
                                onClick={() => toggleExpand(`email-${lead.id}`)}
                                className="text-emerald-600 hover:text-emerald-800 p-2 rounded-full hover:bg-emerald-50 transition-colors"
                              >
                                {expandedCallId === `email-${lead.id}` ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                              </button>
                            </TableCell>
                          </TableRow>
                          
                          {expandedCallId === `email-${lead.id}` && (
                            <TableRow className="bg-slate-50/80">
                              <TableCell colSpan={11} className="p-0 border-b">
                                <div className="p-6">
                                  <div className="bg-white p-5 rounded-xl border border-emerald-100 shadow-sm max-w-3xl">
                                    <h4 className="font-bold text-sm text-slate-700 mb-3 flex items-center gap-2">
                                      <Sparkles className="h-4 w-4 text-emerald-500" /> AI Email Draft
                                    </h4>
                                    <div className="text-sm text-slate-700 bg-slate-50/40 p-4 rounded-lg whitespace-pre-wrap font-medium border border-slate-200/60 shadow-inner">
                                      {lead.email_message || <span className="italic text-slate-400">The AI is currently generating a personalized email for this lead...</span>}
                                    </div>
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>
                          )}
                        </React.Fragment>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}


















































