'use client';

import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, Phone, BarChart3, CheckCircle, XCircle, Clock, ArrowUpRight, Zap, Target, Sparkles, ChevronDown, ChevronUp, RefreshCw, AlertCircle, Calendar, Star, Eye, Mail, Linkedin, MapPin } from 'lucide-react';
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

async function fetchExtractedLeads() {
  const response = await fetch(`/api/v1/leads?limit=100`);
  if (!response.ok) throw new Error('Failed to fetch extracted leads');
  const data = await response.json();
  return {
    ...data,
    leads: data.leads.filter((lead: any) => lead.campaign_name?.startsWith('Extracted -'))
  };
}

async function recampaignLead(leadId: string) {
  const response = await fetch(`/api/v1/leads/${leadId}?status=pending`, {
    method: 'PATCH',
  });
  if (!response.ok) throw new Error('Failed to recampaign lead');
  return response.json();
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<'overview' | 'recent' | 'unpicked' | 'linkedin' | 'email' | 'extracted'>('overview');
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const { data: callingSwitchData, refetch: refetchCallingSwitch } = useQuery({
    queryKey: ['calling-switch-status'],
    queryFn: async () => {
      const res = await fetch('/api/v1/campaigns/calling-switch');
      if (!res.ok) throw new Error('Failed to fetch calling switch status');
      return res.json();
    }
  });

  const toggleCallingMutation = useMutation({
    mutationFn: async (enabled: boolean) => {
      const res = await fetch('/api/v1/campaigns/calling-switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled })
      });
      if (!res.ok) throw new Error('Failed to update calling switch status');
      return res.json();
    },
    onSuccess: () => {
      refetchCallingSwitch();
    }
  });

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

  const { data: extractedLeadsData, isLoading: isLoadingExtracted } = useQuery({
    queryKey: ['extracted-leads'],
    queryFn: fetchExtractedLeads,
    refetchInterval: 30000,
    enabled: activeTab === 'extracted'
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
    leadsToday: 0,
    leadsYesterday: 0,
    totalCampaigns: 0,
    totalCalls: 0,
    callsToday: 0,
    callsYesterday: 0,
    successRate: 0,
    pendingCalls: 0,
    failedCalls: 0,
    emailSent: 0,
    emailSentToday: 0,
    emailSentYesterday: 0,
    emailDelivered: 0,
    emailOpened: 0,
    emailClicked: 0,
    emailReplied: 0,
    emailBounced: 0,
    emailBlocked: 0,
    linkedinSent: 0,
    linkedinSentToday: 0,
    linkedinSentYesterday: 0,
    linkedinConnected: 0,
    linkedinReplied: 0,
    directoriesExtracted: 0,
    leadsWithEmails: 0,
    leadsWithSocials: 0,
    totalBookings: 0,
    bookingsToday: 0,
    lastActiveLeadsDate: null as string | null,
    lastActiveLeadsCount: 0,
    lastActiveEmailDate: null as string | null,
    lastActiveEmailCount: 0,
    lastActiveCallsDate: null as string | null,
    lastActiveCallsCount: 0,
    leads7d: 0,
    calls7d: 0,
    emailSent7d: 0,
  };

  // Helpers: format date like "Jul 22" or "Today" / "Yesterday"
  const fmtDate = (d: string | null): string => {
    if (!d) return '';
    const dt = new Date(d + 'T00:00:00');
    const today = new Date(); today.setHours(0,0,0,0);
    const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
    if (dt.getTime() === today.getTime()) return 'Today';
    if (dt.getTime() === yesterday.getTime()) return 'Yesterday';
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  // Effective values: use today count if > 0, else fallback to last-active-day count
  const effectiveLeadsCount = displayStats.leadsToday > 0 ? displayStats.leadsToday : displayStats.lastActiveLeadsCount;
  const effectiveLeadsLabel = displayStats.leadsToday > 0 ? 'Extracted Today' : (displayStats.lastActiveLeadsDate ? `Last active: ${fmtDate(displayStats.lastActiveLeadsDate)}` : 'No data');
  const effectiveEmailCount = displayStats.emailSentToday > 0 ? displayStats.emailSentToday : displayStats.lastActiveEmailCount;
  const effectiveEmailLabel = displayStats.emailSentToday > 0 ? 'Sent Today' : (displayStats.lastActiveEmailDate ? `Last active: ${fmtDate(displayStats.lastActiveEmailDate)}` : 'No data');
  const effectiveCallsCount = displayStats.callsToday > 0 ? displayStats.callsToday : displayStats.lastActiveCallsCount;
  const effectiveCallsLabel = displayStats.callsToday > 0 ? 'Conducted Today' : (displayStats.lastActiveCallsDate ? `Last active: ${fmtDate(displayStats.lastActiveCallsDate)}` : 'No data');

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
        <button
          onClick={() => setActiveTab('extracted')}
          className={`px-4 py-2 text-sm font-bold rounded-t-lg transition-colors flex items-center gap-2 ${activeTab === 'extracted' ? 'bg-purple-100 text-purple-700 border-b-2 border-purple-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'}`}
        >
          Extracted Leads
          {(extractedLeadsData?.leads?.length > 0) && (
            <span className="bg-purple-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{extractedLeadsData.leads.length}</span>
          )}
        </button>
      </div>

      {/* OVERVIEW TAB */}
      {activeTab === 'overview' && (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
          {/* ⚡ TODAY'S LIVE AUTOMATION PROGRESS BANNER */}
          <div className="bg-gradient-to-r from-violet-900 via-indigo-900 to-slate-900 rounded-2xl p-6 text-white shadow-xl border border-violet-500/30">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 pb-3 border-b border-white/10 gap-2">
              <div>
                <h2 className="text-xl font-black tracking-tight flex items-center gap-2 text-violet-300">
                  <Zap className="h-5 w-5 text-amber-400 fill-current animate-pulse" /> TODAY'S LIVE AUTOMATION PROGRESS
                </h2>
                <p className="text-xs text-slate-300">Real-time daily targets & campaign window performance summary</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {/* 📞 MASTER CALLING ON/OFF SWITCH BUTTON */}
                <button
                  onClick={() => toggleCallingMutation.mutate(!callingSwitchData?.calling_enabled)}
                  disabled={toggleCallingMutation.isPending}
                  className={`px-3 py-1.5 rounded-full text-xs font-black flex items-center gap-2 border shadow-sm transition-all ${
                    callingSwitchData?.calling_enabled !== false
                      ? 'bg-emerald-500 text-white border-emerald-400 hover:bg-emerald-600'
                      : 'bg-rose-600 text-white border-rose-500 hover:bg-rose-700'
                  }`}
                  title="Click to Toggle Master AI Voice Calling Queue ON or OFF"
                >
                  <Phone className="h-3.5 w-3.5 fill-current" />
                  <span>AI Calling: {callingSwitchData?.calling_enabled !== false ? 'ON (ACTIVE)' : 'OFF (PAUSED)'}</span>
                  <span className={`h-2.5 w-2.5 rounded-full ${callingSwitchData?.calling_enabled !== false ? 'bg-white animate-pulse' : 'bg-slate-300'}`}></span>
                </button>

                <div className="flex items-center gap-2 bg-emerald-500/20 text-emerald-300 px-3 py-1.5 rounded-full text-xs font-extrabold border border-emerald-500/40">
                  <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping"></span> Live Tracking Active
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* 1. Leads Extracted Today */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-violet-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <MapPin className="h-3.5 w-3.5 text-purple-400" /> Extracted Today
                </div>
                <div className="text-2xl font-black text-white">+{(displayStats.leadsToday || 0).toLocaleString()} <span className="text-xs font-normal text-violet-200">Leads</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Target: 450 / Day</div>
              </div>

              {/* 2. Emails Sent Today */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-emerald-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Mail className="h-3.5 w-3.5 text-emerald-400" /> Emails Sent Today
                </div>
                <div className="text-2xl font-black text-white">{(displayStats.emailSentToday || 0).toLocaleString()} <span className="text-xs font-normal text-emerald-200">Emails</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Window: 6 PM - 6 AM</div>
              </div>

              {/* 3. Calls Conducted */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-pink-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Phone className="h-3.5 w-3.5 text-pink-400" /> Calls Conducted
                </div>
                <div className="text-2xl font-black text-white">{(displayStats.callsToday || 0).toLocaleString()} <span className="text-xs font-normal text-pink-200">Calls</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Window: 8 PM - 4 AM</div>
              </div>

              {/* 4. LinkedIn Requests */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-blue-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Linkedin className="h-3.5 w-3.5 text-blue-400" /> LinkedIn Requests
                </div>
                <div className="text-2xl font-black text-white">{(displayStats.linkedinSentToday || 0).toLocaleString()} <span className="text-xs font-normal text-blue-200">Sent</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Max 30 / Day Cap</div>
              </div>

              {/* 5. Appointments Booked Today */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all col-span-2 md:col-span-1">
                <div className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Calendar className="h-3.5 w-3.5 text-amber-400" /> Appts Booked
                </div>
                <div className="text-2xl font-black text-amber-300">{(displayStats.bookingsToday || 0).toLocaleString()} <span className="text-xs font-normal text-amber-200">Booked</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Direct Meetings</div>
              </div>
            </div>
          </div>

          {/* 📊 YESTERDAY & ENRICHMENT PERFORMANCE OVERVIEW BANNER */}
          <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-6 text-white shadow-xl border border-indigo-500/20">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-4 pb-3 border-b border-white/10 gap-2">
              <div>
                <h2 className="text-xl font-black tracking-tight flex items-center gap-2 text-indigo-300">
                  <BarChart3 className="h-5 w-5 text-indigo-400" /> YESTERDAY & ENRICHMENT PERFORMANCE OVERVIEW
                </h2>
                <p className="text-xs text-slate-300">Extracted leads batch performance overview & local directory enrichment profile breakdown</p>
              </div>
              <div className="flex items-center gap-2 bg-indigo-500/20 text-indigo-300 px-3 py-1 rounded-full text-xs font-extrabold border border-indigo-500/40">
                End-to-End Metrics
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* 1. Extracted Leads Yesterday / Last Batch */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Users className="h-3.5 w-3.5 text-slate-400" /> Extracted Leads
                </div>
                <div className="text-2xl font-black text-white">
                  +{(displayStats.leadsYesterday > 0 ? displayStats.leadsYesterday : (displayStats.lastActiveLeadsCount || 0)).toLocaleString()} <span className="text-xs font-normal text-slate-300">Leads</span>
                </div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">
                  {displayStats.leadsYesterday > 0 
                    ? 'Scraped Yesterday' 
                    : (displayStats.lastActiveLeadsDate ? `Last Batch: ${fmtDate(displayStats.lastActiveLeadsDate)}` : 'No Recent Extraction')}
                </div>
              </div>

              {/* 2. Email Outreach Yesterday / Last Batch */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-emerald-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Mail className="h-3.5 w-3.5 text-emerald-400" /> Email Outreach
                </div>
                <div className="text-2xl font-black text-white">
                  {(displayStats.emailSentYesterday > 0 ? displayStats.emailSentYesterday : (displayStats.lastActiveEmailCount || 0)).toLocaleString()} <span className="text-xs font-normal text-emerald-200">Sent</span>
                </div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">
                  {displayStats.emailSentYesterday > 0 
                    ? `Delivered: ${(displayStats.emailDelivered || 0).toLocaleString()}` 
                    : (displayStats.lastActiveEmailDate ? `Last Batch: ${fmtDate(displayStats.lastActiveEmailDate)}` : 'Delivered: 0')}
                </div>
              </div>

              {/* 3. Voice Calls Yesterday / Last Batch */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-pink-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Phone className="h-3.5 w-3.5 text-pink-400" /> Voice Calls
                </div>
                <div className="text-2xl font-black text-white">
                  {(displayStats.callsYesterday > 0 ? displayStats.callsYesterday : (displayStats.lastActiveCallsCount || 0)).toLocaleString()} <span className="text-xs font-normal text-pink-200">Calls</span>
                </div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">
                  {displayStats.callsYesterday > 0 
                    ? 'Recorded Calls' 
                    : (displayStats.lastActiveCallsDate ? `Last Batch: ${fmtDate(displayStats.lastActiveCallsDate)}` : 'Recorded Calls')}
                </div>
              </div>

              {/* 4. LinkedIn Autopilot */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all">
                <div className="text-xs font-bold text-blue-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Linkedin className="h-3.5 w-3.5 text-blue-400" /> LinkedIn Autopilot
                </div>
                <div className="text-2xl font-black text-white">{(displayStats.linkedinSentToday || displayStats.linkedinSent || 0).toLocaleString()} <span className="text-xs font-normal text-blue-200">Sent</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Scraped & Outreach</div>
              </div>

              {/* 5. Directory Profiles Enriched */}
              <div className="bg-white/10 backdrop-blur-md p-4 rounded-xl border border-white/15 hover:bg-white/15 transition-all col-span-2 md:col-span-1">
                <div className="text-xs font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5 mb-1">
                  <Sparkles className="h-3.5 w-3.5 text-amber-400" /> Directories Enriched
                </div>
                <div className="text-2xl font-black text-amber-300">{(displayStats.directoriesExtracted || 0).toLocaleString()} <span className="text-xs font-normal text-amber-200">Profiles</span></div>
                <div className="text-[10px] text-slate-300 mt-1 font-medium">Yelp, BBB, Nextdoor, etc.</div>
              </div>
            </div>
          </div>

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
                <div className="flex items-baseline justify-between">
                  <div className="text-3xl font-extrabold text-slate-800">{displayStats.totalContacts?.toLocaleString()}</div>
                  <span className="text-xs font-bold bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">+{(displayStats.leadsToday || 0).toLocaleString()} today</span>
                </div>
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
                <div className="flex items-baseline justify-between">
                  <div className="text-3xl font-extrabold text-slate-800">{displayStats.totalCalls?.toLocaleString()}</div>
                  <span className="text-xs font-bold bg-pink-100 text-pink-700 px-2 py-0.5 rounded-full">+{(displayStats.callsToday || 0).toLocaleString()} today</span>
                </div>
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
                <div className="flex items-baseline justify-between">
                  <div className="text-3xl font-extrabold text-emerald-600">{displayStats.successRate ?? 0}%</div>
                  <span className="text-xs font-bold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full">+{(displayStats.bookingsToday || 0).toLocaleString()} booked today</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1 font-medium flex items-center gap-1">
                  Successful pitches / bookings
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Multi-Channel Outreach Metrics Section */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Voice Calling Card */}
            <Card className="glass-card shadow-md border border-violet-100 hover:border-violet-200 hover:scale-[1.01] transition-all duration-300">
              <CardHeader className="border-b border-slate-50 pb-3 flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base font-bold text-slate-800 flex items-center gap-2">
                  <Phone className="h-5 w-5 text-violet-500" /> Voice Calling
                </CardTitle>
                <span className="text-[10px] bg-violet-500/10 text-violet-600 font-bold px-2 py-0.5 rounded-full uppercase">Real-time</span>
              </CardHeader>
              <CardContent className="pt-4 space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium">Outbound Calls</span>
                  <span className="font-extrabold text-slate-800">{(displayStats.totalCalls || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2 bg-pink-50/50 px-2 py-1 rounded">
                  <span className="text-pink-700 font-bold">Calls Conducted Today</span>
                  <span className="font-extrabold text-pink-700">{displayStats.callsToday || 0}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium">Failed Dials</span>
                  <span className="font-bold text-rose-600">{displayStats.failedCalls || 0}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500 font-medium">Success Rate</span>
                  <span className="font-extrabold text-emerald-600">{displayStats.successRate || 0}%</span>
                </div>
              </CardContent>
            </Card>

            {/* Email Campaigns Card */}
            <Card className="glass-card shadow-md border border-emerald-100 hover:border-emerald-200 hover:scale-[1.01] transition-all duration-300">
              <CardHeader className="border-b border-slate-50 pb-3 flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base font-bold text-slate-800 flex items-center gap-2">
                  <Mail className="h-5 w-5 text-emerald-500" /> Email Outreach
                </CardTitle>
                <span className="text-[10px] bg-emerald-500/10 text-emerald-600 font-bold px-2 py-0.5 rounded-full uppercase">Gmail SMTP</span>
              </CardHeader>
              <CardContent className="pt-4 space-y-3">
                <div className="grid grid-cols-3 gap-2 text-center border-b border-slate-100 pb-3">
                  <div className="bg-slate-50 p-2 rounded-lg border border-slate-100">
                    <p className="text-[10px] text-slate-400 font-bold">ALL-TIME SENT</p>
                    <p className="text-base font-extrabold text-slate-800">{(displayStats.emailSent || 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-emerald-50 p-2 rounded-lg border border-emerald-100">
                    <p className="text-[10px] text-emerald-600 font-bold">DELIVERED</p>
                    <p className="text-base font-extrabold text-emerald-700">{(displayStats.emailDelivered || 0).toLocaleString()}</p>
                  </div>
                  <div className="bg-amber-50 p-2 rounded-lg border border-amber-100">
                    <p className="text-[10px] text-amber-600 font-bold">PENDING</p>
                    <p className="text-base font-extrabold text-amber-700">{(displayStats.emailPending ?? (displayStats.totalContacts - displayStats.emailSent))?.toLocaleString() || 0}</p>
                  </div>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2 bg-emerald-50/50 px-2 py-1 rounded">
                  <span className="text-emerald-700 font-bold">Emails Sent Today</span>
                  <span className="font-extrabold text-emerald-700">{displayStats.emailSentToday || 0}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium flex items-center gap-1.5"><Eye className="h-4 w-4 text-blue-500" /> Opens</span>
                  <span className="font-bold text-slate-800">{(displayStats.emailOpened || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium flex items-center gap-1.5"><Zap className="h-4 w-4 text-purple-500" /> Clicks</span>
                  <span className="font-bold text-slate-800">{(displayStats.emailClicked || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium flex items-center gap-1.5"><CheckCircle className="h-4 w-4 text-emerald-500" /> Replies</span>
                  <span className="font-bold text-emerald-600">{(displayStats.emailReplied || 0).toLocaleString()}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs pt-1">
                  <div className="flex justify-between items-center text-rose-500 font-medium">
                    <span>Bounced Leads:</span>
                    <span className="font-bold">{displayStats.emailBounced || 0}</span>
                  </div>
                  <div className="flex justify-between items-center text-rose-600 font-medium">
                    <span>Inbox Bounce Emails:</span>
                    <span className="font-bold">{displayStats.rawBounceMessages || 0}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* LinkedIn Autopilot Card */}
            <Card className="glass-card shadow-md border border-blue-100 hover:border-blue-200 hover:scale-[1.01] transition-all duration-300">
              <CardHeader className="border-b border-slate-50 pb-3 flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base font-bold text-slate-800 flex items-center gap-2">
                  <Linkedin className="h-5 w-5 text-blue-500" /> LinkedIn Autopilot
                </CardTitle>
                <span className="text-[10px] bg-blue-500/10 text-blue-600 font-bold px-2 py-0.5 rounded-full uppercase">Autopilot</span>
              </CardHeader>
              <CardContent className="pt-4 space-y-3">
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium">Connections Sent</span>
                  <span className="font-extrabold text-blue-600">{(displayStats.linkedinSent || 0).toLocaleString()} <span className="text-[10px] text-slate-400 font-normal">(Max 30/day)</span></span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2 bg-blue-50/50 px-2 py-1 rounded">
                  <span className="text-blue-700 font-bold">Sent Today</span>
                  <span className="font-extrabold text-blue-700">{displayStats.linkedinSentToday || 0}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium">Connections Accepted</span>
                  <span className="font-bold text-emerald-600">{(displayStats.linkedinConnected || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm border-b border-slate-100 pb-2">
                  <span className="text-slate-500 font-medium">Follow-Up Messages Sent</span>
                  <span className="font-bold text-purple-600">{(displayStats.linkedinMessagesSent || 0).toLocaleString()}</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500 font-medium">Leads Replied / Booked</span>
                  <span className="font-extrabold text-slate-800">{displayStats.linkedinReplied || 0}</span>
                </div>
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
                          {displayStats.callsToday ?? 0}
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
                          {displayStats.pendingCalls ?? 0}
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
                          {displayStats.failedCalls ?? 0}
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
                
                {/* Visual Progress Bar */}
                <div className="mt-8 space-y-2">
                  <div className="flex justify-between text-xs font-semibold text-slate-600">
                    <span>Completed Conversations Progress</span>
                    <span>{displayStats.callsToday ?? 0} / {(displayStats.callsToday ?? 0) + (displayStats.pendingCalls ?? 0)} Leads</span>
                  </div>
                  <div className="h-3 w-full bg-slate-100 rounded-full overflow-hidden border border-slate-200/50 p-0.5">
                    <div 
                      className="h-full bg-gradient-to-r from-violet-500 via-indigo-500 to-pink-500 rounded-full" 
                      style={{ 
                        width: `${
                          (displayStats.callsToday ?? 0) + (displayStats.pendingCalls ?? 0) > 0 
                            ? Math.min(100, Math.round(((displayStats.callsToday ?? 0) / ((displayStats.callsToday ?? 0) + (displayStats.pendingCalls ?? 0))) * 100))
                            : 0
                        }%` 
                      }}
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
                              {lead.email_status ? (
                                <span className={`px-2 py-1 rounded-md text-xs font-bold uppercase border whitespace-nowrap ${
                                  lead.email_status === 'replied' ? 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20' :
                                  lead.email_status === 'clicked' ? 'bg-purple-500/10 text-purple-600 border-purple-500/20 font-extrabold' :
                                  lead.email_status === 'opened' ? 'bg-blue-500/10 text-blue-600 border-blue-500/20 font-semibold' :
                                  lead.email_status === 'delivered' ? 'bg-green-500/10 text-green-600 border-green-500/20' :
                                  lead.email_status === 'bounced' ? 'bg-rose-500/10 text-rose-600 border-rose-500/20 font-extrabold' :
                                  lead.email_status === 'blocked' ? 'bg-amber-500/10 text-amber-600 border-amber-500/20' :
                                  'bg-slate-500/10 text-slate-500 border-slate-500/20'
                                }`}>
                                  {lead.email_status}
                                </span>
                              ) : lead.email_sent_at ? (
                                <span className="px-2 py-1 bg-green-500/10 text-green-600 rounded-md text-xs font-bold uppercase border border-green-500/20">
                                  Sent
                                </span>
                              ) : lead.email_message ? (
                                <span className="px-2 py-1 bg-blue-100 text-blue-700 rounded-md text-xs font-bold uppercase border border-blue-200 animate-pulse">
                                  Ready
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

      {/* EXTRACTED LEADS TAB */}
      {activeTab === 'extracted' && (
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-500 space-y-4">
          <Card className="shadow-md glass-card border-t-4 border-t-purple-500">
            <CardHeader className="border-b border-slate-100 pb-4">
              <CardTitle className="text-lg font-bold text-slate-800 flex items-center gap-2">
                <Users className="h-5 w-5 text-purple-500" /> Google Maps Extracted Leads
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">Leads scraped directly from Google Maps and enriched with details.</p>
            </CardHeader>
            <CardContent className="pt-4">
              {isLoadingExtracted ? (
                <div className="p-8 text-center text-muted-foreground animate-pulse">Loading extracted leads...</div>
              ) : (
                <div className="rounded-md border border-slate-200 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-50">
                      <TableRow>
                        <TableHead>Business Name</TableHead>
                        <TableHead>Phone</TableHead>
                        <TableHead>Email</TableHead>
                        <TableHead>Website</TableHead>
                        <TableHead>Location</TableHead>
                        <TableHead>Source Campaign</TableHead>
                        <TableHead>CRM Status</TableHead>
                        <TableHead>Priority</TableHead>
                        <TableHead>Decision Maker</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Extracted At</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {(!extractedLeadsData?.leads || extractedLeadsData.leads.length === 0) && (
                        <TableRow>
                          <TableCell colSpan={11} className="text-center py-8 text-muted-foreground">
                            No extracted leads found. Run Google Maps Extraction first!
                          </TableCell>
                        </TableRow>
                      )}
                      {extractedLeadsData?.leads?.map((lead: any) => (
                        <TableRow key={lead.id} className="hover:bg-purple-50/30 transition-colors">
                          <TableCell className="font-bold text-slate-800">
                            {lead.business_name || lead.full_name || 'Prospect'}
                          </TableCell>
                          <TableCell className="font-mono text-xs">{lead.phone || '--'}</TableCell>
                          <TableCell className="font-mono text-xs text-primary truncate max-w-[150px]" title={lead.email || ''}>
                            {lead.email || '--'}
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
                          <TableCell className="text-xs">
                            {lead.city || lead.state ? `${lead.city || ''} ${lead.state || ''}`.trim() : '--'}
                          </TableCell>
                          <TableCell className="text-xs font-semibold text-purple-600">
                            {lead.campaign_name || '--'}
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
                          <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                            {lead.created_at ? new Date(lead.created_at).toLocaleString() : '--'}
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
    </div>
  );
}


















































