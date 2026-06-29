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
                    <TableHead>Audio Recording</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {calls.map((call: any) => (
                    <TableRow key={call.id} className="hover:bg-accent/40 transition-colors">
                      <TableCell className="font-semibold">
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
                      <TableCell className="text-sm font-semibold whitespace-nowrap">{formatDuration(call.duration_seconds || 0)}</TableCell>
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
                      <TableCell>
                        {call.recording_url ? (
                          <audio src={call.recording_url} controls className="h-6 w-32 max-w-full text-xs" />
                        ) : (
                          <span className="text-xs text-muted-foreground italic">No Recording</span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/leads/${call.lead_id}`}>
                          <Button size="sm" variant="ghost" className="hover:text-primary h-8 px-2 text-xs">
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