'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChevronLeft, Calendar, Phone, Mail, Globe, MapPin, Award, BookOpen, Clock, AlertTriangle, FileText, Send, User, ChevronDown, ChevronUp } from 'lucide-react';
import Link from 'next/link';

async function fetchLeadDetail(id: string) {
  const res = await fetch(`/api/v1/leads/${id}`);
  if (!res.ok) throw new Error('Failed to fetch lead profile');
  return res.json();
}

async function updateLeadProfile({ id, ...data }: { id: string; [key: string]: any }) {
  const res = await fetch(`/api/v1/leads/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error('Failed to update lead');
  return res.json();
}

async function addLeadNote({ id, note }: { id: string; note: string }) {
  const res = await fetch(`/api/v1/leads/${id}/notes?note=${encodeURIComponent(note)}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to append note');
  return res.json();
}

export default function LeadDetailPage() {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  const queryClient = useQueryClient();
  const [noteText, setNoteText] = useState('');
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);

  // Profile fields state
  const [isEditing, setIsEditing] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ['lead-detail', id],
    queryFn: () => fetchLeadDetail(id),
  });

  const updateMutation = useMutation({
    mutationFn: updateLeadProfile,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['lead-detail', id] });
      setIsEditing(false);
    }
  });

  const noteMutation = useMutation({
    mutationFn: addLeadNote,
    onSuccess: () => {
      setNoteText('');
      queryClient.invalidateQueries({ queryKey: ['lead-detail', id] });
    }
  });

  if (isLoading) return <div className="p-8 text-center text-muted-foreground">Loading Lead Profile...</div>;
  if (error || !data) return <div className="p-8 text-center text-red-500">Error loading profile details.</div>;

  const { lead, calls, appointments, timeline } = data;

  const handleStatusChange = (status: string) => {
    updateMutation.mutate({ id, status });
  };

  const handlePriorityChange = (priority: string) => {
    updateMutation.mutate({ id, priority });
  };

  const handleAssignedChange = (assigned_to: string) => {
    updateMutation.mutate({ id, assigned_to });
  };

  const handleNoteSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (noteText.trim()) {
      noteMutation.mutate({ id, note: noteText });
    }
  };

  return (
    <div className="space-y-8">
      {/* Back Button */}
      <div className="flex items-center gap-4">
        <Link href="/leads">
          <Button variant="ghost" size="sm" className="flex items-center gap-1.5 hover:text-primary">
            <ChevronLeft className="h-4 w-4" /> Back to Leads
          </Button>
        </Link>
        <span className="text-muted-foreground">/</span>
        <span className="font-semibold text-foreground">{lead.full_name || 'Prospect Profile'}</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Side: CRM Details Card */}
        <div className="space-y-6">
          <Card className="bg-card border-muted-foreground/10 overflow-hidden shadow-lg">
            <div className="h-2 bg-gradient-to-r from-primary via-purple-500 to-indigo-500" />
            <CardHeader className="pb-4">
              <div className="flex justify-between items-start">
                <div>
                  <CardTitle className="text-xl font-bold">{lead.full_name || 'N/A'}</CardTitle>
                  <CardDescription className="text-sm text-primary mt-1">{lead.business_name || 'N/A'}</CardDescription>
                </div>
                <div className="bg-yellow-500/10 border border-yellow-500/20 text-yellow-500 px-2 py-1 rounded flex items-center gap-1 text-xs font-bold">
                  <Award className="h-3.5 w-3.5" /> Score: {lead.lead_score || 0}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 text-sm">
              
              {/* Status Section */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">CRM Lead Status</label>
                <select
                  value={lead.status}
                  onChange={(e) => handleStatusChange(e.target.value)}
                  className="w-full bg-background border border-muted-foreground/20 rounded p-2 font-semibold uppercase tracking-wider text-xs text-primary"
                >
                  <option value="pending">Pending</option>
                  <option value="calling">Calling</option>
                  <option value="interested">Interested</option>
                  <option value="meeting_booked">Meeting Booked</option>
                  <option value="not_interested">Not Interested</option>
                </select>
              </div>

              {/* Priority Section */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Campaign Priority</label>
                <select
                  value={lead.priority}
                  onChange={(e) => handlePriorityChange(e.target.value)}
                  className="w-full bg-background border border-muted-foreground/20 rounded p-2 text-xs"
                >
                  <option value="normal">Normal</option>
                  <option value="high">High</option>
                  <option value="urgent">Urgent</option>
                </select>
              </div>

              {/* Assigned Representative */}
              <div className="space-y-2">
                <label className="text-xs font-bold text-muted-foreground uppercase tracking-wider">Assigned Agent / Rep</label>
                <select
                  value={lead.assigned_to || ''}
                  onChange={(e) => handleAssignedChange(e.target.value)}
                  className="w-full bg-background border border-muted-foreground/20 rounded p-2 text-xs"
                >
                  <option value="">Unassigned</option>
                  <option value="Alex (AI Call Bot)">Alex (AI Call Bot)</option>
                  <option value="Sarah (AI Call Bot)">Sarah (AI Call Bot)</option>
                  <option value="Chetan Patil">Chetan Patil</option>
                  <option value="Outbound Closer #1">Outbound Closer #1</option>
                </select>
              </div>

              <hr className="border-muted-foreground/10" />

              {/* General Info */}
              <div className="space-y-4">
                <div className="flex items-center gap-2.5 text-muted-foreground">
                  <Phone className="h-4 w-4 text-primary" />
                  <span className="font-mono text-foreground font-semibold">{lead.phone}</span>
                </div>
                {lead.email && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2.5 text-muted-foreground">
                      <Mail className="h-4 w-4 text-primary" />
                      <span className="text-foreground break-all">{lead.email}</span>
                    </div>
                    {lead.email_status && (
                      <div className="pl-6 text-[11px] space-y-0.5 mt-1">
                        <div>
                          <span className="font-semibold text-slate-500">Email Status: </span>
                          <span className={`px-1.5 py-0.2 rounded text-[9px] uppercase border font-bold ${
                            lead.email_status === 'opened' ? 'bg-purple-500/10 text-purple-500 border-purple-500/20' : 
                            lead.email_status === 'clicked' ? 'bg-indigo-500/10 text-indigo-500 border-indigo-500/20' :
                            lead.email_status === 'delivered' ? 'bg-emerald-500/10 text-emerald-500 border-emerald-500/20' :
                            lead.email_status === 'sent' ? 'bg-blue-500/10 text-blue-500 border-blue-500/20' :
                            lead.email_status === 'bounced' ? 'bg-amber-500/10 text-amber-500 border-amber-500/20' :
                            'bg-red-500/10 text-red-500 border-red-500/20'
                          }`}>{lead.email_status}</span>
                        </div>
                        {lead.email_sent_at && <div><span className="text-slate-400">Sent: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_sent_at).toLocaleString()}</span></div>}
                        {lead.email_delivered_at && <div><span className="text-slate-400">Delivered: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_delivered_at).toLocaleString()}</span></div>}
                        {lead.email_opened_at && <div><span className="text-slate-400">Opened: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_opened_at).toLocaleString()}</span></div>}
                        {lead.email_clicked_at && <div><span className="text-slate-400">Clicked: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_clicked_at).toLocaleString()}</span></div>}
                        {lead.email_bounced_at && <div><span className="text-slate-400">Bounced: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_bounced_at).toLocaleString()}</span></div>}
                        {lead.email_blocked_at && <div><span className="text-slate-400">Blocked: </span><span className="text-muted-foreground font-mono">{new Date(lead.email_blocked_at).toLocaleString()}</span></div>}
                      </div>
                    )}
                  </div>
                )}
                {lead.website && (
                  <div className="flex items-center gap-2.5 text-muted-foreground">
                    <Globe className="h-4 w-4 text-primary" />
                    <a href={lead.website} target="_blank" rel="noopener noreferrer" className="text-foreground hover:underline break-all">
                      {lead.website}
                    </a>
                  </div>
                )}
                <div className="flex items-center gap-2.5 text-muted-foreground">
                  <MapPin className="h-4 w-4 text-primary" />
                  <span className="text-foreground">{lead.city || 'N/A'}, {lead.state || 'US'}</span>
                </div>
                <div className="flex items-center gap-2.5 text-muted-foreground">
                  <BookOpen className="h-4 w-4 text-primary" />
                  <span className="text-foreground">Category: {lead.business_type || 'N/A'}</span>
                </div>
              </div>

              {lead.is_dnc && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded flex gap-2 items-center">
                  <AlertTriangle className="h-4 w-4 flex-shrink-0" />
                  <span className="text-xs font-semibold uppercase tracking-wider">Number is on DNC Registry</span>
                </div>
              )}

            </CardContent>
          </Card>

          {/* Google Meet Appointment Details Card */}
          {appointments.length > 0 && (
            <Card className="bg-card border-purple-500/20 shadow-md">
              <CardHeader className="pb-2">
                <CardTitle className="text-md font-bold text-purple-400 flex items-center gap-1.5">
                  <Calendar className="h-4 w-4" /> Booked Discovery Meeting
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-xs">
                {appointments.map((appt: any) => (
                  <div key={appt.id} className="p-3 bg-purple-500/5 rounded border border-purple-500/10 space-y-2">
                    <p className="font-bold text-foreground">{appt.title}</p>
                    <p className="text-muted-foreground">
                      <strong>Date:</strong> {appt.meeting_date}
                    </p>
                    <p className="text-muted-foreground">
                      <strong>Time:</strong> {appt.meeting_time} ({appt.timezone})
                    </p>
                    {appt.cal_meeting_link && (
                      <a href={appt.cal_meeting_link} target="_blank" rel="noopener noreferrer" className="text-purple-400 font-bold hover:underline block mt-1">
                        Go to Google Meet Link
                      </a>
                    )}
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Internal Notes card */}
          <Card className="bg-card border-muted-foreground/10 shadow-md">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-bold text-foreground flex items-center gap-1.5">
                <FileText className="h-4 w-4 text-primary" /> Internal Representative Notes
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="bg-background/50 p-3 rounded text-xs font-mono max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed text-muted-foreground">
                {lead.internal_notes || 'No notes added yet.'}
              </div>
              <form onSubmit={handleNoteSubmit} className="flex gap-2">
                <Input
                  placeholder="Type a timed note..."
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  className="bg-background text-xs"
                />
                <Button type="submit" size="sm" className="px-3">
                  <Send className="h-3.5 w-3.5" />
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>

        {/* Right Side: Chronological Activity Timeline */}
        <div className="lg:col-span-2 space-y-6">
          <Card className="bg-card border-muted-foreground/10 shadow-lg">
            <CardHeader>
              <CardTitle className="text-lg font-bold">Chronological Call Logs & Activity Timeline</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6 relative pl-4 before:absolute before:left-6 before:top-4 before:bottom-4 before:w-0.5 before:bg-muted-foreground/10">
              
              {timeline.map((event: any, index: number) => (
                <div key={index} className="relative pl-8 space-y-2">
                  
                  {/* Icon Bullet */}
                  <div className="absolute left-0 top-1 h-5 w-5 bg-background border-2 border-primary rounded-full flex items-center justify-center">
                    {event.type === 'call' ? (
                      <Phone className="h-3 w-3 text-primary" />
                    ) : event.type === 'appointment' ? (
                      <Calendar className="h-3 w-3 text-purple-500" />
                    ) : event.type === 'email' ? (
                      <Mail className="h-3 w-3 text-green-500" />
                    ) : (
                      <Clock className="h-3 w-3 text-muted-foreground" />
                    )}
                  </div>

                  {/* Header */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5">
                    <p className="text-sm font-semibold text-foreground">{event.title}</p>
                    <span className="text-xs text-muted-foreground">{new Date(event.time).toLocaleString()}</span>
                  </div>

                  <p className="text-xs text-muted-foreground leading-relaxed">{event.detail}</p>

                  {/* Call Log Expandable Panel */}
                  {event.type === 'call' && event.call_id && (
                    <div className="border border-muted-foreground/15 rounded-lg overflow-hidden bg-background/30 mt-2">
                      <button
                        onClick={() => setExpandedCallId(expandedCallId === event.call_id ? null : event.call_id)}
                        className="w-full text-left px-3 py-2 text-xs font-bold text-primary flex items-center justify-between hover:bg-accent/40 transition-all"
                      >
                        <span>{expandedCallId === event.call_id ? 'Hide Call Analytics & Transcript' : 'Review Call Analytics & Transcript'}</span>
                        {expandedCallId === event.call_id ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                      </button>
                      
                      {expandedCallId === event.call_id && (
                        <div className="p-4 border-t border-muted-foreground/10 space-y-4 text-xs">
                          {event.ai_summary && (
                            <div className="p-3 bg-primary/5 border border-primary/10 rounded-lg">
                              <p className="font-bold text-primary mb-1">AI Generated Call Summary</p>
                              <p className="text-muted-foreground italic leading-relaxed">"{event.ai_summary}"</p>
                            </div>
                          )}
                          
                          <div className="space-y-2">
                            <p className="font-bold text-foreground">Interactive Transcript</p>
                            <div className="max-h-60 overflow-y-auto p-3 bg-background/50 rounded-lg space-y-2.5 font-sans leading-relaxed">
                              {event.transcript ? (
                                event.transcript.split('\n').map((line: string, lIdx: number) => {
                                  if (!line.trim()) return null;
                                  const isAI = line.startsWith('Sarah:') || line.startsWith('AI:') || line.startsWith('Alex:');
                                  const agentLabel = line.startsWith('Alex:') ? 'Alex (Reach Magnets)' : 'Sarah (Reach Magnets)';
                                  return (
                                    <div key={lIdx} className={`p-2 rounded max-w-[85%] ${isAI ? 'bg-primary/10 mr-auto text-left' : 'bg-accent border border-muted-foreground/10 ml-auto text-right'}`}>
                                      <p className="font-bold text-xs mb-0.5 text-primary">{isAI ? agentLabel : lead.full_name || 'Prospect'}</p>
                                      <p className="text-muted-foreground">{line.replace('Sarah:', '').replace('Alex:', '').replace('AI:', '').replace('Prospect:', '').trim()}</p>
                                    </div>
                                  );
                                })
                              ) : (
                                <p className="text-muted-foreground italic">No transcript recorded for this call attempt.</p>
                              )}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                </div>
              ))}

            </CardContent>
          </Card>
        </div>

      </div>
    </div>
  );
}
