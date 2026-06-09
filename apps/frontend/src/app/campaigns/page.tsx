'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { BarChart3, Play, Pause, Clock, CheckCircle, XCircle, PlusCircle, Upload, AlertCircle, Users, RefreshCw } from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

interface Campaign {
  id: string;
  name: string;
  description?: string;
  status: 'draft' | 'active' | 'paused' | 'completed';
  total_leads: number;
  total_called: number;
  total_answered: number;
  total_booked: number;
  total_pending?: number;
  total_unpicked?: number;
  created_at: string;
}

async function fetchCampaigns(): Promise<Campaign[]> {
  const response = await fetch(`/api/v1/campaigns/`);
  if (!response.ok) throw new Error('Failed to fetch campaigns');
  return response.json();
}

export default function CampaignsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  
  // Creation States
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [includeUnassigned, setIncludeUnassigned] = useState(false);

  const { data: sourcesData = [] } = useQuery({
    queryKey: ['lead_sources'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/leads/sources`);
      if (!res.ok) return [];
      return res.json();
    },
  });

  const { data: unassignedData } = useQuery({
    queryKey: ['unassigned_leads'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/leads/?campaign_id=unassigned&limit=1`);
      if (!res.ok) return { total: 0 };
      return res.json();
    },
  });
  const unassignedCount = unassignedData?.total || 0;

  const { data: campaigns = [], isLoading, error } = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
  });

  const filteredCampaigns = campaigns.filter(
    (campaign: Campaign) => {
      const matchesSearch = campaign.name.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || campaign.status === statusFilter;
      return matchesSearch && matchesStatus;
    }
  );

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;

    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      let queryParams = `?name=${encodeURIComponent(name)}&description=${encodeURIComponent(description)}`;
      if (includeUnassigned) {
        queryParams += `&assign_unassigned=true`;
      }
      if (selectedSources.length > 0) {
        selectedSources.forEach(source => {
          queryParams += `&source_files=${encodeURIComponent(source)}`;
        });
      }

      // 1. Create campaign
      const createRes = await fetch(`/api/v1/campaigns/${queryParams}`, {
        method: 'POST',
      });
      if (!createRes.ok) throw new Error('Failed to create campaign');

      // Reset
      setName('');
      setDescription('');
      setSelectedSources([]);
      setIncludeUnassigned(false);
      setIsCreating(false);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (err: any) {
      setErrorMsg(err.message || 'Something went wrong');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartCampaign = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/start`, { method: 'POST' });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) {
      console.error(e);
    }
  };

  const handlePauseCampaign = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/pause`, { method: 'POST' });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) {
      console.error(e);
    }
  };

  const handleResumeCampaign = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/resume`, { method: 'POST' });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) {
      console.error(e);
    }
  };

  const handleRecampaign = async (id: string, resetAll: boolean = false) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/recampaign?reset_all=${resetAll}`, { method: 'POST' });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['campaigns'] });
        alert(resetAll ? "All leads (except booked) have been reset to pending!" : "Unpicked leads have been reset to pending!");
      }
    } catch (e) {
      console.error(e);
      alert("Failed to recampaign. Please try again.");
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-500/10 text-green-500 border border-green-500/20';
      case 'paused': return 'bg-yellow-500/10 text-yellow-500 border border-yellow-500/20';
      case 'completed': return 'bg-blue-500/10 text-blue-500 border border-blue-500/20';
      default: return 'bg-gray-500/10 text-gray-500 border border-gray-500/20';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active': return <Play className="h-3 w-3 fill-current" />;
      case 'paused': return <Pause className="h-3 w-3" />;
      case 'completed': return <CheckCircle className="h-3 w-3" />;
      default: return <Clock className="h-3 w-3" />;
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Campaigns</h1>
        <p className="text-muted-foreground mt-2">
          Create and manage your AI voice calling campaigns and import contacts directly.
        </p>
      </div>

      {/* Filter and Create Button Row */}
      <div className="flex flex-col lg:flex-row gap-4">
        <div className="flex-1 relative">
          <Input
            type="search"
            placeholder="Search campaigns..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
          <div className="absolute left-3 top-2.5">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
        <div className="flex gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 bg-background border border-input rounded-md text-sm"
          >
            <option value="all">All Status</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="completed">Completed</option>
          </select>
          <Button onClick={() => setIsCreating(!isCreating)} className="flex items-center space-x-2">
            <PlusCircle className="h-4 w-4" />
            <span>New Campaign</span>
          </Button>
        </div>
      </div>

      {/* Campaign Creation Card (Toggled) */}
      {isCreating && (
        <Card className="border border-primary/20 bg-card/50">
          <CardHeader>
            <CardTitle>Create New Calling Campaign</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateCampaign} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-semibold">Campaign Name</label>
                  <Input 
                    placeholder="e.g. Roofers Outbound Pitch" 
                    value={name} 
                    onChange={e => setName(e.target.value)} 
                    required 
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-semibold">Description</label>
                  <Input 
                    placeholder="e.g. Calling local auto garages in Dallas" 
                    value={description} 
                    onChange={e => setDescription(e.target.value)} 
                  />
                </div>
              </div>

              <div className="flex flex-col gap-1.5 pt-2">
                <label className="text-sm font-semibold flex items-center gap-1.5">
                  <Users className="h-4 w-4 text-primary" /> Select Lead Files
                </label>
                {sourcesData.length === 0 ? (
                  <p className="text-sm text-muted-foreground border rounded-md p-3 bg-background/50">No uploaded lead files available.</p>
                ) : (
                  <div className="flex flex-col gap-2 max-h-40 overflow-y-auto border rounded-md p-3 bg-background">
                    {sourcesData.map((source: any) => (
                      <div key={source.source} className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          id={`source-${source.source}`}
                          checked={selectedSources.includes(source.source)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedSources([...selectedSources, source.source]);
                            } else {
                              setSelectedSources(selectedSources.filter(s => s !== source.source));
                            }
                          }}
                          className="w-4 h-4 text-primary rounded border-muted-foreground/30 accent-primary"
                        />
                        <label htmlFor={`source-${source.source}`} className="text-sm font-medium cursor-pointer flex-1 flex justify-between">
                          <span>{source.source}</span>
                          <span className="text-xs text-muted-foreground">{source.unassigned} unassigned leads</span>
                        </label>
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  Select previously uploaded CSV files to assign their unassigned leads to this campaign.
                </p>
              </div>

              {unassignedCount > 0 && (
                <div className="flex items-center gap-2 pt-1 pb-1">
                  <input
                    type="checkbox"
                    id="includeUnassigned"
                    checked={includeUnassigned}
                    onChange={(e) => setIncludeUnassigned(e.target.checked)}
                    className="w-4 h-4 text-primary rounded border-muted-foreground/30 accent-primary"
                  />
                  <label htmlFor="includeUnassigned" className="text-sm font-medium cursor-pointer">
                    Include <span className="font-bold text-primary">{unassignedCount}</span> existing unassigned leads from CRM
                  </label>
                </div>
              )}

              {errorMsg && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" /> {errorMsg}
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setIsCreating(false)}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating...' : 'Create Campaign'}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Campaigns List */}
      <div className="grid gap-6">
        {isLoading ? (
          <div className="text-center p-8">Loading campaigns...</div>
        ) : error ? (
          <div className="text-center p-8">Error loading campaigns.</div>
        ) : filteredCampaigns.length === 0 ? (
          <div className="text-center p-12 border-2 border-dashed border-muted-foreground/20 rounded-lg">
            <PlusCircle className="h-12 w-12 mx-auto mb-4 text-muted-foreground" />
            <h3 className="text-lg font-medium mb-1">No campaigns found</h3>
            <p className="text-sm text-muted-foreground mb-4">Click "New Campaign" to create your first calling campaign.</p>
          </div>
        ) : (
          filteredCampaigns.map((campaign: Campaign) => {
            const callsMade = campaign.total_called || 0;
            const callsSuccessful = campaign.total_answered || 0;
            const successRate = callsMade > 0 ? ((callsSuccessful / callsMade) * 100).toFixed(1) : "0.0";
            
            return (
              <Card key={campaign.id} className="bg-card/30 border-muted-foreground/10">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle>{campaign.name}</CardTitle>
                      {campaign.description && (
                        <p className="text-sm text-muted-foreground mt-1">{campaign.description}</p>
                      )}
                      <p className="text-xs text-muted-foreground mt-2">
                        Created {new Date(campaign.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-full flex items-center space-x-1 uppercase tracking-wider ${getStatusColor(campaign.status)}`}>
                        {getStatusIcon(campaign.status)}
                        <span>{campaign.status}</span>
                      </span>
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-bold">{campaign.total_leads || 0}</p>
                      <p className="text-xs text-muted-foreground">Contacts</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-amber-500">{campaign.total_pending || 0}</p>
                      <p className="text-xs text-muted-foreground">Pending</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-green-500">{campaign.total_answered || 0}</p>
                      <p className="text-xs text-muted-foreground">Picked / Answered</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-rose-500">{campaign.total_unpicked || 0}</p>
                      <p className="text-xs text-muted-foreground">Unpicked / Failed</p>
                    </div>
                    <div>
                      <p className="text-2xl font-bold text-purple-500">{campaign.total_booked || 0}</p>
                      <p className="text-xs text-muted-foreground">Booked Meetings</p>
                    </div>
                  </div>
                  <div className="mt-4 pt-4 border-t border-muted-foreground/10">
                    <div className="flex justify-between items-center">
                      <div>
                        <p className="text-sm font-medium">Answer / Success Rate</p>
                        <p className="text-2xl font-bold text-primary">{successRate}%</p>
                      </div>
                      <div className="flex space-x-2">
                        {campaign.total_unpicked !== undefined && campaign.total_unpicked > 0 && (
                          <Button variant="outline" size="sm" onClick={() => handleRecampaign(campaign.id, false)} className="border-indigo-200 text-indigo-700 hover:bg-indigo-50">
                            <RefreshCw className="h-3 w-3 mr-1.5" />
                            Recampaign Unpicked
                          </Button>
                        )}
                        {campaign.status !== 'active' && campaign.status !== 'draft' && (
                          <Button variant="outline" size="sm" onClick={() => handleRecampaign(campaign.id, true)} className="border-violet-200 text-violet-700 hover:bg-violet-50">
                            <RefreshCw className="h-3 w-3 mr-1.5" />
                            Recampaign All
                          </Button>
                        )}
                        {campaign.status === 'draft' && (
                          <Button variant="default" size="sm" onClick={() => handleStartCampaign(campaign.id)}>
                            <Play className="h-3 w-3 mr-1.5 fill-current" />
                            Start Campaign
                          </Button>
                        )}
                        {campaign.status === 'active' && (
                          <Button variant="outline" size="sm" onClick={() => handlePauseCampaign(campaign.id)}>
                            <Pause className="h-3 w-3 mr-1.5" />
                            Pause
                          </Button>
                        )}
                        {campaign.status === 'paused' && (
                          <Button variant="default" size="sm" onClick={() => handleResumeCampaign(campaign.id)}>
                            <Play className="h-3 w-3 mr-1.5 fill-current" />
                            Resume
                          </Button>
                        )}
                        {campaign.status === 'completed' && (
                          <span className="text-sm text-green-600 font-semibold px-3 py-1.5 bg-green-50 rounded-md">
                            Campaign Completed
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })
        )}
      </div>
    </div>
  );
}