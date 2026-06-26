'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Calendar, Search, Filter, AlertCircle, Link2, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import Link from 'next/link';

async function fetchAppointments({ timeFilter, status, search }: { timeFilter: string; status: string; search: string }) {
  let endpoint = `/api/v1/appointments/`;
  
  if (timeFilter === 'today') {
    endpoint = `/api/v1/appointments/today`;
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('Failed to fetch today appointments');
    const data = await res.json();
    return { appointments: data };
  } else if (timeFilter === 'upcoming') {
    endpoint = `/api/v1/appointments/upcoming`;
    const res = await fetch(endpoint);
    if (!res.ok) throw new Error('Failed to fetch upcoming appointments');
    const data = await res.json();
    return { appointments: data };
  }

  let url = `/api/v1/appointments/?page=1&limit=50`;
  if (status && status !== 'all') url += `&status=${status}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch appointments');
  return res.json();
}

async function updateAppointmentStatus({ id, status }: { id: string; status: string }) {
  const res = await fetch(`/api/v1/appointments/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status })
  });
  if (!res.ok) throw new Error('Failed to update status');
  return res.json();
}

export default function AppointmentsPage() {
  const queryClient = useQueryClient();
  const [timeFilter, setTimeFilter] = useState('all');
  const [status, setStatus] = useState('all');
  const [search, setSearch] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['appointments', { timeFilter, status, search }],
    queryFn: () => fetchAppointments({ timeFilter, status, search })
  });

  const { data: statsData } = useQuery({
    queryKey: ['appointments-stats'],
    queryFn: async () => {
          const res = await fetch(`/api/v1/appointments/stats`);
      return res.json();
    }
  });

  const statusMutation = useMutation({
    mutationFn: updateAppointmentStatus,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['appointments'] });
      queryClient.invalidateQueries({ queryKey: ['appointments-stats'] });
    }
  });

  const handleStatusChange = (id: string, newStatus: string) => {
    statusMutation.mutate({ id, status: newStatus });
  };

  const appts = data?.appointments || [];
  const stats = statsData || { today: 0, this_week: 0, this_month: 0, completion_rate: 0, no_show_rate: 0 };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'confirmed': return 'bg-blue-500/10 text-blue-500 border border-blue-500/20';
      case 'cancelled': return 'bg-red-500/10 text-red-500 border border-red-500/20';
      case 'rescheduled': return 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20';
      case 'completed': return 'bg-green-500/10 text-green-500 border border-green-500/20';
      case 'no_show': return 'bg-orange-500/10 text-orange-500 border border-orange-500/20';
      default: return 'bg-gray-500/10 text-gray-500 border border-gray-500/20';
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Calendar className="h-8 w-8 text-primary" /> Discovery Meetings & Bookings
        </h1>
        <p className="text-muted-foreground mt-1">Unified view of customer consultation meetings, synced from Google Meet.</p>
      </div>

      {/* Bookings Metrics Banner */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-primary">{stats.today}</div>
            <p className="text-xs text-muted-foreground mt-1">Discovery Calls Today</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{stats.this_week}</div>
            <p className="text-xs text-muted-foreground mt-1">Scheduled This Week</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{stats.this_month}</div>
            <p className="text-xs text-muted-foreground mt-1">Scheduled This Month</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-500">{stats.completion_rate}%</div>
            <p className="text-xs text-muted-foreground mt-1">Show / Close Rate</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10 col-span-2 lg:col-span-1">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-red-500">{stats.no_show_rate}%</div>
            <p className="text-xs text-muted-foreground mt-1">No-Show / Cancel Rate</p>
          </CardContent>
        </Card>
      </div>

      {/* Filter and Lists Section */}
      <Card className="bg-card/30 backdrop-blur border-muted-foreground/10">
        <CardHeader>
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="flex gap-2 bg-background border rounded-lg p-1 w-full md:w-auto">
              <Button size="sm" variant={timeFilter === 'all' ? 'default' : 'ghost'} onClick={() => { setTimeFilter('all'); setStatus('all'); }}>All Bookings</Button>
              <Button size="sm" variant={timeFilter === 'today' ? 'default' : 'ghost'} onClick={() => setTimeFilter('today')}>Today Only</Button>
              <Button size="sm" variant={timeFilter === 'upcoming' ? 'default' : 'ghost'} onClick={() => setTimeFilter('upcoming')}>Next 7 Days</Button>
            </div>
            
            {timeFilter === 'all' && (
              <div className="flex gap-4 w-full md:w-auto justify-end">
                <div className="relative w-full md:w-64">
                  <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search bookings..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    className="pl-8 bg-background h-9"
                  />
                </div>
                
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  className="bg-background border rounded-lg px-2.5 py-1 text-sm h-9"
                >
                  <option value="all">All Statuses</option>
                  <option value="confirmed">Confirmed</option>
                  <option value="rescheduled">Rescheduled</option>
                  <option value="completed">Completed</option>
                  <option value="no_show">No Show</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center p-8 text-muted-foreground">Loading appointment list...</div>
          ) : error ? (
            <div className="flex justify-center p-8 text-red-500">Error loading appointments.</div>
          ) : appts.length === 0 ? (
            <div className="flex flex-col justify-center items-center p-12 text-muted-foreground gap-2">
              <AlertCircle className="h-8 w-8 text-primary" /> No scheduled discovery meetings found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Meeting Date & Time</TableHead>
                    <TableHead>Prospect Details</TableHead>
                    <TableHead>Business Name</TableHead>
                    <TableHead>Assigned Representative</TableHead>
                    <TableHead>Cal Link</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {appts.map((appt: any) => (
                    <TableRow key={appt.id} className="hover:bg-accent/40 transition-colors">
                      <TableCell className="font-semibold">
                        <div className="flex flex-col">
                          <span>{appt.meeting_date}</span>
                          <span className="text-xs text-primary font-mono">{appt.meeting_time} ({appt.timezone})</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-semibold text-foreground">{appt.prospect_name}</span>
                          <span className="text-xs text-muted-foreground font-mono">{appt.prospect_phone}</span>
                        </div>
                      </TableCell>
                      <TableCell>{appt.prospect_business || 'N/A'}</TableCell>
                      <TableCell className="text-sm">{appt.assigned_to || 'Alex (AI Agent)'}</TableCell>
                      <TableCell>
                        {appt.cal_meeting_link ? (
                          <a href={appt.cal_meeting_link} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline flex items-center gap-1 text-xs">
                            <Link2 className="h-3.5 w-3.5" /> Google Meet
                          </a>
                        ) : 'N/A'}
                      </TableCell>
                      <TableCell>
                        <span className={`px-2 py-0.5 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColor(appt.status)}`}>
                          {appt.status.replace('_', ' ')}
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex gap-2 justify-end items-center">
                          <select
                            value={appt.status}
                            onChange={(e) => handleStatusChange(appt.id, e.target.value)}
                            className="bg-background border rounded px-1.5 py-1 text-xs"
                          >
                            <option value="confirmed">Confirmed</option>
                            <option value="completed">Completed</option>
                            <option value="no_show">No Show</option>
                            <option value="cancelled">Cancelled</option>
                          </select>
                          <Link href={`/leads/${appt.lead_id}`}>
                            <Button size="sm" variant="outline" className="text-xs py-1 h-7">Profile</Button>
                          </Link>
                        </div>
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
  );
}
