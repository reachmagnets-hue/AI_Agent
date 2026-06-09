'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Phone, User, Clock, MessageCircle, CheckCircle, XCircle, PlayCircle, Search, Calendar, Star, AlertCircle, Volume2 } from 'lucide-react';
import Link from 'next/link';

async function fetchCalls({ search, status, outcome, page }: { search: string; status: string; outcome: string; page: number }) {
  let url = `/api/v1/calls/?page=${page}&limit=15`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (status && status !== 'all') url += `&status=${status}`;
  if (outcome && outcome !== 'all') url += `&outcome=${outcome}`;
  
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch call logs');
  return res.json();
}

export default function CallsPage() {
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [outcome, setOutcome] = useState('all');
  const [page, setPage] = useState(1);

  const { data, isLoading, error } = useQuery({
    queryKey: ['calls', { search, status, outcome, page }],
    queryFn: () => fetchCalls({ search, status, outcome, page }),
  });

  const { data: statsData } = useQuery({
    queryKey: ['calls-stats'],
    queryFn: async () => {
          const res = await fetch(`/api/v1/calls/stats/overview`);
      return res.json();
    }
  });

  const calls = data?.calls || [];
  const total = data?.total || 0;
  const totalPages = data?.pages || 1;
  const stats = statsData || { today: { total: 0, answered: 0, booked: 0, avg_duration: 0.0 } };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed': return <XCircle className="h-4 w-4 text-red-500" />;
      case 'initiated': return <PlayCircle className="h-4 w-4 text-blue-500" />;
      case 'ringing': return <Volume2 className="h-4 w-4 text-yellow-500" />;
      default: return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getOutcomeColor = (outcome: string) => {
    switch (outcome) {
      case 'meeting_booked': return 'bg-purple-500/10 text-purple-500 border border-purple-500/20';
      case 'interested': return 'bg-green-500/10 text-green-500 border border-green-500/20';
      case 'not_interested': return 'bg-red-500/10 text-red-500 border border-red-500/20';
      default: return 'bg-gray-500/10 text-gray-500 border border-gray-500/20';
    }
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <Phone className="h-8 w-8 text-primary" /> Outbound Call Activity Logs
        </h1>
        <p className="text-muted-foreground mt-1">Review AI outbound conversations, listen to call recordings, and view transcripts.</p>
      </div>

      {/* Call Activity Overview Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{stats.today?.total || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Calls Placed Today</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-500">{stats.today?.answered || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Answered Today</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-purple-500">{stats.today?.booked || 0}</div>
            <p className="text-xs text-muted-foreground mt-1">Booked Today</p>
          </CardContent>
        </Card>
        <Card className="bg-card/50 backdrop-blur-sm border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{stats.today?.avg_duration || 0.0}s</div>
            <p className="text-xs text-muted-foreground mt-1">Avg Call Duration</p>
          </CardContent>
        </Card>
      </div>

      {/* Search and Table */}
      <Card className="bg-card/30 backdrop-blur border-muted-foreground/10">
        <CardHeader>
          <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
            <div className="relative w-full md:w-96">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search transcripts, prospect name, phone..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="pl-9 bg-background"
              />
            </div>
            
            <div className="flex gap-4 w-full md:w-auto justify-end">
              <select
                value={status}
                onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                className="bg-background border rounded px-2.5 py-1.5 text-sm"
              >
                <option value="all">All Statuses</option>
                <option value="initiated">Initiated</option>
                <option value="ringing">Ringing</option>
                <option value="answered">Answered</option>
                <option value="completed">Completed</option>
                <option value="failed">Failed</option>
              </select>

              <select
                value={outcome}
                onChange={(e) => { setOutcome(e.target.value); setPage(1); }}
                className="bg-background border rounded px-2.5 py-1.5 text-sm"
              >
                <option value="all">All Outcomes</option>
                <option value="meeting_booked">Meeting Booked</option>
                <option value="interested">Interested</option>
                <option value="interested_callback">Callback Requested</option>
                <option value="not_interested">Not Interested</option>
                <option value="voicemail_left">Voicemail Left</option>
                <option value="no_answer">No Answer</option>
                <option value="hung_up">Hung Up</option>
                <option value="wrong_number">Wrong Number</option>
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex justify-center p-8 text-muted-foreground">Loading call log list...</div>
          ) : error ? (
            <div className="flex justify-center p-8 text-red-500">Error loading call activity.</div>
          ) : calls.length === 0 ? (
            <div className="flex flex-col justify-center items-center p-12 text-muted-foreground gap-2">
              <AlertCircle className="h-8 w-8 text-primary" /> No call activities found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prospect Details</TableHead>
                    <TableHead>Campaign ID</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Outcome</TableHead>
                    <TableHead>Audio Recording</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calls.map((call: any) => (
                    <TableRow key={call.id} className="hover:bg-accent/40 transition-colors">
                      <TableCell className="font-semibold">
                        <div className="flex flex-col">
                          <span className="font-bold text-foreground">{call.lead?.full_name || 'Prospect'}</span>
                          <span className="text-xs text-muted-foreground font-mono">{call.to_number || call.lead?.phone}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs font-mono">{call.campaign_id ? call.campaign_id.substring(0, 8) + '...' : 'Outbound Script'}</TableCell>
                      <TableCell className="text-sm font-semibold">{formatDuration(call.duration_seconds || 0)}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1.5 text-sm">
                          {getStatusIcon(call.status)}
                          <span className="capitalize">{call.status}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        {call.outcome ? (
                          <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase tracking-wider ${getOutcomeColor(call.outcome)}`}>
                            {call.outcome.replace('_', ' ')}
                          </span>
                        ) : 'Pending'}
                      </TableCell>
                      <TableCell>
                        {call.recording_url ? (
                          <audio src={call.recording_url} controls className="h-7 w-48 max-w-full text-xs" />
                        ) : (
                          <span className="text-xs text-muted-foreground italic">No Recording</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/leads/${call.lead_id}`}>
                          <Button size="sm" variant="ghost" className="hover:text-primary">
                            CRM Profile
                          </Button>
                        </Link>
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