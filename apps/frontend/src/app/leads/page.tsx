'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Users, Search, Plus, Filter, Upload, AlertCircle, Eye, Star } from 'lucide-react';

async function fetchLeads({ search, status, priority, page }: { search: string; status: string; priority: string; page: number }) {
  let url = `/api/v1/leads/?page=${page}&limit=15`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (status && status !== 'all') url += `&status=${status}`;
  if (priority && priority !== 'all') url += `&priority=${priority}`;
  
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
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [importStatus, setImportStatus] = useState<string | null>(null);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['leads', { search, status, priority, page }],
    queryFn: () => fetchLeads({ search, status, priority, page }),
  });

  const importMutation = useMutation({
    mutationFn: uploadLeadsCSV,
    onSuccess: (resData) => {
      setImportStatus(`Successfully imported ${resData.imported} leads! (Skipped ${resData.skipped_dnc} on DNC, ${resData.errors} errors)`);
      queryClient.invalidateQueries({ queryKey: ['leads'] });
      queryClient.invalidateQueries({ queryKey: ['lead_sources'] });
      queryClient.invalidateQueries({ queryKey: ['unassigned_leads'] });
      setFile(null);
    },
    onError: (err: any) => {
      setImportStatus(`Import failed: ${err.message}`);
    }
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      setImportStatus(null);
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
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Users className="h-8 w-8 text-primary" /> Lead Profiles & CRM
          </h1>
          <p className="text-muted-foreground mt-1">Manage leads, track statuses, and audit calling outcomes.</p>
        </div>
        
        {/* CSV Import */}
        <Card className="max-w-md bg-card border-muted-foreground/10">
          <CardContent className="pt-6">
            <div className="flex flex-col gap-2">
              <label className="text-sm font-semibold flex items-center gap-1.5">
                <Upload className="h-4 w-4 text-primary" /> Bulk Upload CSV Leads
              </label>
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
                </select>
              </div>

              <select
                value={priority}
                onChange={(e) => { setPriority(e.target.value); setPage(1); }}
                className="bg-background border rounded px-2.5 py-1.5 text-sm"
              >
                <option value="all">All Priorities</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
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
                    <TableHead>Phone</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Priority</TableHead>
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
                      <TableCell className="text-sm font-mono">{lead.phone}</TableCell>
                      <TableCell>
                        <span className={`px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${getStatusColor(lead.status)}`}>
                          {lead.status.replace('_', ' ')}
                        </span>
                      </TableCell>
                      <TableCell className="text-sm">
                        <span className={getPriorityColor(lead.priority)}>{lead.priority}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-yellow-500">
                          <Star className="h-3.5 w-3.5 fill-current" />
                          <span className="text-sm font-bold">{lead.lead_score || 0}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {lead.last_called_at ? new Date(lead.last_called_at).toLocaleString() : 'Never'}
                      </TableCell>
                      <TableCell className="text-right">
                        <Link href={`/leads/${lead.id}`}>
                          <Button size="sm" variant="ghost" className="flex items-center gap-1 hover:text-primary">
                            <Eye className="h-4 w-4" /> CRM Profile
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
