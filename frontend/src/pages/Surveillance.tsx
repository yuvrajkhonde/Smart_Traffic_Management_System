import { useEffect, useState, useRef } from 'react';
import axios from 'axios';
import { apiService } from '../api/apiService';
import { 
  Camera, Plus, X, Globe, Cpu, RefreshCw, 
  Trash2, Tag, ShieldCheck, ShieldAlert, Volume2, MapPin,
  UploadCloud, Film, CheckCircle2, AlertCircle
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

// Fix leaflet icon issue
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const LocationPicker = ({ position, setPosition }: { position: [number, number], setPosition: (pos: [number, number]) => void }) => {
  useMapEvents({
    click(e) {
      setPosition([e.latlng.lat, e.latlng.lng]);
    },
  });
  return position ? <Marker position={position} /> : null;
};

const Surveillance = () => {
  const [cameras, setCameras] = useState<any[]>([]);
  
  const [signalStates, setSignalStates] = useState<any>(() => {
    const saved = localStorage.getItem('btu_live_signals');
    return saved ? JSON.parse(saved) : {};
  }); 

  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [activeNode, setActiveNode] = useState<string | null>(null); 
  const [liveFines, setLiveFines] = useState<any>({});
  
  const [voiceMode, setVoiceMode] = useState<'en' | 'hi' | 'both' | 'muted'>(() => {
    const saved = localStorage.getItem('btu_voice_mode');
    return (saved as any) || 'both';
  });

  const [spokenIds] = useState(() => new Set<string>());
  const isFirstLoad = useRef(true);

  const handleVoiceModeChange = (mode: 'en' | 'hi' | 'both' | 'muted') => {
    setVoiceMode(mode);
    localStorage.setItem('btu_voice_mode', mode);
  };

  const speakAnnouncement = (ann: any) => {
    if (voiceMode === 'muted') return;
    const synth = window.speechSynthesis;
    if (!synth) return;

    const speakEn = () => {
      const utterEn = new SpeechSynthesisUtterance(ann.text_en);
      utterEn.lang = 'en-US';
      const voices = synth.getVoices();
      const enVoice = voices.find(v => v.lang.startsWith('en'));
      if (enVoice) utterEn.voice = enVoice;
      
      utterEn.onend = () => {
        if (voiceMode === 'both') speakHi();
      };
      synth.speak(utterEn);
    };

    const speakHi = () => {
      const utterHi = new SpeechSynthesisUtterance(ann.text_hi);
      utterHi.lang = 'hi-IN';
      const voices = synth.getVoices();
      const hiVoice = voices.find(v => v.lang.startsWith('hi'));
      if (hiVoice) utterHi.voice = hiVoice;
      synth.speak(utterHi);
    };

    if (voiceMode === 'en' || voiceMode === 'both') {
      speakEn();
    } else if (voiceMode === 'hi') {
      speakHi();
    }
  };
  
  const [formData, setFormData] = useState({ 
    location_name: '', 
    cameras: [''], 
    latitude: 23.2599, 
    longitude: 77.4126 
  });

  // 📹 Video Upload & GPS Geotagging State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadData, setUploadData] = useState({ 
    location_name: '', 
    latitude: 23.2599, 
    longitude: 77.4126 
  });
  const [uploading, setUploading] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<any | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleVideoUploadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadFile) {
      setUploadError("Please select a video file (.mp4, .avi, .mov).");
      return;
    }
    if (!uploadData.location_name.trim()) {
      setUploadError("Please enter the junction/location name where this footage was recorded.");
      return;
    }

    setUploading(true);
    setUploadError(null);
    setJobStatus({ status: 'uploading', progress: 5, violations_found: 0 });

    try {
      const data = new FormData();
      data.append('file', uploadFile);
      data.append('location_name', uploadData.location_name);
      data.append('latitude', String(uploadData.latitude));
      data.append('longitude', String(uploadData.longitude));

      const res = await apiService.uploadSurveillanceVideo(data);
      const newJobId = res.data?.job_id;
      setJobId(newJobId);
      setJobStatus({ status: 'processing', progress: 15, violations_found: 0 });

      // Poll status until done
      const pollTimer = setInterval(async () => {
        try {
          const stRes = await apiService.getVideoJobStatus(newJobId);
          const st = stRes.data;
          setJobStatus(st);
          if (st.status === 'completed' || st.status === 'failed') {
            clearInterval(pollTimer);
            setUploading(false);
            fetchCameras(); // Refresh grid with newly added camera node
          }
        } catch {
          clearInterval(pollTimer);
          setUploading(false);
        }
      }, 2000);
    } catch (err: any) {
      setUploading(false);
      setUploadError(err?.response?.data?.detail || "Video upload failed. Check backend connection.");
    }
  };

  const resetUploadModal = () => {
    setShowUploadModal(false);
    setUploadFile(null);
    setUploadData({ location_name: '', latitude: 23.2599, longitude: 77.4126 });
    setUploading(false);
    setJobId(null);
    setJobStatus(null);
    setUploadError(null);
  };

  const token = localStorage.getItem('access_token');
  const API_BASE_URL = 'http://127.0.0.1:8000';

  const fetchCameras = async () => {
    try {
      const response = await apiService.getCameras();
      setCameras(response.data);
      setLoading(false);
    } catch (err) {
      setLoading(false);
    }
  };

  const fetchLiveRates = async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/admin/module/settings/config`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.data && res.data.fine_multipliers) {
        setLiveFines(res.data.fine_multipliers);
      }
    } catch (err) {
      console.error("Policy sync failed");
    }
  };

  useEffect(() => { 
    fetchCameras(); 
    fetchLiveRates();

    const savedCam = localStorage.getItem('selected_camera');
    if (savedCam) {
      const parsed = JSON.parse(savedCam);
      setActiveNode(parsed.id);
    }

    const dataInterval = setInterval(async () => {
      try {
        const [res, annRes] = await Promise.all([
          axios.get(`${API_BASE_URL}/traffic/congestion`, {
            headers: { Authorization: `Bearer ${token}` }
          }),
          axios.get(`${API_BASE_URL}/traffic/announcements`, {
            headers: { Authorization: `Bearer ${token}` }
          })
        ]);
        
        const roads = res.data || [];
        const announcements = annRes.data || [];

        if (isFirstLoad.current) {
          if (announcements.length > 0) {
            const mostRecent = announcements[announcements.length - 1];
            speakAnnouncement(mostRecent);
          }
          announcements.forEach((ann: any) => {
            spokenIds.add(ann.id);
          });
          isFirstLoad.current = false;
        } else {
          announcements.forEach((ann: any) => {
            if (!spokenIds.has(ann.id)) {
              spokenIds.add(ann.id);
              speakAnnouncement(ann);
            }
          });
        }

        setSignalStates((prev: any) => {
          const newState = { ...prev }; 
          roads.forEach((sig: any) => {
            const camId = sig.camera_id;
            if (!camId) return;

            const densityPct = sig.congestion_level || 0;

            newState[camId] = {
              phase: sig.current_state || 'red',
              timer: sig.recommended_time || 0,
              vehicle_count: sig.vehicle_count || 0,
              density_pct: densityPct,
              is_emergency: sig.is_emergency || false
            };
          });
          
          localStorage.setItem('btu_live_signals', JSON.stringify(newState));
          return newState;
        });
      } catch (err) {
        console.error("Telemetry sync failed");
      }
    }, 1000); // Polling every 1s matches RL prediction tick!

    return () => {
      clearInterval(dataInterval);
    };
  }, [token]);

  const handleToggleNode = (cam: any) => {
    if (activeNode === cam.id) {
      setActiveNode(null);
      localStorage.removeItem('selected_camera');
    } else {
      setActiveNode(cam.id);
      localStorage.setItem('selected_camera', JSON.stringify(cam));
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const validCams = formData.cameras.filter(ip => ip.trim() !== '');
      if (validCams.length === 0) return alert('Add at least one stream source');

      await Promise.all(
        validCams.map(ip => 
          apiService.registerCamera({
            location_name: formData.location_name,
            ip_address: ip,
            latitude: formData.latitude,
            longitude: formData.longitude
          })
        )
      );
      setShowAddModal(false);
      setFormData({ location_name: '', cameras: [''], latitude: 23.2599, longitude: 77.4126 });
      fetchCameras();
    } catch (err) {
      alert("Deployment Failed. Check stream source.");
    }
  };

  const handleReconnect = (id: string) => {
    setSyncing(id);
    setTimeout(() => { fetchCameras(); setSyncing(null); }, 1500);
  };

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(`⚠️ DECOMMISSION NODE [${name}]?`)) {
      try {
        await apiService.deleteCamera(id);
        fetchCameras();
      } catch (err) {
        alert("Purge Failed.");
      }
    }
  };

  return (
    <div className="flex-1 relative h-screen overflow-y-auto p-12 transition-all duration-700 admin-scrollbar bg-[var(--color-bg)] text-white">

      <div className="relative z-10 max-w-[1600px] mx-auto">
        <div className="flex flex-col xl:flex-row justify-between items-start xl:items-center gap-8 mb-12">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <div className="p-2 bg-accent/20 rounded-xl">
                <Camera size={24} className="text-accent" />
              </div>
              Live AI Streams
            </h1>
            <p className="text-sm font-medium text-slate-400 mt-2">
              BTU Central Command — Bhopal Metropolitan Hub
            </p>
          </div>

          <div className="flex flex-wrap gap-4">
            {Object.entries(liveFines).map(([key, val]: any) => (
              <div key={key} className="bg-white/5 border border-white/5 px-6 py-4 rounded-3xl flex items-center gap-4 backdrop-blur-xl">
                <div className="p-2 bg-purple-500/20 rounded-xl text-purple-400"><Tag size={14} /></div>
                <div>
                  <p className="text-[8px] font-black text-white/20 uppercase tracking-widest">{key}</p>
                  <p className="text-sm font-black text-white italic tracking-tighter">₹{val}</p>
                </div>
              </div>
            ))}
            
            <div className="flex bg-white/5 border border-white/10 p-1 rounded-3xl items-center gap-1 backdrop-blur-xl">
              <div className="px-3 text-white/40 flex items-center gap-1.5">
                <Volume2 size={14} className={voiceMode === 'muted' ? 'text-red-500 animate-pulse' : 'text-purple-400'} />
                <span className="text-[8px] font-black uppercase tracking-widest hidden sm:inline">Voice</span>
              </div>
              <button 
                onClick={() => handleVoiceModeChange('en')}
                className={`px-4 py-2.5 rounded-2xl text-[8px] font-black uppercase tracking-widest transition-all ${voiceMode === 'en' ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/20' : 'text-white/40 hover:text-white hover:bg-white/5'}`}
              >
                EN
              </button>
              <button 
                onClick={() => handleVoiceModeChange('hi')}
                className={`px-4 py-2.5 rounded-2xl text-[8px] font-black uppercase tracking-widest transition-all ${voiceMode === 'hi' ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/20' : 'text-white/40 hover:text-white hover:bg-white/5'}`}
              >
                HI
              </button>
              <button 
                onClick={() => handleVoiceModeChange('both')}
                className={`px-4 py-2.5 rounded-2xl text-[8px] font-black uppercase tracking-widest transition-all ${voiceMode === 'both' ? 'bg-purple-600 text-white shadow-lg shadow-purple-900/20' : 'text-white/40 hover:text-white hover:bg-white/5'}`}
              >
                BOTH
              </button>
              <button 
                onClick={() => handleVoiceModeChange('muted')}
                className={`px-4 py-2.5 rounded-2xl text-[8px] font-black uppercase tracking-widest transition-all ${voiceMode === 'muted' ? 'bg-red-600 text-white shadow-lg shadow-red-950/20' : 'text-white/40 hover:text-white hover:bg-white/5'}`}
              >
                MUTED
              </button>
            </div>

            <button 
              onClick={() => {
                setShowUploadModal(true);
                setUploadError(null);
                setJobStatus(null);
              }} 
              className="bg-purple-600 text-white hover:bg-white hover:text-black px-7 py-4 rounded-3xl font-black text-[10px] uppercase tracking-widest flex items-center gap-2.5 transition-all shadow-xl shadow-purple-900/30 ml-4"
            >
              <UploadCloud size={16} /> Upload Video
            </button>

            <button onClick={() => setShowAddModal(true)} className="bg-white text-black hover:bg-purple-600 hover:text-white px-8 py-4 rounded-3xl font-black text-[10px] uppercase tracking-widest flex items-center gap-3 transition-all">
              <Plus size={16} /> Deploy Node
            </button>
          </div>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center h-[50vh]">
            <Cpu className="text-purple-500 animate-pulse mb-6" size={56} />
            <span className="font-black text-white/20 uppercase tracking-[0.5em] italic">Initializing Grid...</span>
          </div>
        ) : (() => {
          const groupedCameras = cameras.reduce((groups, cam) => {
            const loc = cam.location_name || 'Unknown Location';
            if (!groups[loc]) groups[loc] = [];
            groups[loc].push(cam);
            return groups;
          }, {} as Record<string, any[]>);

          return (
            <div className="flex flex-col gap-16">
              {Object.entries(groupedCameras).map(([location, cams]: any) => (
                <div key={location} className="space-y-6">
                  <div className="flex items-center gap-4">
                    <h2 className="text-xl font-bold uppercase tracking-widest text-slate-200">{location} Junction</h2>
                    <div className="h-px bg-border flex-1"></div>
                    <span className="text-[10px] font-bold text-accent bg-accent/10 px-3 py-1 rounded-full">{cams.length} Nodes</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {cams.map((cam: any) => {
              const signal = signalStates[cam.id] || { phase: 'red', timer: 15, vehicle_count: 0, density_pct: 0, is_emergency: false };
              const activeColor = signal.phase;

              let ringColor = 'border-border';
              let textTheme = 'text-white';
              let loadBarColor = signal.density_pct >= 85 ? 'bg-danger' : signal.density_pct >= 60 ? 'bg-warn' : 'bg-ok';

              if (activeColor === 'green') {
                ringColor = 'border-green-500/50 ring-2 ring-green-500/20';
                textTheme = 'text-green-400';
              } else if (activeColor === 'yellow') {
                ringColor = 'border-amber-500/50 ring-2 ring-amber-500/20';
                textTheme = 'text-amber-400';
              } else if (activeColor === 'red') {
                ringColor = 'border-red-500/50 ring-2 ring-red-500/20';
                textTheme = 'text-red-400';
              }

              return (
                <div key={cam.id} className={`bg-[var(--color-surface)] p-5 rounded-2xl border transition-all duration-300 relative flex flex-col ${activeNode === cam.id ? 'border-accent ring-2 ring-accent/30' : ringColor}`}>
                  
                  <div className="absolute top-8 left-8 z-20 flex items-center gap-3 p-3 rounded-xl border border-border bg-surface2/90 backdrop-blur-md shadow-lg">
                    <div className="flex flex-col gap-1.5">
                        <div className={`h-2 w-2 rounded-full transition-all duration-300 ${activeColor === 'red' ? 'bg-red-500 scale-110' : 'bg-red-950'}`}></div>
                        <div className={`h-2 w-2 rounded-full transition-all duration-300 ${activeColor === 'yellow' ? 'bg-amber-500 scale-110' : 'bg-amber-950'}`}></div>
                        <div className={`h-2 w-2 rounded-full transition-all duration-300 ${activeColor === 'green' ? 'bg-green-500 scale-110' : 'bg-green-950'}`}></div>
                    </div>
                    <div className="pr-1 border-l border-border pl-3">
                        <p className="text-[10px] font-semibold uppercase text-slate-400 tracking-wide mb-0.5">AI Phase</p>
                        <p className={`text-lg font-bold ${signal.is_emergency ? 'animate-pulse' : ''} ${textTheme}`}>
                            {activeColor === 'yellow' ? 'AMBER' : activeColor.toUpperCase()} {signal.timer}s
                        </p>
                    </div>
                  </div>

                  <div className="aspect-video bg-[var(--color-bg)] rounded-xl overflow-hidden border border-border relative group mb-4">
                    <img 
                      src={`${API_BASE_URL}/cameras/live/${cam.id}?token=${token}&sync=${syncing === cam.id ? Date.now() : ''}`}
                      alt={cam.location_name}
                      className={`w-full h-full object-cover transition-all duration-300 ${syncing === cam.id ? 'opacity-20' : 'opacity-100'}`}
                      onError={(e) => { 
                        e.currentTarget.style.display = 'none'; 
                        e.currentTarget.parentElement!.querySelector('.offline-overlay')?.classList.remove('hidden');
                      }}
                    />
                    
                    {/* Offline Overlay */}
                    <div className="offline-overlay hidden absolute inset-0 flex flex-col items-center justify-center bg-[var(--color-bg)]">
                        <Camera className="text-slate-600 mb-2" size={32} />
                        <span className="text-sm font-medium text-slate-400 mb-4">Camera Offline</span>
                        <button onClick={() => handleReconnect(cam.id)} className="px-4 py-1.5 bg-surface2 border border-border rounded-lg text-xs hover:bg-surface transition-colors flex items-center gap-2">
                            <RefreshCw size={14} className={syncing === cam.id ? 'animate-spin' : ''} /> Retry
                        </button>
                    </div>
                    
                    <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-black/80 via-black/40 to-transparent p-4 flex justify-between items-end">
                      <div className="flex items-center gap-2 max-w-[50%]">
                        <Camera size={18} className="text-white/60 shrink-0" />
                        <h3 className="text-lg font-bold text-white truncate drop-shadow-md" title={cam.location_name}>{cam.location_name}</h3>
                      </div>
                      
                      <div className="flex items-center gap-4 text-right">
                        <div className="flex flex-col items-end">
                            <p className="text-[10px] font-semibold uppercase text-slate-300 tracking-wide mb-1">Load Density</p>
                            <div className="flex items-center gap-2 mb-1">
                                <span className="text-sm font-bold">{signal.vehicle_count || 0} / 60 veh</span>
                            </div>
                            <div className="w-24 bg-white/20 h-1.5 rounded-full overflow-hidden">
                                <div className={`h-full transition-all duration-1000 ${loadBarColor}`} style={{ width: `${signal.density_pct}%` }}></div>
                            </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mt-auto flex justify-between items-center bg-surface2 p-3 rounded-xl border border-border">
                    <div className="flex flex-col">
                      <span className="text-xs font-medium text-slate-400 flex items-center gap-1.5">
                        <Globe size={14} /> {cam.latitude}°N / {cam.longitude}°E
                      </span>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <button onClick={() => handleToggleNode(cam)} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg transition-all font-medium text-xs ${activeNode === cam.id ? 'bg-accent text-white' : 'bg-surface border border-border text-slate-300 hover:text-white'}`}>
                        {activeNode === cam.id ? <><ShieldCheck size={14} /> Locked</> : <><ShieldAlert size={14} /> Lock</>}
                      </button>
                      <button onClick={() => handleReconnect(cam.id)} className="p-1.5 bg-surface hover:bg-surface2 text-slate-400 hover:text-white rounded-lg transition-all border border-border" title="Refresh Feed">
                        <RefreshCw size={16} className={syncing === cam.id ? 'animate-spin' : ''} />
                      </button>
                      <div className="w-px h-6 bg-border mx-1"></div>
                      <button onClick={() => handleDelete(cam.id, cam.location_name)} className="p-1.5 bg-surface hover:bg-red-500/20 text-slate-400 hover:text-red-400 rounded-lg transition-all border border-border" title="Decommission Node">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
            </div>
          ))}
        </div>
      );
    })()}
      </div>

      {/* 🛡️ DEPLOY NODE MODAL: Universal source support */}
      {showAddModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-md p-6">
          <div className="bg-slate-900 border border-purple-500/30 p-10 rounded-[3rem] w-full max-w-lg relative">
            <button onClick={() => setShowAddModal(false)} className="absolute top-8 right-8 text-white/40 hover:text-white transition-colors hover:text-white">
              <X />
            </button>
            
            <h2 className="text-3xl font-black italic uppercase tracking-tighter text-white mb-2">
              Deploy <span className="text-purple-500">New Node</span>
            </h2>
            <p className="text-[9px] font-black text-white/20 uppercase tracking-widest mb-8 italic">
              Hardware Registry — Central Command
            </p>

            <form onSubmit={handleRegister} className="flex flex-col gap-6">
              <div className="h-[200px] w-full rounded-2xl overflow-hidden border border-white/10 relative z-0">
                <MapContainer center={[formData.latitude, formData.longitude]} zoom={13} style={{ height: '100%', width: '100%' }} zoomControl={false}>
                  <TileLayer key="osm-dark-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-map-tiles" />
                  <LocationPicker 
                    position={[formData.latitude, formData.longitude]} 
                    setPosition={(pos) => setFormData({...formData, latitude: pos[0], longitude: pos[1]})} 
                  />
                </MapContainer>
                <div className="absolute bottom-2 left-2 z-[1000] bg-black/80 px-3 py-1 rounded-lg border border-white/10 backdrop-blur text-[8px] font-black uppercase tracking-widest text-white/50 flex items-center gap-2">
                  <MapPin size={12} className="text-purple-400" /> Click map to set PIN
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <p className="text-[7px] font-black text-purple-400 uppercase ml-2 tracking-widest">Lat</p>
                  <input required placeholder="23.2599" type="number" step="any" className="bg-white/5 border border-white/10 p-4 rounded-2xl text-white font-bold placeholder:text-white/10 outline-none focus:border-purple-500/50 transition-all text-sm" value={formData.latitude} onChange={e => setFormData({...formData, latitude: parseFloat(e.target.value) || 0})} />
                </div>
                <div className="flex flex-col gap-2">
                  <p className="text-[7px] font-black text-purple-400 uppercase ml-2 tracking-widest">Long</p>
                  <input required placeholder="77.4126" type="number" step="any" className="bg-white/5 border border-white/10 p-4 rounded-2xl text-white font-bold placeholder:text-white/10 outline-none focus:border-purple-500/50 transition-all text-sm" value={formData.longitude} onChange={e => setFormData({...formData, longitude: parseFloat(e.target.value) || 0})} />
                </div>
              </div>

              <div className="flex flex-col gap-2 mt-2">
                <p className="text-[7px] font-black text-purple-400 uppercase ml-2 tracking-widest">Junction Name</p>
                <input required placeholder="E.G., MP NAGAR ZONE-1" className="bg-white/5 border border-white/10 p-5 rounded-2xl text-white font-bold placeholder:text-white/10 outline-none focus:border-purple-500/50 transition-all" value={formData.location_name} onChange={e => setFormData({...formData, location_name: e.target.value})} />
              </div>

              <div className="flex flex-col gap-3">
                <div className="flex justify-between items-center px-2">
                  <p className="text-[7px] font-black text-purple-400 uppercase tracking-widest">Camera Sources</p>
                  <button type="button" onClick={() => setFormData({ ...formData, cameras: [...formData.cameras, ''] })} className="text-[9px] font-black text-white hover:text-purple-400 uppercase tracking-widest flex items-center gap-1 transition-colors">
                    <Plus size={12} /> Add Camera
                  </button>
                </div>
                
                <div className="flex flex-col gap-2 max-h-[150px] overflow-y-auto admin-scrollbar pr-2">
                  {formData.cameras.map((cam, idx) => (
                    <div key={idx} className="flex gap-2">
                      <input 
                        required 
                        placeholder="0, RTSP URL, OR test_videos/north_lane.mp4" 
                        className="flex-1 bg-white/5 border border-white/10 p-4 rounded-xl text-white font-bold placeholder:text-white/40 outline-none focus:border-purple-500/50 transition-all text-sm" 
                        value={cam} 
                        onChange={e => {
                          const newCams = [...formData.cameras];
                          newCams[idx] = e.target.value;
                          setFormData({ ...formData, cameras: newCams });
                        }} 
                      />
                      {formData.cameras.length > 1 && (
                        <button type="button" onClick={() => {
                          const newCams = formData.cameras.filter((_, i) => i !== idx);
                          setFormData({ ...formData, cameras: newCams });
                        }} className="p-4 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-xl transition-all border border-red-500/20">
                          <Trash2 size={16} />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <button type="submit" className="bg-purple-600 p-6 rounded-3xl text-white font-black uppercase tracking-[0.2em] hover:bg-white hover:text-black transition-all mt-4 shadow-2xl shadow-purple-900/20 text-[10px]">
                Execute Deployment
              </button>
            </form>
          </div>
        </div>
      )}

      {/* 📹 UPLOAD VIDEO EVIDENCE MODAL WITH LEAFLET LOCATION PICKER */}
      {showUploadModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-md p-4 sm:p-6 overflow-y-auto">
          <div className="bg-slate-900 border border-purple-500/40 p-8 sm:p-10 rounded-[2.5rem] w-full max-w-xl relative shadow-2xl shadow-purple-950/50 max-h-[92vh] overflow-y-auto admin-scrollbar">
            <button 
              onClick={resetUploadModal} 
              className="absolute top-6 right-6 text-white/40 hover:text-white transition-colors p-2 rounded-full hover:bg-white/5"
            >
              <X size={20} />
            </button>
            
            <div className="flex items-center gap-3 mb-2">
              <div className="p-2.5 bg-purple-500/20 text-purple-400 rounded-2xl">
                <UploadCloud size={22} />
              </div>
              <div>
                <h2 className="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter text-white flex items-center gap-2">
                  Upload <span className="text-purple-500">Video Evidence</span>
                  {jobId && <span className="text-[9px] px-2 py-0.5 rounded-lg bg-purple-500/20 text-purple-400 font-mono tracking-normal not-italic">#{jobId.slice(0, 8)}</span>}
                </h2>
                <p className="text-[9px] font-black text-white/30 uppercase tracking-widest italic">
                  GPS Geotagged AI Ingestion — Bhopal Traffic Command
                </p>
              </div>
            </div>

            {uploadError && (
              <div className="my-4 p-4 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center gap-3 text-red-400 text-xs">
                <AlertCircle size={18} className="shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {jobStatus && jobStatus.status === 'completed' ? (
              <div className="my-6 p-6 rounded-3xl bg-green-500/10 border border-green-500/30 flex flex-col items-center text-center gap-4">
                <div className="p-4 bg-green-500/20 text-green-400 rounded-full">
                  <CheckCircle2 size={36} />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-white">AI Analysis Completed!</h3>
                  <p className="text-xs text-slate-300 mt-1">
                    Processed footage for <strong className="text-white">{uploadData.location_name}</strong>.
                  </p>
                  <p className="text-sm font-black text-green-400 mt-2">
                    🚨 {jobStatus.violations_found || 0} Traffic Violations Logged
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    The GIS Heatmap and node telemetry have been updated at this location.
                  </p>
                </div>
                <div className="flex gap-3 mt-2 w-full">
                  <button
                    onClick={resetUploadModal}
                    className="flex-1 bg-white text-black hover:bg-purple-600 hover:text-white py-3 rounded-2xl font-black text-xs uppercase tracking-wider transition-all"
                  >
                    Done
                  </button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleVideoUploadSubmit} className="flex flex-col gap-5 mt-4">
                {/* 1. Video File Picker */}
                <div className="flex flex-col gap-2">
                  <p className="text-[8px] font-black text-purple-400 uppercase tracking-widest ml-1">
                    Select Surveillance Video
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/mp4,video/avi,video/quicktime,video/x-matroska,.mp4,.avi,.mov"
                    className="hidden"
                    onChange={(e) => {
                      if (e.target.files && e.target.files[0]) {
                        setUploadFile(e.target.files[0]);
                        setUploadError(null);
                      }
                    }}
                  />
                  {uploadFile ? (
                    <div className="bg-white/5 border border-purple-500/40 p-4 rounded-2xl flex items-center justify-between">
                      <div className="flex items-center gap-3 truncate">
                        <div className="p-2 bg-purple-500/20 text-purple-400 rounded-xl">
                          <Film size={18} />
                        </div>
                        <div className="truncate">
                          <p className="text-xs font-bold text-white truncate">{uploadFile.name}</p>
                          <p className="text-[10px] text-slate-400 font-medium">
                            {(uploadFile.size / (1024 * 1024)).toFixed(1)} MB
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => setUploadFile(null)}
                        className="text-white/40 hover:text-red-400 text-xs px-2 py-1 transition-colors"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <div
                      onClick={() => fileInputRef.current?.click()}
                      className="border-2 border-dashed border-white/15 hover:border-purple-500/50 bg-white/5 hover:bg-white/10 transition-all rounded-2xl p-6 flex flex-col items-center justify-center cursor-pointer text-center group"
                    >
                      <UploadCloud size={28} className="text-white/30 group-hover:text-purple-400 transition-colors mb-2" />
                      <p className="text-xs font-bold text-white">Click or drag & drop video file</p>
                      <p className="text-[9px] text-white/40 mt-1 uppercase tracking-wider">
                        MP4, AVI, MOV up to 500MB
                      </p>
                    </div>
                  )}
                </div>

                {/* 2. Interactive Leaflet Map for Location Selection */}
                <div className="flex flex-col gap-2">
                  <div className="flex justify-between items-center ml-1">
                    <p className="text-[8px] font-black text-purple-400 uppercase tracking-widest">
                      Pin Video Recording Location (Heatmap Target)
                    </p>
                    <span className="text-[8px] text-white/40 font-bold">
                      {uploadData.latitude.toFixed(4)}°N, {uploadData.longitude.toFixed(4)}°E
                    </span>
                  </div>

                  <div className="h-[180px] w-full rounded-2xl overflow-hidden border border-white/10 relative z-0">
                    <MapContainer 
                      center={[uploadData.latitude, uploadData.longitude]} 
                      zoom={13} 
                      style={{ height: '100%', width: '100%' }} 
                      zoomControl={false}
                    >
                      <TileLayer 
                        key="osm-dark-upload-tiles" 
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" 
                        className="dark-map-tiles" 
                      />
                      <LocationPicker 
                        position={[uploadData.latitude, uploadData.longitude]} 
                        setPosition={(pos) => setUploadData({ ...uploadData, latitude: pos[0], longitude: pos[1] })} 
                      />
                    </MapContainer>
                    <div className="absolute bottom-2 left-2 z-[1000] bg-black/85 px-3 py-1 rounded-lg border border-white/10 backdrop-blur text-[8px] font-black uppercase tracking-widest text-purple-300 flex items-center gap-1.5 shadow-lg">
                      <MapPin size={12} className="text-purple-400" /> Click map to move PIN
                    </div>
                  </div>
                </div>

                {/* 3. Location / Junction Name & Lat/Long Coordinates */}
                <div className="flex flex-col gap-2">
                  <p className="text-[8px] font-black text-purple-400 uppercase ml-1 tracking-widest">
                    Junction / Recording Location Name
                  </p>
                  <input
                    required
                    placeholder="E.G., MP NAGAR ZONE-1"
                    className="bg-white/5 border border-white/10 p-4 rounded-2xl text-white font-bold placeholder:text-white/20 outline-none focus:border-purple-500/50 transition-all text-sm"
                    value={uploadData.location_name}
                    onChange={(e) => setUploadData({ ...uploadData, location_name: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <p className="text-[7px] font-black text-purple-400 uppercase ml-1 tracking-widest">Latitude</p>
                    <input
                      required
                      type="number"
                      step="any"
                      className="bg-white/5 border border-white/10 p-3 rounded-xl text-white font-bold outline-none focus:border-purple-500/50 transition-all text-xs"
                      value={uploadData.latitude}
                      onChange={(e) => setUploadData({ ...uploadData, latitude: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <p className="text-[7px] font-black text-purple-400 uppercase ml-1 tracking-widest">Longitude</p>
                    <input
                      required
                      type="number"
                      step="any"
                      className="bg-white/5 border border-white/10 p-3 rounded-xl text-white font-bold outline-none focus:border-purple-500/50 transition-all text-xs"
                      value={uploadData.longitude}
                      onChange={(e) => setUploadData({ ...uploadData, longitude: parseFloat(e.target.value) || 0 })}
                    />
                  </div>
                </div>

                {/* 4. Processing Progress Display */}
                {uploading && (
                  <div className="bg-white/5 border border-purple-500/20 p-4 rounded-2xl flex flex-col gap-2.5">
                    <div className="flex justify-between items-center text-xs">
                      <span className="text-white font-bold flex items-center gap-2">
                        <RefreshCw size={14} className="animate-spin text-purple-400" />
                        {jobStatus?.status === 'uploading' ? 'Uploading Video...' : 'Running AI Detection Pipeline...'}
                      </span>
                      <span className="text-purple-400 font-black">{jobStatus?.progress || 10}%</span>
                    </div>
                    <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500 rounded-full"
                        style={{ width: `${jobStatus?.progress || 10}%` }}
                      />
                    </div>
                    <p className="text-[9px] text-slate-400 italic">
                      YOLOv8 ByteTrack Tracking • Helmet Verification • Indian RTO ALPR Consensus
                    </p>
                  </div>
                )}

                {/* 5. Submit Button */}
                <button
                  type="submit"
                  disabled={uploading}
                  className={`bg-purple-600 p-5 rounded-3xl text-white font-black uppercase tracking-[0.2em] transition-all mt-2 shadow-2xl shadow-purple-900/30 text-[10px] flex items-center justify-center gap-2 ${
                    uploading ? 'opacity-50 cursor-not-allowed' : 'hover:bg-white hover:text-black'
                  }`}
                >
                  {uploading ? (
                    <>
                      <RefreshCw size={14} className="animate-spin" /> Analyzing Video ({jobStatus?.progress || 0}%)
                    </>
                  ) : (
                    <>
                      <UploadCloud size={16} /> Ingest Video & Update Heatmap
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default Surveillance;