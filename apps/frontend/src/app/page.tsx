'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, Phone, BarChart3, CheckCircle, XCircle, Clock, ArrowUpRight, Zap, Target, Sparkles } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

async function fetchDashboardData() {
  const response = await fetch(`/api/v1/calls/dashboard/stats`);
  if (!response.ok) {
    throw new Error('Failed to fetch dashboard data');
  }
  return response.json();
}

export default function Dashboard() {
  const { data: stats, isLoading, error } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: fetchDashboardData,
    refetchInterval: 30000,
  });

  const mockStats = {
    totalContacts: 1247,
    totalCampaigns: 23,
    totalCalls: 4589,
    callsToday: 127,
    successRate: 78.5,
    pendingCalls: 342,
    failedCalls: 15,
  };

  const displayStats = stats || mockStats;

  return (
    <div className="space-y-10">
      {/* Header section with sparkles decoration */}
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

      {/* Grid: Details and Quick Actions */}
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

        {/* Quick actions box */}
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
            
            <div className="bg-slate-50 border border-slate-150 p-4 rounded-xl text-center text-xs text-muted-foreground font-medium">
              Ready to import CSV files, configure agent voice prompts, or sync schedules.
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Loading & Error Blocks */}
      {isLoading && (
        <div className="flex items-center justify-center p-8 bg-white/40 backdrop-blur rounded-xl border border-white/60">
          <div className="animate-pulse text-muted-foreground text-sm font-semibold flex items-center gap-2">
            <Clock className="h-4 w-4 text-violet-500 animate-spin" /> Synchronizing Command Center...
          </div>
        </div>
      )}

      {error && (
        <div className="bg-rose-50 border border-rose-100 text-rose-800 px-4 py-3 rounded-xl text-sm font-medium">
          Note: Local backend server not responding. Displaying client-side sample data.
        </div>
      )}
    </div>
  );
}
