'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  BarChart3, Play, Pause, Clock, CheckCircle,
  PlusCircle, AlertCircle, Users, RefreshCw, Mail, Phone, Linkedin, Sparkles
} from 'lucide-react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

interface Campaign {
  id: string;
  name: string;
  description?: string;
  status: 'draft' | 'active' | 'paused' | 'completed';
  campaign_type: 'call' | 'email' | 'linkedin';
  total_leads: number;
  total_called: number;
  total_answered: number;
  total_booked: number;
  total_pending?: number;
  total_unpicked?: number;
  email_sent?: number;
  email_delivered?: number;
  email_opened?: number;
  email_replied?: number;
  created_at: string;
}

const CAMPAIGN_TYPES = [
  {
    id: 'call',
    label: 'Call Campaign',
    icon: Phone,
    description: 'AI voice outbound calling to all leads',
    color: 'from-violet-500 to-purple-600',
    borderColor: 'border-violet-400',
    bgColor: 'bg-violet-500/10',
    textColor: 'text-violet-400',
  },
  {
    id: 'email',
    label: 'Email Campaign',
    icon: Mail,
    description: 'Personalised outreach emails with 45s delay',
    color: 'from-blue-500 to-cyan-600',
    borderColor: 'border-blue-400',
    bgColor: 'bg-blue-500/10',
    textColor: 'text-blue-400',
  },
  {
    id: 'linkedin',
    label: 'LinkedIn Campaign',
    icon: Linkedin,
    description: 'Automated LinkedIn connection & message outreach',
    color: 'from-sky-500 to-blue-700',
    borderColor: 'border-sky-400',
    bgColor: 'bg-sky-500/10',
    textColor: 'text-sky-400',
  },
] as const;

async function fetchCampaigns(): Promise<Campaign[]> {
  const response = await fetch(`/api/v1/campaigns/`);
  if (!response.ok) throw new Error('Failed to fetch campaigns');
  return response.json();
}

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function CampaignsPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/');
  }, [router]);
  
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Creation States
  const [isCreating, setIsCreating] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [campaignType, setCampaignType] = useState<'call' | 'email' | 'linkedin'>('call');
  const [selectedSources, setSelectedSources] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Lead scope options: 'all', 'all_email', 'unassigned', 'extracted_today', 'extracted_yesterday', 'unsent_today', 'unsent_yesterday', 'unsent_all', 'sources'
  const [leadScope, setLeadScope] = useState<'all' | 'all_email' | 'unassigned' | 'extracted_today' | 'extracted_yesterday' | 'unsent_today' | 'unsent_yesterday' | 'unsent_all' | 'sources'>('unassigned');

  const { data: sourcesData = [] } = useQuery({
    queryKey: ['lead_sources'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/leads/sources`);
      if (!res.ok) return [];
      return res.json();
    },
  });

  const { data: leadCounts } = useQuery({
    queryKey: ['lead_counts'],
    queryFn: async () => {
      const res = await fetch(`/api/v1/leads/counts`);
      if (!res.ok) return { total: 0, with_email: 0, with_phone: 0, unassigned: 0, extracted_today: 0, extracted_yesterday: 0, unsent_email_today: 0, unsent_email_yesterday: 0, unsent_email_all: 0 };
      return res.json();
    },
  });
  const totalLeads = leadCounts?.total || 0;
  const leadsWithEmail = leadCounts?.with_email || 0;
  const leadsWithPhone = leadCounts?.with_phone || 0;
  const unassignedCount = leadCounts?.unassigned || 0;
  const extractedToday = leadCounts?.extracted_today || 0;
  const extractedYesterday = leadCounts?.extracted_yesterday || 0;
  const unsentToday = leadCounts?.unsent_email_today || 0;
  const unsentYesterday = leadCounts?.unsent_email_yesterday || 0;
  const unsentAll = leadCounts?.unsent_email_all || 0;

  const { data: campaigns = [], isLoading, error } = useQuery({
    queryKey: ['campaigns'],
    queryFn: fetchCampaigns,
  });

  const filteredCampaigns = campaigns.filter((campaign: Campaign) => {
    const matchesSearch = campaign.name.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesStatus = statusFilter === 'all' || campaign.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const handleCreateCampaign = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsSubmitting(true);
    setErrorMsg(null);

    try {
      let queryParams = `?name=${encodeURIComponent(name)}&campaign_type=${campaignType}`;
      if (description) queryParams += `&description=${encodeURIComponent(description)}`;

      if (leadScope === 'all') {
        queryParams += `&assign_all=true`;
      } else if (leadScope === 'all_email') {
        queryParams += `&assign_all_with_email=true`;
      } else if (leadScope === 'unassigned') {
        queryParams += `&assign_unassigned=true`;
      } else if (['extracted_today', 'extracted_yesterday', 'unsent_today', 'unsent_yesterday', 'unsent_all'].includes(leadScope)) {
        queryParams += `&lead_scope=${leadScope}`;
      } else if (leadScope === 'sources') {
        selectedSources.forEach(source => {
          queryParams += `&source_files=${encodeURIComponent(source)}`;
        });
      }

      const createRes = await fetch(`/api/v1/campaigns${queryParams}`, {
        method: 'POST',
      });
      if (!createRes.ok) {
        let detail = 'Failed to create campaign';
        try { const j = await createRes.json(); detail = j.detail || detail; } catch {}
        throw new Error(detail);
      }

      // Reset
      setName('');
      setDescription('');
      setCampaignType('call');
      setLeadScope('unassigned');
      setSelectedSources([]);
      setIsCreating(false);
      queryClient.invalidateQueries({ queryKey: ['campaigns'] });
      queryClient.invalidateQueries({ queryKey: ['lead_counts'] });
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
    } catch (e) { console.error(e); }
  };

  const handlePauseCampaign = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/pause`, { method: 'POST' });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) { console.error(e); }
  };

  const handleResumeCampaign = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/resume`, { method: 'POST' });
      if (res.ok) queryClient.invalidateQueries({ queryKey: ['campaigns'] });
    } catch (e) { console.error(e); }
  };

  const handleRecampaign = async (id: string, resetAll: boolean = false) => {
    try {
      const res = await fetch(`/api/v1/campaigns/${id}/recampaign?reset_all=${resetAll}`, { method: 'POST' });
      if (res.ok) {
        queryClient.invalidateQueries({ queryKey: ['campaigns'] });
        alert(resetAll ? 'All leads (except booked) have been reset to pending!' : 'Unpicked leads have been reset to pending!');
      }
    } catch (e) {
      console.error(e);
      alert('Failed to recampaign. Please try again.');
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

  /** Resolve campaign_type for a campaign (DB field preferred, fallback legacy name detection) */
  const resolveCampaignType = (campaign: Campaign): 'call' | 'email' | 'linkedin' => {
    if (campaign.campaign_type) return campaign.campaign_type;
    const n = campaign.name.toLowerCase();
    if (n.includes('linkedin') || n.includes('linked in')) return 'linkedin';
    if (n.includes('email') || n.includes('e mail')) return 'email';
    return 'call';
  };

  const getCampaignTypeMeta = (ct: 'call' | 'email' | 'linkedin') =>
    CAMPAIGN_TYPES.find(t => t.id === ct) || CAMPAIGN_TYPES[0];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-foreground">Campaigns</h1>
        <p className="text-muted-foreground mt-2">
          Create and manage your AI calling, email outreach, and LinkedIn campaigns.
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
            <CardTitle>Create New Campaign</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateCampaign} className="space-y-6">

              {/* Campaign Type Selector */}
              <div className="flex flex-col gap-2">
                <label className="text-sm font-semibold">Campaign Type</label>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {CAMPAIGN_TYPES.map((type) => {
                    const Icon = type.icon;
                    const isSelected = campaignType === type.id;
                    return (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => setCampaignType(type.id as typeof campaignType)}
                        className={`relative flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer text-center
                          ${isSelected
                            ? `${type.borderColor} ${type.bgColor} shadow-md scale-[1.02]`
                            : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/30'
                          }`}
                      >
                        <div className={`p-2.5 rounded-lg ${isSelected ? type.bgColor : 'bg-muted/50'}`}>
                          <Icon className={`h-5 w-5 ${isSelected ? type.textColor : 'text-muted-foreground'}`} />
                        </div>
                        <div>
                          <p className={`text-sm font-semibold ${isSelected ? type.textColor : 'text-foreground'}`}>
                            {type.label}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5 leading-tight">{type.description}</p>
                        </div>
                        {isSelected && (
                          <div className={`absolute top-2 right-2 w-2 h-2 rounded-full ${type.textColor.replace('text-', 'bg-')}`} />
                        )}
                      </button>
                    );
                  })}
                </div>
                {campaignType === 'email' && (
                  <p className="text-xs text-amber-500 flex items-center gap-1 mt-1">
                    ⏱ Gmail safe mode: 45-second delay enforced between each email to protect your account.
                  </p>
                )}
              </div>

              {/* Name + Description */}
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

              {/* Lead Scope Selector */}
              <div className="flex flex-col gap-2 pt-2">
                <label className="text-sm font-semibold flex items-center gap-1.5">
                  <Users className="h-4 w-4 text-primary" /> Who to include in this campaign?
                </label>

                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2">
                  {/* Today's Extracted */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('extracted_today')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'extracted_today' ? 'border-indigo-500 bg-indigo-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'extracted_today' ? 'bg-indigo-500/20' : 'bg-muted/50'}`}>
                      <Sparkles className={`h-4 w-4 ${leadScope === 'extracted_today' ? 'text-indigo-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'extracted_today' ? 'text-indigo-500' : 'text-foreground'}`}>
                        Extracted Today
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{extractedToday.toLocaleString()}</span> leads extracted today
                      </p>
                    </div>
                  </button>

                  {/* Yesterday's Extracted */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('extracted_yesterday')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'extracted_yesterday' ? 'border-violet-500 bg-violet-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'extracted_yesterday' ? 'bg-violet-500/20' : 'bg-muted/50'}`}>
                      <Clock className={`h-4 w-4 ${leadScope === 'extracted_yesterday' ? 'text-violet-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'extracted_yesterday' ? 'text-violet-500' : 'text-foreground'}`}>
                        Extracted Yesterday
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{extractedYesterday.toLocaleString()}</span> leads from yesterday
                      </p>
                    </div>
                  </button>

                  {/* Remaining Unsent Today */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('unsent_today')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'unsent_today' ? 'border-cyan-500 bg-cyan-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'unsent_today' ? 'bg-cyan-500/20' : 'bg-muted/50'}`}>
                      <Mail className={`h-4 w-4 ${leadScope === 'unsent_today' ? 'text-cyan-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'unsent_today' ? 'text-cyan-500' : 'text-foreground'}`}>
                        Unsent Today
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{unsentToday.toLocaleString()}</span> emails pending from today
                      </p>
                    </div>
                  </button>

                  {/* Remaining Unsent Yesterday */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('unsent_yesterday')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'unsent_yesterday' ? 'border-emerald-500 bg-emerald-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'unsent_yesterday' ? 'bg-emerald-500/20' : 'bg-muted/50'}`}>
                      <Mail className={`h-4 w-4 ${leadScope === 'unsent_yesterday' ? 'text-emerald-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'unsent_yesterday' ? 'text-emerald-500' : 'text-foreground'}`}>
                        Unsent Yesterday
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{unsentYesterday.toLocaleString()}</span> emails pending from yesterday
                      </p>
                    </div>
                  </button>

                  {/* All Pending Unsent Emails */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('unsent_all')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'unsent_all' ? 'border-teal-500 bg-teal-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'unsent_all' ? 'bg-teal-500/20' : 'bg-muted/50'}`}>
                      <Mail className={`h-4 w-4 ${leadScope === 'unsent_all' ? 'text-teal-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'unsent_all' ? 'text-teal-500' : 'text-foreground'}`}>
                        All Unsent Emails
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{unsentAll.toLocaleString()}</span> total pending emails
                      </p>
                    </div>
                  </button>

                  {/* All with Email */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('all_email')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'all_email' ? 'border-blue-500 bg-blue-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'all_email' ? 'bg-blue-500/20' : 'bg-muted/50'}`}>
                      <Mail className={`h-4 w-4 ${leadScope === 'all_email' ? 'text-blue-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'all_email' ? 'text-blue-500' : 'text-foreground'}`}>
                        All with Email
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{leadsWithEmail.toLocaleString()}</span> total email leads
                      </p>
                    </div>
                  </button>

                  {/* Unassigned Only */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('unassigned')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'unassigned' ? 'border-amber-500 bg-amber-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'unassigned' ? 'bg-amber-500/20' : 'bg-muted/50'}`}>
                      <Clock className={`h-4 w-4 ${leadScope === 'unassigned' ? 'text-amber-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'unassigned' ? 'text-amber-500' : 'text-foreground'}`}>
                        Unassigned Only
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{unassignedCount.toLocaleString()}</span> unassigned leads
                      </p>
                    </div>
                  </button>

                  {/* All Leads */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('all')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'all' ? 'border-primary bg-primary/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'all' ? 'bg-primary/20' : 'bg-muted/50'}`}>
                      <Users className={`h-4 w-4 ${leadScope === 'all' ? 'text-primary' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'all' ? 'text-primary' : 'text-foreground'}`}>
                        All Leads
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        <span className="font-bold text-foreground">{totalLeads.toLocaleString()}</span> total leads in DB
                      </p>
                    </div>
                  </button>

                  {/* Source Files */}
                  <button
                    type="button"
                    onClick={() => setLeadScope('sources')}
                    className={`flex items-start gap-2.5 p-3 rounded-xl border-2 text-left transition-all duration-150
                      ${leadScope === 'sources' ? 'border-green-500 bg-green-500/10' : 'border-muted-foreground/20 hover:border-muted-foreground/40 hover:bg-muted/20'}`}
                  >
                    <div className={`mt-0.5 p-1.5 rounded-lg ${leadScope === 'sources' ? 'bg-green-500/20' : 'bg-muted/50'}`}>
                      <BarChart3 className={`h-4 w-4 ${leadScope === 'sources' ? 'text-green-500' : 'text-muted-foreground'}`} />
                    </div>
                    <div>
                      <p className={`text-xs font-bold ${leadScope === 'sources' ? 'text-green-500' : 'text-foreground'}`}>
                        Pick Source Files
                      </p>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        Select specific uploaded CSV files
                      </p>
                    </div>
                  </button>
                </div>

                {/* Source Files picker — shown only when 'sources' is selected */}
                {leadScope === 'sources' && (
                  <div className="mt-2">
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
                              <span className="text-xs text-muted-foreground">{source.unassigned} unassigned</span>
                            </label>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Warning for All Leads */}
                {leadScope === 'all' && (
                  <p className="text-xs text-amber-500 mt-1">
                    ⚠ This will reassign <strong>{totalLeads.toLocaleString()}</strong> leads (including those already in other campaigns) to this new campaign.
                  </p>
                )}
                {leadScope === 'all_email' && (
                  <p className="text-xs text-blue-500 mt-1">
                    📧 <strong>{leadsWithEmail.toLocaleString()}</strong> leads with email addresses will be included. Perfect for email campaigns.
                  </p>
                )}
              </div>

              {errorMsg && (
                <p className="text-sm text-red-500 flex items-center gap-1">
                  <AlertCircle className="h-4 w-4" /> {errorMsg}
                </p>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="outline" onClick={() => setIsCreating(false)}>Cancel</Button>
                <Button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? 'Creating...' : `Create ${getCampaignTypeMeta(campaignType).label}`}
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
            <p className="text-sm text-muted-foreground mb-4">Click &quot;New Campaign&quot; to create your first campaign.</p>
          </div>
        ) : (
          filteredCampaigns.map((campaign: Campaign) => {
            const ct = resolveCampaignType(campaign);
            const typeMeta = getCampaignTypeMeta(ct);
            const TypeIcon = typeMeta.icon;
            const callsMade = campaign.total_called || 0;
            const callsSuccessful = campaign.total_answered || 0;
            const successRate = callsMade > 0 ? ((callsSuccessful / callsMade) * 100).toFixed(1) : '0.0';

            return (
              <Card key={campaign.id} className="bg-card/30 border-muted-foreground/10">
                <CardHeader>
                  <div className="flex justify-between items-start">
                    <div className="flex items-start gap-3">
                      {/* Campaign type badge icon */}
                      <div className={`p-2 rounded-lg mt-0.5 ${typeMeta.bgColor}`}>
                        <TypeIcon className={`h-4 w-4 ${typeMeta.textColor}`} />
                      </div>
                      <div>
                        <CardTitle>{campaign.name}</CardTitle>
                        {campaign.description && (
                          <p className="text-sm text-muted-foreground mt-1">{campaign.description}</p>
                        )}
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${typeMeta.bgColor} ${typeMeta.textColor}`}>
                            {typeMeta.label}
                          </span>
                          <p className="text-xs text-muted-foreground">
                            Created {new Date(campaign.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
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
                  {/* Email Campaign Stats */}
                  {ct === 'email' && (
                    <div className="grid grid-cols-2 md:grid-cols-6 gap-4 text-center">
                      <div>
                        <p className="text-2xl font-bold">{campaign.total_leads || 0}</p>
                        <p className="text-xs text-muted-foreground">Contacts</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-amber-500">{campaign.total_pending || 0}</p>
                        <p className="text-xs text-muted-foreground">Pending</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-blue-500">{campaign.email_sent || 0}</p>
                        <p className="text-xs text-muted-foreground">Sent</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-green-500">{campaign.email_delivered || 0}</p>
                        <p className="text-xs text-muted-foreground">Delivered</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-purple-500">{campaign.email_opened || 0}</p>
                        <p className="text-xs text-muted-foreground">Opened</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-emerald-500">{campaign.email_replied || 0}</p>
                        <p className="text-xs text-muted-foreground">Replied</p>
                      </div>
                    </div>
                  )}

                  {/* LinkedIn Campaign Stats */}
                  {ct === 'linkedin' && (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
                      <div>
                        <p className="text-2xl font-bold">{campaign.total_leads || 0}</p>
                        <p className="text-xs text-muted-foreground">Contacts</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-amber-500">{campaign.total_pending || 0}</p>
                        <p className="text-xs text-muted-foreground">Pending</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-sky-500">{campaign.total_called || 0}</p>
                        <p className="text-xs text-muted-foreground">Messages Sent</p>
                      </div>
                      <div>
                        <p className="text-2xl font-bold text-purple-500">{campaign.total_booked || 0}</p>
                        <p className="text-xs text-muted-foreground">Booked Meetings</p>
                      </div>
                    </div>
                  )}

                  {/* Call Campaign Stats */}
                  {ct === 'call' && (
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
                  )}

                  <div className="mt-4 pt-4 border-t border-muted-foreground/10">
                    <div className="flex justify-between items-center">
                      <div>
                        {ct === 'call' && (
                          <>
                            <p className="text-sm font-medium">Answer / Success Rate</p>
                            <p className="text-2xl font-bold text-primary">{successRate}%</p>
                          </>
                        )}
                        {ct === 'email' && campaign.status === 'active' && (
                          <p className="text-xs text-amber-500">⏱ Sending with 45s delay per email</p>
                        )}
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