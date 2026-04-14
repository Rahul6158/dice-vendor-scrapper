import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  LineChart, Line
} from 'recharts';
import { 
  LayoutDashboard, 
  Briefcase, 
  FileText, 
  Search, 
  ChevronDown, 
  Zap, 
  Users, 
  CheckCircle2, 
  TrendingUp,
  Inbox,
  AlertCircle,
  RefreshCw,
  Clock,
  MapPin,
  DollarSign,
  Building,
  ExternalLink,
  Bookmark,
  MoreHorizontal,
  Settings,
  Sliders,
  Save,
  RotateCcw,
  ChevronRight,
  ArrowLeft,
  Lock,
  Calendar,
  Activity,
  Trash2
} from 'lucide-react';
import axios from 'axios';
import { clsx } from 'clsx';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const API_KEY = import.meta.env.VITE_API_KEY || '';

// ─── JobDetailsDrawer ─────────────────────────────────────────────────────────
// Defined OUTSIDE App so React never remounts it on parent re-renders.
const JobDetailsDrawer = ({ job, onClose }) => {
  const [isClosing, setIsClosing] = useState(false);

  // Animate out, then fire the real onClose after the animation completes
  const handleClose = (e) => {
    if (e) e.stopPropagation();
    setIsClosing(true);
    setTimeout(() => {
      setIsClosing(false);
      onClose();
    }, 280); // matches CSS transition duration
  };

  if (!job) return null;

  const getWorkplaceBadgeClass = (wt) => {
    if (!wt) return 'drawer-badge';
    const v = wt.toLowerCase();
    if (v === 'remote') return 'drawer-badge badge-remote';
    if (v === 'hybrid') return 'drawer-badge badge-hybrid';
    return 'drawer-badge';
  };

  const containsHtml = (str) => str && /<[a-zA-Z][^>]*>/.test(str);

  const showToast = (msg) => {
    const el = document.createElement('div');
    el.className = 'share-toast';
    el.textContent = msg;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('share-toast--visible'));
    setTimeout(() => {
      el.classList.remove('share-toast--visible');
      setTimeout(() => el.remove(), 300);
    }, 2200);
  };

  const handleShare = async (e) => {
    e.stopPropagation();
    const shareData = {
      title: job.title || 'Job Opportunity',
      text: `${job.title} at ${job.company}${job.location ? ' — ' + job.location : ''}`,
      url: job.url,
    };
    try {
      if (navigator.share && navigator.canShare && navigator.canShare(shareData)) {
        await navigator.share(shareData);
      } else {
        await navigator.clipboard.writeText(job.url);
        showToast('✓ Job link copied to clipboard');
      }
    } catch {
      try {
        await navigator.clipboard.writeText(job.url);
        showToast('✓ Job link copied to clipboard');
      } catch {
        showToast('Could not copy link — open the console for the URL');
        console.log('Job URL:', job.url);
      }
    }
  };

  const empBadges = job.job_type
    ? job.job_type.split(',').map(t => t.trim()).filter(Boolean)
    : [];

  return (
    <div
      className={`drawer-overlay${isClosing ? ' drawer-overlay--closing' : ''}`}
      onClick={handleClose}
    >
      <div
        className={`details-drawer${isClosing ? ' details-drawer--closing' : ''}`}
        onClick={e => e.stopPropagation()}
      >

        {/* ── Dice-style header card ─────────────────────────────── */}
        <div className="drawer-job-header">
          {/* Row 1: Company + close + apply */}
          <div className="drawer-header-top">
            <div className="drawer-company-row">
              <div className="drawer-company-logo">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                  <rect width="24" height="24" rx="4" fill="#e2e8f0"/>
                  <path d="M6 18L12 6L18 18" stroke="#94a3b8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <span className="drawer-company-name">{job.company || 'N/A'}</span>
            </div>
            <div className="drawer-header-actions">
              {/* Share — functional */}
              <button className="drawer-icon-btn" title="Share job link" onClick={handleShare}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
              </button>
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer"
                className="drawer-apply-btn"
                onClick={e => e.stopPropagation()}
              >Apply Now</a>
              <button className="drawer-close-btn" onClick={handleClose} title="Close">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
          </div>

          {/* Row 2: Job title */}
          <h1 className="drawer-job-title">{job.title || 'Job Title'}</h1>

          {/* Row 3: Location • Posted */}
          <div className="drawer-subtitle">
            {job.location && <span>{job.location}</span>}
            {job.location && job.posted_date && <span className="drawer-dot">•</span>}
            {job.posted_date && (
              <span>Posted {job.posted_date?.slice(0, 10)}</span>
            )}
            {job.experience_required && (
              <>
                <span className="drawer-dot">•</span>
                <span>{job.experience_required}</span>
              </>
            )}
          </div>

          {/* Row 4: Badges */}
          <div className="drawer-badges-row">
            {empBadges.map(b => (
              <span key={b} className="drawer-badge">{b}</span>
            ))}
            {job.workplace_type && job.workplace_type !== 'N/A' && (
              <span className={getWorkplaceBadgeClass(job.workplace_type)}>
                {job.workplace_type}
              </span>
            )}
            {job.salary && (
              <span className="drawer-badge badge-salary">{job.salary}</span>
            )}
          </div>
        </div>

        {/* ── Scrollable body ────────────────────────────────────── */}
        <div className="drawer-content">
          {/* Skills */}
          {job.skills && (
            <div className="doc-section">
              <h3 className="doc-section-title">Skills</h3>
              <div className="skills-cloud">
                {job.skills.split(',').map(skill => (
                  <span key={skill.trim()} className="skill-chip">{skill.trim()}</span>
                ))}
              </div>
            </div>
          )}

          {job.skills && <div className="doc-divider" />}

          {/* Description — detect HTML anywhere, not just at start of string */}
          <div className="doc-section">
            <h3 className="doc-section-title">Job Description</h3>
            {containsHtml(job.description) ? (
              <div
                className="job-description-html"
                dangerouslySetInnerHTML={{ __html: job.description }}
              />
            ) : (
              <div style={{ fontSize: '14px', color: '#475569', lineHeight: '1.8', whiteSpace: 'pre-wrap' }}>
                {job.description || 'No description available.'}
              </div>
            )}
          </div>
        </div>

        {/* ── Sticky Apply Now footer ─────────────────────────────── */}
        <div className="drawer-footer">
          <a
            href={job.url}
            target="_blank"
            rel="noreferrer"
            className="drawer-apply-btn-full"
            onClick={e => e.stopPropagation()}
          >
            Apply Now
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ marginLeft: '8px' }}>
              <path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/>
              <polyline points="15 3 21 3 21 9"/>
              <line x1="10" y1="14" x2="21" y2="3"/>
            </svg>
          </a>
        </div>

      </div>
    </div>
  );
};


const App = () => {
  const [activeTab, setActiveTab] = useState('candidate-matching');
  const [stats, setStats] = useState({
    jobs_scraped_today: 0,
    new_jobs: 0,
    matched_candidates: 0,
    tailored_resumes: 0,
    total_jobs: 0
  });
  const [jobs, setJobs] = useState([]);
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState({ status: 'idle' });
  const [loading, setLoading] = useState(false);
  
  // Filter States
  const [searchQuery, setSearchQuery] = useState('');
  const [filterCompany, setFilterCompany] = useState('All Companies');
  const [filterLocation, setFilterLocation] = useState('All Locations');
  const [filterBadge, setFilterBadge] = useState('All Badges');
  const [showType, setShowType] = useState('both');
  const [selectedJob, setSelectedJob] = useState(null);
  const [rowsPerPage, setRowsPerPage] = useState(10);
  const [tablePage, setTablePage] = useState(1);
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'cards'

  // ── Settings State ──
  const [scrapeSettings, setScrapeSettings] = useState(null);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsMsg, setSettingsMsg] = useState(null);
  const [clearMsg, setClearMsg] = useState(null);
  const [clearingData, setClearingData] = useState(false);
  const [clearSheets, setClearSheets] = useState({ active: true, inactive: true });
  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [settingsSubTab, setSettingsSubTab] = useState('menu'); // 'menu' | 'scraper'
  const [prevTab, setPrevTab] = useState('candidate-matching');

  // ── Sidebar open/close ──
  const [sidebarOpen, setSidebarOpen] = useState(true);

  useEffect(() => {
    fetchStatus();
    if (activeTab === 'candidate-matching') fetchStats();
    if (activeTab === 'job-board' && jobs.length === 0) loadInitialJobs();
    if (activeTab === 'settings' && !scrapeSettings) fetchSettings();
    const interval = setInterval(() => { fetchStatus(); }, 15000);
    return () => clearInterval(interval);
  }, [activeTab]);

  const filteredJobs = jobs.filter(job => {
    const jobTitle = (job.title || '').toLowerCase();
    const jobCompany = (job.company || '').trim();
    const jobLocation = (job.location || '').trim();
    const query = searchQuery.toLowerCase().trim();

    const matchesSearch = query === '' || 
                         jobTitle.includes(query) || 
                         jobCompany.toLowerCase().includes(query);
    
    const matchesCompany = filterCompany === 'All Companies' || jobCompany === filterCompany;
    const matchesLocation = filterLocation === 'All Locations' || jobLocation === filterLocation;
    
    const matchesBadge = filterBadge === 'All Badges' || 
                        (job.workplace_type && job.workplace_type.trim() === filterBadge) || 
                        (job.job_type && job.job_type.trim() === filterBadge);
    
    const matchesType = showType === 'both' || job.type === showType;

    return matchesSearch && matchesCompany && matchesLocation && matchesBadge && matchesType;
  });

  // Derive unique company/location options from ALL loaded jobs (not filtered)
  // so dropdowns stay complete regardless of other active filters
  const getUniqueValues = (key, label) => {
    const values = jobs.map(j => (j[key] || '').trim()).filter(Boolean);
    const unique = [...new Set(values)].sort();
    return ['All ' + label, ...unique];
  };

  const getUniqueBadges = () => {
    const badges = [];
    jobs.forEach(j => {
      if (j.workplace_type) badges.push(j.workplace_type.trim());
      if (j.job_type) badges.push(j.job_type.trim());
    });
    const unique = [...new Set(badges)].sort();
    return ['All Badges', ...unique];
  };

  const fetchStats = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/stats`, {
        headers: { 'X-API-Key': API_KEY }
      });
      setStats(res.data);
    } catch (err) {
      console.error('Failed to fetch stats', err);
    }
  };

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/status`, {
        headers: { 'X-API-Key': API_KEY }
      });
      setStatus(res.data);
    } catch (err) {
      console.error('Failed to fetch status', err);
    }
  };

  const loadInitialJobs = () => {
    setJobs([]);
    setPage(1);
    fetchJobs(1, true);
  };

  const fetchJobs = async (pageToFetch = page, isInitial = false) => {
    setLoading(true);
    try {
      const targetPage = isInitial ? 1 : pageToFetch;
      // Load a large batch so all jobs are available for client-side filtering
      const res = await axios.get(`${API_BASE_URL}/jobs?page=${targetPage}&limit=200`, {
        headers: { 'X-API-Key': API_KEY }
      });
      
      if (isInitial) {
        setJobs(res.data.jobs);
        setPage(2);
      } else {
        setJobs(prev => [...prev, ...res.data.jobs]);
        setPage(prev => prev + 1);
      }
    } catch (err) {
      console.error('Failed to fetch jobs', err);
    } finally {
      setLoading(false);
    }
  };

  const triggerScrape = async () => {
    try {
      await axios.post(`${API_BASE_URL}/trigger`, {}, { headers: { 'X-API-Key': API_KEY } });
      fetchStatus();
    } catch (err) {
      console.error('Trigger scrape failed', err);
      alert('Failed to trigger scrape: ' + (err.response?.data?.detail || err.message));
    }
  };

  const fetchSettings = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/settings`, { headers: { 'X-API-Key': API_KEY } });
      setScrapeSettings(res.data);
    } catch (err) {
      console.error('Failed to fetch settings', err);
    }
  };

  const saveSettings = async () => {
    setSettingsSaving(true);
    setSettingsMsg(null);
    try {
      const res = await axios.post(`${API_BASE_URL}/settings`, scrapeSettings, { headers: { 'X-API-Key': API_KEY } });
      setScrapeSettings(res.data.config);
      setSettingsMsg({ type: 'success', text: '✓ Settings saved — will apply on next scrape run.' });
    } catch (err) {
      setSettingsMsg({ type: 'error', text: 'Failed to save: ' + (err.response?.data?.detail || err.message) });
    } finally {
      setSettingsSaving(false);
      setTimeout(() => setSettingsMsg(null), 4000);
    }
  };

  const clearData = async () => {
    const selected = Object.entries(clearSheets).filter(([, v]) => v).map(([k]) => k === 'active' ? 'active-scraped-data' : 'inactive-scraped-data');
    if (selected.length === 0) {
      setClearMsg({ type: 'error', text: 'Please select at least one sheet to clear.' });
      return;
    }
    setShowClearConfirm(true);
  };

  const confirmClearData = async () => {
    setShowClearConfirm(false);
    setClearingData(true);
    setClearMsg(null);
    try {
      await axios.post(`${API_BASE_URL}/clear-data`, {}, { headers: { 'X-API-Key': API_KEY } });
      const cleared = clearSheets.active && clearSheets.inactive ? 'Both sheets' : (clearSheets.active ? 'Active' : 'Inactive');
      setClearMsg({ type: 'success', text: `✓ ${cleared} cleared.` });
      fetchStats();
    } catch (err) {
      setClearMsg({ type: 'error', text: 'Failed to clear: ' + (err.response?.data?.message || err.message) });
    } finally {
      setClearingData(false);
      setTimeout(() => setClearMsg(null), 4000);
    }
  };

  const getChartData = () => {
    const counts = jobs.reduce((acc, job) => {
      const type = job.workplace_type || 'Unknown';
      acc[type] = (acc[type] || 0) + 1;
      return acc;
    }, {});
    
    return Object.entries(counts).map(([name, count]) => ({
      name,
      jobs: count,
      amt: count
    }));
  };

  const renderCandidateMatching = () => (
    <div className="dashboard-content">
      <div className="stats-grid">
        <div className="stat-card card-blue">
          <div className="stat-info">
            <span>Total Matches</span>
            <div className="stat-value">{stats.total_jobs}</div>
            <div className="stat-subtext">Across {stats.jobs_scraped_today} today</div>
          </div>
          <div className="stat-icon"><Briefcase size={24} /></div>
        </div>
        <div className="stat-card card-green">
          <div className="stat-info">
            <span>Avg Match Score</span>
            <div className="stat-value">84%</div>
            <div className="stat-subtext">Active matching</div>
          </div>
          <div className="stat-icon"><TrendingUp size={24} /></div>
        </div>
        <div className="stat-card card-purple">
          <div className="stat-info">
            <span>Resumes Tailored</span>
            <div className="stat-value">{stats.tailored_resumes}</div>
            <div className="stat-subtext">AI optimised</div>
          </div>
          <div className="stat-icon"><FileText size={24} /></div>
        </div>
        <div className="stat-card card-amber">
          <div className="stat-info">
            <span>Apps Submitted</span>
            <div className="stat-value">{stats.matched_candidates}</div>
            <div className="stat-subtext">Successfully routed</div>
          </div>
          <div className="stat-icon"><CheckCircle2 size={24} /></div>
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <div className="section-title">
            <Users size={20} color="#6366f1" />
            <h3>Candidate Pool</h3>
            <span className="badge">{stats.matched_candidates}</span>
          </div>
          <div className="flex gap-2">
            <div className="search-wrapper" style={{ width: '200px' }}>
              <Search size={16} className="search-icon" />
              <input type="text" className="search-input" placeholder="Search candidate..." />
            </div>
            <select className="select-filter">
              <option>All Tiers</option>
            </select>
          </div>
        </div>
        <div className="empty-state">
          <Users className="empty-state-icon" />
          <p>No candidates matches found for the current job filters.</p>
        </div>
      </div>

      <div className="section-card">
        <div className="section-header">
          <div className="section-title">
            <TrendingUp size={20} color="#6366f1" />
            <h3>Workplace Distribution</h3>
          </div>
        </div>
        <div className="priority-chart-container">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={getChartData().length > 0 ? getChartData() : [
                { name: 'Remote', jobs: 0 },
                { name: 'On-site', jobs: 0 },
                { name: 'Hybrid', jobs: 0 },
              ]}
              margin={{ top: 20, right: 30, left: 20, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="name" axisLine={false} tickLine={false} />
              <YAxis axisLine={false} tickLine={false} />
              <Tooltip />
              <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
              <Bar dataKey="jobs" fill="#6366f1" radius={[4, 4, 0, 0]} barSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );


  const renderJobBoard = () => {
    const getWorkplaceBadgeClass = (wt) => {
      if (!wt) return 'type-badge';
      const v = wt.toLowerCase();
      if (v === 'remote') return 'remote-badge';
      if (v === 'hybrid') return 'hybrid-badge';
      if (v === 'on-site') return 'onsite-badge';
      return 'type-badge';
    };

    // Reset to first page whenever filters change
    const resetTablePage = () => setTablePage(1);

    const totalPages = Math.max(1, Math.ceil(filteredJobs.length / rowsPerPage));
    const safePage   = Math.min(tablePage, totalPages);
    const start      = (safePage - 1) * rowsPerPage;
    const pageJobs   = filteredJobs.slice(start, start + rowsPerPage);

    return (
      <div className="dashboard-content">

        {/* ── Filter Card ── */}
        <div className="jb-filter-card">
          <div className="jb-filter-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/></svg>
            FILTERS
          </div>
          <div className="jb-filter-row">
            {/* Search */}
            <div className="jb-search-wrap">
              <Search size={14} className="jb-search-icon" />
              <input
                type="text"
                className="jb-search-input"
                placeholder="Search job titles..."
                value={searchQuery}
                onChange={(e) => { setSearchQuery(e.target.value); resetTablePage(); }}
              />
            </div>
            {/* Location */}
            <select className="jb-select" value={filterLocation} onChange={(e) => { setFilterLocation(e.target.value); resetTablePage(); }}>
              {getUniqueValues('location', 'Locations').map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            {/* Workplace Type */}
            <select className="jb-select" value={filterBadge} onChange={(e) => { setFilterBadge(e.target.value); resetTablePage(); }}>
              {getUniqueBadges().map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            {/* Company */}
            <select className="jb-select" value={filterCompany} onChange={(e) => { setFilterCompany(e.target.value); resetTablePage(); }}>
              {getUniqueValues('company', 'Companies').map(v => <option key={v} value={v}>{v}</option>)}
            </select>
            {/* Status: Active / Inactive / Both */}
            <select className="jb-select" value={showType} onChange={(e) => { setShowType(e.target.value); resetTablePage(); }}>
              <option value="both">All Sources</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
            </select>
            {/* Refresh */}
            <button className="jb-refresh-btn" onClick={loadInitialJobs} title="Refresh data">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            </button>
          </div>
        </div>

        {/* ── Table Card ── */}
        <div className="job-table-wrapper">
          {loading && jobs.length === 0 ? (
            <div className="jb-loading">Loading jobs…</div>
          ) : filteredJobs.length === 0 ? (
            <div className="empty-state">
              <Briefcase className="empty-state-icon" />
              <p>No jobs found matching your filters.</p>
              <button className="jb-clear-btn" onClick={() => {
                setSearchQuery(''); setFilterCompany('All Companies');
                setFilterLocation('All Locations'); setFilterBadge('All Badges'); setShowType('both');
              }}>Clear Filters</button>
            </div>
          ) : (
            <>
              {/* Toolbar: count + rows-per-page + view toggle */}
              <div className="jb-table-toolbar">
                <div className="jb-rows-select">
                  <span className="jb-result-count">{filteredJobs.length} jobs</span>
                  {viewMode === 'table' && (
                    <>
                      <span style={{ color: '#cbd5e1', margin: '0 4px' }}>·</span>
                      <label>Rows:</label>
                      <select
                        className="pagination-select"
                        value={rowsPerPage}
                        onChange={(e) => { setRowsPerPage(Number(e.target.value)); setTablePage(1); }}
                      >
                        {[5, 10, 25, 50].map(n => <option key={n} value={n}>{n}</option>)}
                      </select>
                    </>
                  )}
                </div>
                {/* Table / Cards toggle */}
                <div className="view-toggle">
                  <button
                    className={`view-toggle-btn ${viewMode === 'table' ? 'active' : ''}`}
                    onClick={() => setViewMode('table')}
                    title="Table view"
                  >
                    {/* List icon */}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <line x1="3" y1="6"  x2="21" y2="6" />
                      <line x1="3" y1="12" x2="21" y2="12"/>
                      <line x1="3" y1="18" x2="21" y2="18"/>
                    </svg>
                    Table
                  </button>
                  <button
                    className={`view-toggle-btn ${viewMode === 'cards' ? 'active' : ''}`}
                    onClick={() => setViewMode('cards')}
                    title="Cards view"
                  >
                    {/* Grid icon */}
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                      <rect x="3" y="3" width="7" height="7" rx="1"/>
                      <rect x="14" y="3" width="7" height="7" rx="1"/>
                      <rect x="3" y="14" width="7" height="7" rx="1"/>
                      <rect x="14" y="14" width="7" height="7" rx="1"/>
                    </svg>
                    Cards
                  </button>
                </div>
              </div>

              {viewMode === 'table' ? (
                /* ── TABLE VIEW ── */
                <div className="job-table-scroll">
                  <table className="job-table">
                    <thead>
                      <tr>
                        <th style={{ minWidth: 200 }}>Job Title</th>
                        <th style={{ minWidth: 140 }}>Company</th>
                        <th style={{ minWidth: 110 }}>Location</th>
                        <th style={{ minWidth: 150 }}>Type</th>
                        <th style={{ minWidth: 75  }}>WP</th>
                        <th style={{ minWidth: 120 }}>Salary</th>
                        <th style={{ minWidth: 60  }}>Posted</th>
                        <th style={{ minWidth: 80  }}>Status</th>
                        <th style={{ minWidth: 65  }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageJobs.map((job, i) => (
                        <tr key={start + i} onClick={() => setSelectedJob(job)}>
                          <td>
                            <div className="jt-title" title={job.title}>{job.title || '—'}</div>
                            {job.experience_required && <div className="jt-sub">{job.experience_required}</div>}
                          </td>
                          <td className="jt-company jt-clamp" title={job.company}>{job.company || '—'}</td>
                          <td className="jt-location jt-clamp" title={job.location}>{job.location || '—'}</td>
                          <td>{job.job_type ? <span className="jt-badge type-badge jt-clamp" title={job.job_type}>{job.job_type}</span> : '—'}</td>
                          <td>{job.workplace_type && job.workplace_type !== 'N/A' ? <span className={`jt-badge ${getWorkplaceBadgeClass(job.workplace_type)}`}>{job.workplace_type}</span> : '—'}</td>
                          <td className="jt-salary jt-clamp" title={job.salary}>{job.salary || '—'}</td>
                          <td className="jt-date">{job.posted_date ? job.posted_date.slice(5, 10) : '—'}</td>
                          <td><span className={`jt-badge ${job.type === 'active' ? 'active-badge' : 'inactive-badge'}`}>{job.type === 'active' ? 'Active' : 'Inactive'}</span></td>
                          <td><button className="jt-apply-btn" onClick={(e) => { e.stopPropagation(); window.open(job.url, '_blank'); }}>Apply</button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                /* ── CARDS VIEW ── */
                <div className="jb-cards-grid">
                  {pageJobs.map((job, i) => {
                    const initials = (job.company || '?').trim().slice(0, 2).toUpperCase();
                    const hues = [210, 250, 170, 30, 340, 190, 280];
                    const hue = hues[(job.company || '').charCodeAt(0) % hues.length];
                    return (
                      <div key={start + i} className="jb-card" onClick={() => setSelectedJob(job)}>
                        {/* Card header */}
                        <div className="jb-card-header">
                          <div className="jb-card-avatar" style={{ background: `hsl(${hue},60%,92%)`, color: `hsl(${hue},60%,35%)` }}>
                            {initials}
                          </div>
                          <div className="jb-card-meta">
                            <div className="jb-card-company">{job.company || '—'}</div>
                            <div className="jb-card-date">{job.posted_date ? job.posted_date.slice(5, 10) : '—'}</div>
                          </div>
                          <span className={`jt-badge ${job.type === 'active' ? 'active-badge' : 'inactive-badge'}`} style={{ marginLeft: 'auto', flexShrink: 0 }}>
                            {job.type === 'active' ? 'Active' : 'Inactive'}
                          </span>
                        </div>

                        {/* Title */}
                        <div className="jb-card-title">{job.title || '—'}</div>
                        {job.experience_required && <div className="jb-card-exp">{job.experience_required}</div>}

                        {/* Badges row */}
                        <div className="jb-card-badges">
                          {job.workplace_type && job.workplace_type !== 'N/A' && (
                            <span className={`jt-badge ${getWorkplaceBadgeClass(job.workplace_type)}`}>{job.workplace_type}</span>
                          )}
                          {job.job_type && (
                            <span className="jt-badge type-badge">{job.job_type}</span>
                          )}
                          {job.location && (
                            <span className="jb-card-location">
                              <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
                              {job.location}
                            </span>
                          )}
                        </div>

                        {/* Footer */}
                        <div className="jb-card-footer">
                          <span className="jb-card-salary">{job.salary || 'Salary not specified'}</span>
                          <button
                            className="jt-apply-btn"
                            onClick={(e) => { e.stopPropagation(); window.open(job.url, '_blank'); }}
                          >Apply</button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Pagination — same for both views */}
              <div className="pagination-bar">
                <button className="pagination-btn" onClick={() => setTablePage(p => Math.max(1, p - 1))} disabled={safePage === 1}>← Prev</button>
                <span className="pagination-count" style={{ margin: '0 12px' }}>Page {safePage} of {totalPages}</span>
                <button className="pagination-btn" onClick={() => setTablePage(p => Math.min(totalPages, p + 1))} disabled={safePage === totalPages}>Next →</button>
              </div>
            </>
          )}
        </div>

        <JobDetailsDrawer job={selectedJob} onClose={() => setSelectedJob(null)} />
      </div>
    );
  };

  const renderResumeReview = () => (
    <div className="dashboard-content">
      <div className="tabs">
        <div className="tab active"><AlertCircle size={16} /> Pending Action <span className="badge">0</span></div>
        <div className="tab"><Clock size={16} /> In Review</div>
        <div className="tab"><CheckCircle2 size={16} /> Resolved</div>
      </div>
      <div className="section-card">
        <div className="empty-state">
          <Inbox className="empty-state-icon" />
          <h3 style={{ color: '#1e293b', marginBottom: '8px' }}>All caught up</h3>
          <p>No resumes currently in this state.</p>
        </div>
      </div>
    </div>
  );

  const DATE_OPTIONS = [
    { value: 'ONE',    label: 'Last 24 hours',  desc: 'Only jobs posted in the last 24 hours' },
    { value: 'THREE',  label: 'Last 3 days',    desc: 'Jobs posted in the last 3 days' },
    { value: 'SEVEN',  label: 'Last 7 days',    desc: 'Jobs posted in the last 7 days' },
    { value: 'THIRTY', label: 'Last 30 days',   desc: 'Jobs posted in the last 30 days' },
  ];

  // Auto-suggest max pages based on date range (approx. 10 jobs/page on Dice)
  const suggestedPages = { ONE: 10, THREE: 30, SEVEN: 50, THIRTY: 150 };

  const renderSettings = () => {
    if (settingsSubTab === 'menu') {
      return (
        <div className="dashboard-content">
          <div className="settings-hub-grid">
            <div className="settings-hub-card" onClick={() => setSettingsSubTab('scraper')}>
              <div className="hub-card-icon" style={{ background: 'linear-gradient(135deg, #6366f1, #4f46e5)', color: 'white' }}>
                 <Settings size={28} />
              </div>
              <div className="hub-card-content">
                 <h3>Scraper Parameters</h3>
                 <p>Fine-tune date filters, pagination limits, and worker counts.</p>
              </div>
              <ChevronRight size={20} className="hub-card-arrow" />
            </div>
            
            <div className="settings-hub-card" onClick={() => setSettingsSubTab('scheduler')}>
              <div className="hub-card-icon" style={{ background: 'linear-gradient(135deg, #10b981, #059669)', color: 'white' }}>
                 <Calendar size={28} />
              </div>
              <div className="hub-card-content">
                 <h3>Automation Schedule</h3>
                 <p>Manage daily run times and automated scraping windows.</p>
              </div>
              <ChevronRight size={20} className="hub-card-arrow" />
            </div>

            <div className="settings-hub-card disabled">
              <div className="hub-card-icon" style={{ background: '#f1f5f9', color: '#94a3b8' }}>
                 <LayoutDashboard size={28} />
              </div>
              <div className="hub-card-content">
                 <h3>Interface Preferences</h3>
                 <p>Appearance, notifications, and dashboard display options.</p>
              </div>
              <Lock size={16} className="hub-card-lock" />
            </div>
          </div>
          
          <div style={{ marginTop: '40px', borderTop: '1px solid #e2e8f0', paddingTop: '24px' }}>
             <button className="settings-back-btn" onClick={() => setActiveTab('candidate-matching')}>
                <ArrowLeft size={14} />
                Return to Dashboard
             </button>
          </div>
        </div>
      );
    }

    if (!scrapeSettings) return <div className="jb-loading">Loading settings…</div>;
    const s = scrapeSettings;
    const update = (key, val) => setScrapeSettings(prev => ({ ...prev, [key]: val }));

    return (
      <div className="dashboard-content">
        <div className="settings-header-nav" style={{ justifyContent: 'space-between' }}>
           <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
             <button className="settings-back-btn" onClick={() => setSettingsSubTab('menu')}>
                <ArrowLeft size={14} /> 
                Settings Menu
             </button>
             <div className="settings-nav-breadcrumb">
               <span>Settings</span> {" / "} <span>{settingsSubTab === 'scraper' ? 'Scraper Parameters' : 'Automation Schedule'}</span>
             </div>
           </div>

           <div className="settings-header-actions">
              {settingsMsg && (
                <span className={`settings-msg ${settingsMsg.type}`} style={{ marginRight: '16px' }}>{settingsMsg.text}</span>
              )}
              <button
                className="settings-save-btn"
                onClick={saveSettings}
                disabled={settingsSaving}
              >
                <Save size={15} />
                {settingsSaving ? 'Saving…' : 'Save Changes'}
              </button>
           </div>
        </div>

        <div className="settings-grid">
          {settingsSubTab === 'scraper' && (
            <>
              {/* Scraper Vitals & Analytics */}
              <div className="settings-card full-width vitals-card">
                 <div className="settings-card-header">
                   <div className="settings-card-icon" style={{ background: status.status === 'running' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(16, 185, 129, 0.1)', color: status.status === 'running' ? '#3b82f6' : '#10b981' }}>
                      <Activity size={18} className={status.status === 'running' ? 'animate-pulse' : ''} />
                   </div>
                   <div style={{ flex: 1, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <div className="settings-card-title">Scraper Vitals & Analytics</div>
                        <div className="settings-card-desc">
                          {status.status === 'running' ? `Agents are currently: ${status.current_task}` : 'System is idle. Diagnostic data from last session available.'}
                        </div>
                      </div>
                      <div className="scheduler-health-badge" style={{ background: stats?.scheduler_next_run === 'Disabled' ? '#f1f5f9' : '#f0fdf4', color: stats?.scheduler_next_run === 'Disabled' ? '#64748b' : '#15803d' }}>
                         <Clock size={12} />
                         <span>Next Run: {stats?.scheduler_next_run}</span>
                      </div>
                   </div>
                  </div>
                  
                  {status.status === 'running' && (
                    <div className="scraper-progress-container" style={{ margin: '16px 0' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontSize: '12px', color: '#64748b' }}>
                        <span>Progress</span>
                        <span>{status.progress}%</span>
                      </div>
                      <div className="progress-bar-bg" style={{ height: '8px', background: '#e2e8f0', borderRadius: '4px', overflow: 'hidden' }}>
                        <div className="progress-bar-fill" style={{ 
                          width: `${status.progress}%`, 
                          height: '100%', 
                          background: 'linear-gradient(90deg, #3b82f6, #10b981)', 
                          borderRadius: '4px',
                          transition: 'width 0.3s ease'
                        }} />
                      </div>
                      <div style={{ marginTop: '8px', fontSize: '12px', color: '#64748b' }}>
                        {status.current_task}
                      </div>
                    </div>
                  )}
                  
                  <div className="vitals-dashboard">
                    <div className="vitals-grid">
                       {/* Performance Highlights */}
                       <div className="vitals-tile">
                          <div className="vitals-tile-lbl">Recently Scraped Active</div>
                          <div className="vitals-tile-val" style={{ color: '#10b981' }}>{status.last_active_count || 0}</div>
                       </div>
                       <div className="vitals-tile">
                          <div className="vitals-tile-lbl">Recently Scraped Inactive</div>
                          <div className="vitals-tile-val" style={{ color: '#3b82f6' }}>{status.last_inactive_count || 0}</div>
                       </div>
                       <div className="vitals-tile lifetime">
                          <div className="vitals-tile-lbl">Total Jobs Active</div>
                          <div className="vitals-tile-val">{stats?.total_active || 0}</div>
                       </div>
                       <div className="vitals-tile lifetime">
                          <div className="vitals-tile-lbl">Total Jobs Inactive</div>
                          <div className="vitals-tile-val">{stats?.total_inactive || 0}</div>
                       </div>
                    </div>

<div className="vitals-footer-stats">
                        <span>Heartbeat: Optimal</span>
                        <span>•</span>
                        <span>Next Run: {stats?.scheduler_next_run || 'Unknown'}</span>
                        <span>•</span>
                        <span>Last Run: {status.last_run_at ? new Date(status.last_run_at * 1000).toLocaleTimeString() : 'N/A'}</span>
                     </div>
                  </div>
               </div>

               {/* Date Range Card */}
              <div className="settings-card">
                <div className="settings-card-header">
                  <div className="settings-card-icon" style={{ background: 'hsl(250,80%,95%)', color: 'hsl(250,70%,50%)' }}>
                    <Clock size={18} />
                  </div>
                  <div>
                    <div className="settings-card-title">Date Range</div>
                    <div className="settings-card-desc">How far back to look for new job postings</div>
                  </div>
                </div>
                <div className="settings-date-options">
                  {DATE_OPTIONS.map(opt => (
                    <label
                      key={opt.value}
                      className={`settings-date-option ${s.date_range === opt.value ? 'selected' : ''}`}
                      onClick={() => {
                        update('date_range', opt.value);
                        // Auto-suggest pages on selection
                        update('max_search_pages', suggestedPages[opt.value]);
                      }}
                    >
                      <div className="settings-date-radio">
                        <div className="settings-date-dot" />
                      </div>
                      <div>
                        <div className="settings-date-label">{opt.label}</div>
                        <div className="settings-date-hint">{opt.desc}</div>
                      </div>
                      {s.date_range === opt.value && (
                        <span className="settings-active-badge">Active</span>
                      )}
                    </label>
                  ))}
                </div>
              </div>

              {/* Pagination Card */}
              <div className="settings-card">
                <div className="settings-card-header">
                  <div className="settings-card-icon" style={{ background: 'hsl(170,70%,94%)', color: 'hsl(170,60%,35%)' }}>
                    <Sliders size={18} />
                  </div>
                  <div>
                    <div className="settings-card-title">Max Search Pages</div>
                    <div className="settings-card-desc">Maximum pages to paginate per vendor URL (auto-adjusted by date range)</div>
                  </div>
                </div>
                <div className="settings-slider-row">
                  <input
                    type="range"
                    min={1} max={200} step={1}
                    value={s.max_search_pages}
                    onChange={e => update('max_search_pages', Number(e.target.value))}
                    className="settings-slider"
                  />
                  <span className="settings-slider-val">{s.max_search_pages}</span>
                </div>
                <div className="settings-hint-row">
                  <span>Suggested for <strong>{DATE_OPTIONS.find(o => o.value === s.date_range)?.label}</strong>: {suggestedPages[s.date_range]} pages</span>
                  <button
                    className="settings-suggest-btn"
                    onClick={() => update('max_search_pages', suggestedPages[s.date_range])}
                  >
                    <RotateCcw size={12} /> Use suggested
                  </button>
                </div>
              </div>

              {/* Performance Card */}
              <div className="settings-card">
                <div className="settings-card-header">
                  <div className="settings-card-icon" style={{ background: 'hsl(30,90%,94%)', color: 'hsl(30,75%,45%)' }}>
                    <TrendingUp size={18} />
                  </div>
                  <div>
                    <div className="settings-card-title">Performance</div>
                    <div className="settings-card-desc">Thread count and network timeouts</div>
                  </div>
                </div>
                <div className="settings-fields">
                  <div className="settings-field">
                    <label>Max Parallel Workers</label>
                    <div className="settings-number-wrap">
                      <input
                        type="number" min={1} max={10}
                        value={s.max_workers}
                        onChange={e => update('max_workers', Number(e.target.value))}
                        className="settings-number"
                      />
                      <span className="settings-unit">threads</span>
                    </div>
                    <p className="settings-field-hint">Higher = faster but may trigger rate limits. Recommended: 3</p>
                  </div>
                  <div className="settings-field">
                    <label>Request Timeout</label>
                    <div className="settings-number-wrap">
                      <input
                        type="number" min={5} max={120}
                        value={s.request_timeout}
                        onChange={e => update('request_timeout', Number(e.target.value))}
                        className="settings-number"
                      />
                      <span className="settings-unit">seconds</span>
                    </div>
                    <p className="settings-field-hint">Per-request timeout. Default: 30s</p>
                  </div>
                  <div className="settings-field">
                    <label>Scrape Cooldown</label>
                    <div className="settings-number-wrap">
                      <input
                        type="number" min={60} max={3600}
                        value={s.scrape_cooldown}
                        onChange={e => update('scrape_cooldown', Number(e.target.value))}
                        className="settings-number"
                      />
                      <span className="settings-unit">seconds</span>
                    </div>
                    <p className="settings-field-hint">Minimum time between manual triggers. Default: 300s</p>
                  </div>
                </div>
              </div>

              {/* Clear Scraped Data Card */}
              <div className="settings-card" style={{ border: '1px solid #fecaca', background: 'hsl(0,100%,98%)' }}>
                <div className="settings-card-header">
                  <div className="settings-card-icon" style={{ background: 'hsl(0,90%,94%)', color: 'hsl(0,75%,45%)' }}>
                    <Trash2 size={18} />
                  </div>
                  <div>
                    <div className="settings-card-title">Clear Scraped Data</div>
                    <div className="settings-card-desc">Permanently delete job data from selected sheets</div>
                  </div>
                </div>
                <div className="settings-checkbox-group">
                  <label className="settings-checkbox-label">
                    <input
                      type="checkbox"
                      checked={clearSheets.active}
                      onChange={e => setClearSheets(prev => ({ ...prev, active: e.target.checked }))}
                      className="settings-checkbox"
                    />
                    <span className="settings-checkbox-custom" />
                    Active
                  </label>
                  <label className="settings-checkbox-label">
                    <input
                      type="checkbox"
                      checked={clearSheets.inactive}
                      onChange={e => setClearSheets(prev => ({ ...prev, inactive: e.target.checked }))}
                      className="settings-checkbox"
                    />
                    <span className="settings-checkbox-custom" />
                    Inactive
                  </label>
                </div>
                {clearMsg && (
                  <div className={`settings-msg ${clearMsg.type}`} style={{ marginBottom: '12px' }}>{clearMsg.text}</div>
                )}
                <button
                  className="settings-danger-btn"
                  onClick={clearData}
                  disabled={clearingData || (!clearSheets.active && !clearSheets.inactive)}
                >
                  <Trash2 size={14} />
                  {clearingData ? 'Clearing...' : 'Clear Selected'}
                </button>
              </div>
            </>
          )}

          {showClearConfirm && (
            <div className="modal-overlay" onClick={() => setShowClearConfirm(false)}>
              <div className="modal-content" onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                  <Trash2 size={20} />
                  <h3>Confirm Delete</h3>
                </div>
                <p className="modal-body">
                  This will permanently delete all job data from the selected sheet(s). This action cannot be undone.
                </p>
                <div className="modal-actions">
                  <button className="modal-btn-cancel" onClick={() => setShowClearConfirm(false)}>
                    Cancel
                  </button>
                  <button className="modal-btn-confirm" onClick={confirmClearData}>
                    Delete
                  </button>
                </div>
              </div>
            </div>
          )}

          {settingsSubTab === 'scheduler' && (
            <>
              {/* Scheduler Card */}
              <div className="settings-card">
                <div className="settings-card-header">
                  <div className="settings-card-icon" style={{ background: 'hsl(210,95%,92%)', color: 'hsl(210,90%,40%)' }}>
                    <Clock size={18} />
                  </div>
                  <div>
                    <div className="settings-card-title">Daily Scheduler</div>
                    <div className="settings-card-desc">Automatically trigger a full scrape every day</div>
                  </div>
                </div>
                <div className="settings-fields" style={{ marginTop: '16px' }}>
                  <div className="settings-field" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      <label style={{ margin: 0, fontSize: '14px' }}>Enable Scheduler</label>
                      <p style={{ margin: 0, fontSize: '11px', color: '#64748b' }}>Runs once per day at target time</p>
                    </div>
                    <label className="switch">
                      <input 
                        type="checkbox" 
                        checked={s.schedule_enabled}
                        onChange={e => update('schedule_enabled', e.target.checked)}
                      />
                      <span className="slider round"></span>
                    </label>
                  </div>
                  <div className={clsx('settings-field', !s.schedule_enabled && 'disabled-field')}>
                    <label>Run Time (Daily)</label>
                    <div className="settings-input-group">
                       <input 
                         type="time" 
                         className="settings-time-input"
                         value={s.schedule_time}
                         onChange={e => update('schedule_time', e.target.value)}
                         disabled={!s.schedule_enabled}
                       />
                    </div>
                    <span className="settings-field-hint" style={{ marginTop: '8px', display: 'block' }}>Based on server's local time. Currently: {new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="app-container">

      {/* ── Open-tab arrow — shown when sidebar is closed ── */}
      {!sidebarOpen && (
        <button
          className="sidebar-open-tab"
          onClick={() => setSidebarOpen(true)}
          title="Open menu"
        >
          {/* Right-pointing chevron */}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6"/>
          </svg>
        </button>
      )}

      {/* Sidebar */}
      <aside
        className="sidebar"
        style={{ width: sidebarOpen ? '20vw' : 0, minWidth: sidebarOpen ? 180 : 0 }}
      >
        {/* Header: logo + controls */}
        <div className="sidebar-header">
          <div className="logo-icon">
            <Zap size={18} color="#fff" fill="#fff" />
          </div>
          <div className="logo-text">
            <h1>Tabner HR</h1>
            <p>Mission Control</p>
          </div>
          {/* Close button only */}
          <div className="sidebar-controls">
            <button
              className="sidebar-ctrl-btn sidebar-ctrl-close"
              onClick={() => setSidebarOpen(false)}
              title="Close menu"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18"/>
                <line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        <nav className="nav-section">
          <p className="nav-label">Navigation</p>
          <div
            className={clsx('nav-item', activeTab === 'candidate-matching' && 'active')}
            onClick={() => setActiveTab('candidate-matching')}
          >
            <LayoutDashboard size={18} />
            <div className="nav-item-text">
              <h4>Candidate Matching</h4>
              <p>Matches &amp; resumes</p>
            </div>
          </div>
          <div
            className={clsx('nav-item', activeTab === 'job-board' && 'active')}
            onClick={() => setActiveTab('job-board')}
          >
            <Briefcase size={18} />
            <div className="nav-item-text">
              <h4>Job Board</h4>
              <p>Scraped listings</p>
            </div>
          </div>
          <div
            className={clsx('nav-item', activeTab === 'resume-review' && 'active')}
            onClick={() => setActiveTab('resume-review')}
          >
            <FileText size={18} />
            <div className="nav-item-text">
              <h4>Resume Review</h4>
              <p>Formatting queue</p>
            </div>
          </div>
        </nav>

        <div className="sidebar-footer">
          <div className="agent-status">
            <div className="status-indicator">
              <span className="dot"></span>
              {status.status === 'running' ? 'Agents Working...' : 'Agents Active'}
            </div>
            <p className="status-desc">
              {status.status === 'running' ? status.current_task : 'Scraper runs daily at 9:00 AM'}
            </p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button
                className={clsx('scrape-btn', status.status === 'running' && 'running')}
                onClick={triggerScrape}
                disabled={status.status === 'running' || status.status === 'starting'}
                style={{ flex: 1, fontSize: '12px' }}
              >
                {status.status === 'running' ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center' }}>
                    <RefreshCw size={14} className="animate-spin" />
                    <span>{status.progress}%</span>
                  </div>
                ) : 'Trigger Scrape Now'}
              </button>

              {(status.status === 'running' || status.status === 'starting') && (
                <button
                  className="stop-btn"
                  onClick={async () => {
                    try {
                      await axios.post(`${API_BASE_URL}/stop`, {}, { headers: { 'x-api-key': API_KEY } });
                    } catch (e) {
                      console.error('Stop failed', e);
                    }
                  }}
                  title="Stop Scraping"
                  style={{ width: '40px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '14px', color: '#ef4444', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  <Lock size={16} />
                </button>
              )}
            </div>
          </div>
        </div>

        <button
           className={clsx('sidebar-settings-btn', activeTab === 'settings' && 'active')}
           onClick={() => {
             if (activeTab === 'settings') {
               setActiveTab(prevTab);
             } else {
               setPrevTab(activeTab);
               setActiveTab('settings');
               setSettingsSubTab('menu');
             }
           }}
           title="Application Settings"
        >
           <Settings size={14} />
           <span>Settings</span>
        </button>

        {/* End sidebar */}
      </aside>

      {/* Main Content — left margin tracks sidebar width */}
      <main
        className="main-content"
        style={{ marginLeft: sidebarOpen ? '20vw' : 0 }}
      >
        <header className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '28px' }}>
          <div>
            <h2>
              {activeTab === 'candidate-matching' && 'Candidate Matching'}
              {activeTab === 'job-board' && 'Job Board'}
              {activeTab === 'resume-review' && 'Resume Review'}
              {activeTab === 'settings' && 'Settings'}
            </h2>
            <p>
              {activeTab === 'candidate-matching' && 'Review top matches, tailor resumes, and submit candidates to jobs.'}
              {activeTab === 'job-board' && 'Live feed of scraped jobs from Dice vendors.'}
              {activeTab === 'resume-review' && 'Resolve auto-formatting failures and feed missing data to the agent.'}
              {activeTab === 'settings' && 'Configure scraping parameters. Changes apply on the next scheduled or manual run.'}
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {activeTab === 'settings' && (
              <button 
                className="page-close-btn" 
                onClick={() => setActiveTab(prevTab)}
                title="Close settings"
              >
                <MoreHorizontal size={18} />
              </button>
            )}
            
            {/* Total Jobs stat card (Job Board only) */}
            {activeTab === 'job-board' && (
              <div className="jb-stat-card">
                <div className="jb-stat-number">{stats?.total_jobs || jobs.length}</div>
                <div className="jb-stat-label">TOTAL JOBS</div>
              </div>
            )}
          </div>
        </header>

        {activeTab === 'candidate-matching' && renderCandidateMatching()}
        {activeTab === 'job-board'           && renderJobBoard()}
        {activeTab === 'resume-review'       && renderResumeReview()}
        {activeTab === 'settings'            && renderSettings()}
      </main>
    </div>
  );
};

export default App;
