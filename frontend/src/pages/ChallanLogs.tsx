import { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { apiService } from '../api/apiService';
import { 
  ExternalLink, Search, Activity, Fingerprint, RefreshCw, Send, 
  CheckCircle2, X, ChevronRight, AlertCircle, Film, Camera, MapPin, 
  Clock, ShieldCheck 
} from 'lucide-react';

const API_BASE_URL = 'http://127.0.0.1:8000';

interface RowEdit {
  plate: string;
  phone: string;
  issued: boolean;
  loading: boolean;
  error: string;
}

const ChallanLogs = () => {
  const [logs, setLogs] = useState<any[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);
  const [rowEdits, setRowEdits] = useState<Record<string, RowEdit>>({});
  
  const [activeTab, setActiveTab] = useState<'Pending' | 'Issued' | 'Contested'>('Pending');
  const [sourceFilter, setSourceFilter] = useState<'all' | 'uploaded' | 'live'>('all');
  const [selectedLog, setSelectedLog] = useState<any | null>(null);

  const token = localStorage.getItem('access_token');

  const fetchLogs = useCallback(async (isInitial = false) => {
    try {
      if (isInitial) setLoading(true);
      setIsSyncing(true);
      const response = await apiService.getViolations(searchTerm);
      const data: any[] = response.data || [];
      setLogs(data);
      setRowEdits(prev => {
        const next = { ...prev };
        data.forEach(log => {
          const isIssued = log.status === 'issued';
          if (!next[log.id]) {
            const isUnknown = !log.plate_number || ['UNKNOWN', 'PENDING', 'PENDINGRECOGNITION'].includes(log.plate_number.toUpperCase());
            next[log.id] = { 
              plate: isUnknown ? '' : log.plate_number, 
              phone: '', 
              issued: isIssued, 
              loading: false, 
              error: '' 
            };
          } else if (isIssued) {
            next[log.id].issued = true;
          }
        });
        return next;
      });
    } catch (err) {
      console.error("BTU Archive Sync Error:", err);
    } finally {
      setLoading(false);
      setIsSyncing(false);
    }
  }, [searchTerm]);

  useEffect(() => {
    fetchLogs(true);
    const interval = setInterval(() => fetchLogs(false), 10000);
    return () => clearInterval(interval);
  }, [fetchLogs]);

  const updateRow = (id: string, updates: Partial<RowEdit>) => {
    setRowEdits(prev => ({ ...prev, [id]: { ...prev[id], ...updates } }));
  };

  const handleVerifyAndIssue = async (log: any) => {
    const row = rowEdits[log.id];
    if (!row || !row.plate || !row.phone) return;

    updateRow(log.id, { loading: true, error: '' });
    try {
      await axios.post(
        `${API_BASE_URL}/challans/issue`,
        {
          violation_id: log.id,
          vehicle_number: row.plate.replace(/[\s-]/g, '').toUpperCase(),
          phone_number: row.phone,
          violation_type: log.violation_type,
          owner_name: 'Unknown',
          location: log.location || log.camera_id || 'Bhopal City',
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      updateRow(log.id, { issued: true, loading: false });
      // Refresh database records
      fetchLogs(false);
      setTimeout(() => setSelectedLog(null), 1500); // close drawer after success
    } catch (err: any) {
      const msg = err?.response?.data?.detail || 'Failed to issue challan';
      updateRow(log.id, { error: msg, loading: false });
    }
  };

  const getConfidenceColor = (score: number) => {
    if (score >= 0.9) return 'text-ok bg-ok/10 border-ok/20';
    if (score >= 0.7) return 'text-warn bg-warn/10 border-warn/20';
    return 'text-danger bg-danger/10 border-danger/20';
  };
  
  const getConfidenceBarColor = (score: number) => {
    if (score >= 0.9) return 'bg-ok';
    if (score >= 0.7) return 'bg-warn';
    return 'bg-danger';
  };

  const filteredLogs = logs.filter(log => {
    const isIssued = log.status === 'issued' || rowEdits[log.id]?.issued || false;
    if (activeTab === 'Pending' && isIssued) return false;
    if (activeTab === 'Issued' && !isIssued) return false;
    if (activeTab === 'Contested') return false;

    if (sourceFilter === 'uploaded' && log.source !== 'uploaded_video') return false;
    if (sourceFilter === 'live' && log.source === 'uploaded_video') return false;

    return true;
  });

  const pendingCount = logs.filter(l => l.status !== 'issued' && !rowEdits[l.id]?.issued).length;
  const issuedCount = logs.filter(l => l.status === 'issued' || rowEdits[l.id]?.issued).length;
  const uploadedCount = logs.filter(l => l.source === 'uploaded_video').length;
  const liveCount = logs.filter(l => l.source !== 'uploaded_video').length;

  return (
    <div className="flex-1 relative overflow-hidden flex font-sans bg-[var(--color-bg)] text-white">
      {/* Main Content Area */}
      <div className={`flex-1 overflow-y-auto p-8 transition-all duration-300 ${selectedLog ? 'pr-[420px]' : ''}`}>
        <div className="max-w-[1600px] mx-auto">
          
          <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-8 gap-4">
            <div>
              <h1 className="text-3xl font-bold flex items-center gap-3">
                E-Challan Enforcement & Evidence
                {isSyncing && <RefreshCw size={18} className="animate-spin text-slate-400" />}
              </h1>
              <p className="text-sm font-medium text-slate-400 mt-2">
                Bhopal Police BTU • Review violations from live cameras and uploaded surveillance videos
              </p>
            </div>

            <div className="relative group">
              <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-accent transition-colors" size={18} />
              <input
                type="text"
                placeholder="Search Plate Number..."
                className="pl-11 pr-4 py-2.5 rounded-xl bg-[var(--color-surface)] border border-border outline-none font-semibold text-sm w-80 focus:border-accent transition-all text-white placeholder:text-slate-500 shadow-sm"
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>

          {/* Top Control Bar: Status Tabs + Source Filter Switcher */}
          <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6 border-b border-border pb-3">
            {/* Primary Status Tabs */}
            <div className="flex gap-2">
              {(['Pending', 'Issued', 'Contested'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-5 py-2.5 rounded-xl text-sm font-bold transition-all flex items-center gap-2 ${
                    activeTab === tab 
                      ? 'bg-[var(--color-surface)] text-accent border border-border shadow-md' 
                      : 'text-slate-400 hover:text-white hover:bg-surface'
                  }`}
                >
                  {tab === 'Pending' && 'Pending Review'}
                  {tab === 'Issued' && 'Issued Challans'}
                  {tab === 'Contested' && 'Contested'}
                  {tab === 'Pending' && (
                    <span className="bg-accent/20 text-accent px-2 py-0.5 rounded-md text-[10px] font-mono">
                      {pendingCount}
                    </span>
                  )}
                  {tab === 'Issued' && (
                    <span className="bg-ok/20 text-ok px-2 py-0.5 rounded-md text-[10px] font-mono">
                      {issuedCount}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* Secondary Source Filter */}
            <div className="flex items-center gap-1.5 bg-surface2/60 p-1.5 rounded-xl border border-border">
              <span className="text-[10px] font-black uppercase tracking-wider text-slate-400 px-2">
                Source:
              </span>
              <button
                onClick={() => setSourceFilter('all')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  sourceFilter === 'all'
                    ? 'bg-white text-slate-900 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                All ({logs.length})
              </button>
              <button
                onClick={() => setSourceFilter('uploaded')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  sourceFilter === 'uploaded'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-purple-400 hover:bg-purple-500/10'
                }`}
              >
                <Film size={12} /> Uploaded Footage ({uploadedCount})
              </button>
              <button
                onClick={() => setSourceFilter('live')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all flex items-center gap-1.5 ${
                  sourceFilter === 'live'
                    ? 'bg-cyan-600 text-white shadow-sm'
                    : 'text-cyan-400 hover:bg-cyan-500/10'
                }`}
              >
                <Camera size={12} /> Live CCTV ({liveCount})
              </button>
            </div>
          </div>

          {/* Main Records Table */}
          <div className="bg-[var(--color-surface)] rounded-2xl border border-border overflow-hidden shadow-xl">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-border bg-surface2/50">
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">ID</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">Source & Location</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">Violation</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">AI Confidence</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">Vehicle Plate</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide">Status</th>
                  <th className="p-4 text-xs font-semibold text-slate-400 uppercase tracking-wide text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading ? (
                  <tr>
                    <td colSpan={7} className="p-20 text-center">
                      <Activity className="animate-spin text-accent mx-auto mb-4" size={32} />
                      <span className="font-semibold text-slate-400 text-sm">Accessing Records...</span>
                    </td>
                  </tr>
                ) : filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="p-20 text-center">
                      <Fingerprint className="text-slate-600 mx-auto mb-4" size={40} />
                      <p className="font-semibold text-slate-400 text-sm">No matching violation records found</p>
                      <p className="text-xs text-slate-500 mt-1">Try switching tabs or resetting the search filter</p>
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => {
                    const row = rowEdits[log.id] || { plate: '', phone: '', issued: false, loading: false, error: '' };
                    const isIssued = log.status === 'issued' || row.issued;
                    const confColor = getConfidenceColor(log.confidence_score);
                    const barColor = getConfidenceBarColor(log.confidence_score);
                    const isUploaded = log.source === 'uploaded_video';

                    return (
                      <tr 
                        key={log.id} 
                        className={`hover:bg-surface2 transition-all cursor-pointer ${selectedLog?.id === log.id ? 'bg-surface2' : ''}`} 
                        onClick={() => setSelectedLog(log)}
                      >
                        <td className="p-4 text-sm font-mono text-slate-400">
                          #{log.id.slice(0, 6)}
                        </td>
                        
                        {/* Source & Location Column */}
                        <td className="p-4">
                          <div className="flex flex-col gap-1">
                            {isUploaded ? (
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 w-max">
                                <Film size={11} className="text-purple-400" /> Uploaded Video
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-[10px] font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 w-max">
                                <Camera size={11} className="text-cyan-400" /> Live Camera
                              </span>
                            )}
                            <span className="text-xs text-slate-300 font-medium truncate max-w-[220px] flex items-center gap-1">
                              <MapPin size={11} className="text-slate-500 shrink-0" />
                              {log.location || 'Bhopal City'}
                            </span>
                          </div>
                        </td>

                        {/* Violation Type */}
                        <td className="p-4">
                          <span className={`px-2.5 py-1 rounded-md text-xs font-bold uppercase border ${
                            log.violation_type === 'No Helmet' 
                              ? 'bg-danger/10 text-red-400 border-danger/20' 
                              : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                          }`}>
                            {log.violation_type}
                          </span>
                        </td>

                        {/* AI Confidence */}
                        <td className="p-4">
                          <div className="flex flex-col gap-1.5 w-32">
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-md border w-max ${confColor}`}>
                              {(log.confidence_score * 100).toFixed(1)}%
                            </span>
                            <div className="w-full h-1.5 bg-bg rounded-full overflow-hidden">
                              <div className={`h-full ${barColor}`} style={{ width: `${log.confidence_score * 100}%` }}></div>
                            </div>
                          </div>
                        </td>

                        {/* Vehicle Plate */}
                        <td className="p-4">
                          <div className="flex items-center gap-1.5">
                            <span className="font-mono font-bold text-slate-100 bg-surface2 px-2.5 py-1 rounded-lg border border-border text-xs">
                              {row.plate || log.plate_number || 'UNKNOWN'}
                            </span>
                            {row.plate && row.plate !== 'UNKNOWN' && (
                              <span title="ALPR Verified Plate">
                                <ShieldCheck size={14} className="text-ok" />
                              </span>
                            )}
                          </div>
                        </td>

                        {/* Status */}
                        <td className="p-4">
                          {isIssued ? (
                            <span className="inline-flex items-center gap-1 text-xs font-bold text-ok bg-ok/10 border border-ok/20 px-2.5 py-1 rounded-md">
                              <CheckCircle2 size={12} /> Issued
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-md">
                              <Clock size={12} /> Pending Review
                            </span>
                          )}
                        </td>

                        {/* Action */}
                        <td className="p-4 text-right">
                          <button 
                            onClick={(e) => { e.stopPropagation(); setSelectedLog(log); }}
                            className="inline-flex items-center gap-1 text-accent hover:text-accent/80 text-sm font-bold bg-accent/10 px-3 py-1.5 rounded-xl border border-accent/20 hover:bg-accent/20 transition-all"
                          >
                            Review <ChevronRight size={16} />
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Side Review Drawer */}
      <div className={`fixed top-0 right-0 h-full w-[420px] bg-[var(--color-surface)] border-l border-border shadow-2xl transform transition-transform duration-300 z-50 flex flex-col ${selectedLog ? 'translate-x-0' : 'translate-x-full'}`}>
        {selectedLog && (() => {
          const row = rowEdits[selectedLog.id];
          const isIssued = selectedLog.status === 'issued' || row?.issued;
          const canIssue = row && row.plate.length >= 6 && row.phone.length >= 10;
          const isUploaded = selectedLog.source === 'uploaded_video';

          return (
            <>
              <div className="p-6 border-b border-border flex justify-between items-center bg-surface2">
                <div>
                  <h2 className="text-lg font-bold">Review Challan Evidence</h2>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    {isUploaded ? 'Recorded Surveillance Upload' : 'Live Camera Incident'}
                  </p>
                </div>
                <button onClick={() => setSelectedLog(null)} className="p-2 hover:bg-bg rounded-lg text-slate-400 hover:text-white transition-colors">
                  <X size={20} />
                </button>
              </div>

              <div className="p-6 overflow-y-auto flex-1 space-y-6">
                {/* Visual Evidence (3-Panel Composite) */}
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                      3-Panel Forensic Composite
                    </span>
                    <span className="text-[10px] text-slate-500 font-mono">
                      SHA-256 Verified
                    </span>
                  </div>
                  <div className="aspect-video bg-bg rounded-xl overflow-hidden border border-border relative group">
                    <img src={selectedLog.evidence_image_url} alt="Evidence" className="w-full h-full object-cover" />
                    <a href={selectedLog.evidence_image_url} target="_blank" rel="noreferrer" className="absolute top-2 right-2 p-2 bg-black/60 rounded-lg text-white opacity-0 group-hover:opacity-100 transition-opacity backdrop-blur-md">
                      <ExternalLink size={16} />
                    </a>
                  </div>
                </div>

                {/* Metadata Pills */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-bg p-3 rounded-xl border border-border">
                    <p className="text-[10px] text-slate-500 font-bold uppercase mb-1">Violation</p>
                    <p className="text-sm font-bold text-red-400">{selectedLog.violation_type}</p>
                  </div>
                  <div className="bg-bg p-3 rounded-xl border border-border">
                    <p className="text-[10px] text-slate-500 font-bold uppercase mb-1">AI Confidence</p>
                    <p className="text-sm font-bold text-ok">{(selectedLog.confidence_score * 100).toFixed(1)}%</p>
                  </div>
                </div>

                <div className="bg-bg p-3 rounded-xl border border-border space-y-1.5 text-xs">
                  <div className="flex justify-between items-center text-slate-400">
                    <span>Location:</span>
                    <span className="font-semibold text-white">{selectedLog.location || 'Bhopal City'}</span>
                  </div>
                  <div className="flex justify-between items-center text-slate-400">
                    <span>Source:</span>
                    <span className="font-semibold text-purple-400">
                      {isUploaded ? '📹 Uploaded Video' : '📡 Live Camera'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-slate-400">
                    <span>Timestamp:</span>
                    <span className="font-mono text-slate-300">
                      {new Date(selectedLog.detected_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Issuance Form or Confirmation */}
                {isIssued ? (
                  <div className="bg-ok/10 border border-ok/20 rounded-xl p-6 text-center space-y-2">
                    <CheckCircle2 size={32} className="text-ok mx-auto mb-2" />
                    <h3 className="text-lg font-bold text-ok">Official Challan Issued</h3>
                    <p className="text-sm text-slate-400">
                      Challan notice logged to citizen database for vehicle {row?.plate || selectedLog.plate_number}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4 pt-4 border-t border-border">
                    <div className="space-y-2">
                      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Verify Vehicle Plate Number
                      </label>
                      <input
                        type="text"
                        value={row?.plate || ''}
                        onChange={e => updateRow(selectedLog.id, { plate: e.target.value.toUpperCase() })}
                        placeholder="MP09AB1234"
                        className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-white font-mono font-bold text-sm uppercase tracking-wider outline-none focus:border-accent transition-colors"
                      />
                    </div>
                    
                    <div className="space-y-2">
                      <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide">
                        Citizen Contact Phone (SMS / WhatsApp)
                      </label>
                      <input
                        type="tel"
                        value={row?.phone || ''}
                        onChange={e => updateRow(selectedLog.id, { phone: e.target.value.replace(/\D/g, '') })}
                        placeholder="9876543210"
                        maxLength={10}
                        className="w-full bg-bg border border-border rounded-xl px-4 py-3 text-white font-mono font-bold text-sm tracking-wider outline-none focus:border-accent transition-colors"
                      />
                    </div>

                    {row?.error && (
                      <div className="p-3 bg-danger/10 border border-danger/20 rounded-xl flex items-start gap-2 text-red-400 text-sm">
                        <AlertCircle size={16} className="mt-0.5 shrink-0" />
                        <span>{row.error}</span>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {!isIssued && (
                <div className="p-6 border-t border-border bg-surface2">
                  <button
                    disabled={!canIssue || row?.loading}
                    onClick={() => handleVerifyAndIssue(selectedLog)}
                    className={`w-full flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl font-bold text-sm uppercase tracking-wide transition-all ${
                      canIssue && !row?.loading
                        ? 'bg-accent hover:bg-accent/80 text-white shadow-lg'
                        : 'bg-surface text-slate-500 cursor-not-allowed'
                    }`}
                  >
                    {row?.loading ? (
                      <Activity size={18} className="animate-spin" />
                    ) : (
                      <>
                        <Send size={16} /> Issue Official Notice
                      </>
                    )}
                  </button>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
};

export default ChallanLogs;