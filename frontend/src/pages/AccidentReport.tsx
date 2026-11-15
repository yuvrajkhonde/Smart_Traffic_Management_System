import React, { useState, useEffect } from 'react';
import { apiService } from '../api/apiService';
import {
  MapPin, AlertTriangle, FileText, CheckCircle2, 
  Activity, ShieldAlert, Users, Skull, Clock,
  Upload, Image as ImageIcon, Minus, Plus, Navigation
} from 'lucide-react';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix for default Leaflet icon in React
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

const AccidentReport = () => {
  const [formData, setFormData] = useState({ 
    severity: 'Minor', 
    description: '',
    injuries: 0,
    fatalities: 0,
    latitude: 23.2599,
    longitude: 77.4126
  });
  
  const [status, setStatus] = useState<'idle' | 'loading' | 'success'>('idle');
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [timestamp, setTimestamp] = useState(new Date().toLocaleString());
  const [recentReports, setRecentReports] = useState<any[]>([]);

  useEffect(() => {
    const timer = setInterval(() => setTimestamp(new Date().toLocaleString()), 1000);
    fetchRecentReports();
    return () => clearInterval(timer);
  }, []);

  const fetchRecentReports = async () => {
    try {
      const res = await apiService.getLiveAccidents();
      setRecentReports((res.data || []).slice(0, 5));
    } catch (e) {
      console.error(e);
    }
  };

  const handlePhotoUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const url = URL.createObjectURL(file);
      setPhotoPreview(url);
    }
  };

  const getUserLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setFormData(prev => ({
            ...prev,
            latitude: pos.coords.latitude,
            longitude: pos.coords.longitude
          }));
        },
        (err) => console.error(err)
      );
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('loading');
    try {
      const payload = {
        ...formData,
        injuries: parseInt(formData.injuries.toString()) || 0,
        fatalities: parseInt(formData.fatalities.toString()) || 0,
        latitude: parseFloat(formData.latitude.toString()),
        longitude: parseFloat(formData.longitude.toString())
      };
      
      await apiService.reportAccident(payload);
      setStatus('success');
      fetchRecentReports();
      setTimeout(() => {
        setStatus('idle');
        setFormData({ ...formData, description: '', injuries: 0, fatalities: 0 });
        setPhotoPreview(null);
      }, 3000);
    } catch (err) {
      console.error("Report failed:", err);
      setStatus('idle');
    }
  };

  const adjustCount = (field: 'injuries' | 'fatalities', delta: number) => {
    setFormData(prev => ({
      ...prev,
      [field]: Math.max(0, prev[field] + delta)
    }));
  };

  return (
    <div className="flex-1 relative overflow-y-auto p-6 md:p-12 font-sans transition-all duration-700 bg-[var(--color-bg)] text-white">
      <div className="max-w-[1600px] mx-auto">
        
        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <div className="p-2 bg-red-500/20 rounded-xl">
                <ShieldAlert size={24} className="text-red-500" />
              </div>
              Incident Report
            </h1>
            <p className="text-sm font-medium text-slate-400 mt-2">
              BTU Field Unit — Rapid Logging Terminal
            </p>
          </div>
        </div>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Main Form */}
          <div className="flex-1 bg-[var(--color-surface)] p-8 rounded-2xl border border-border shadow-xl">
            {status === 'success' ? (
              <div className="text-center py-24 animate-in zoom-in-95 duration-300">
                <div className="relative inline-block mb-6">
                    <CheckCircle2 size={64} className="text-green-500 relative z-10" />
                    <div className="absolute inset-0 bg-green-500 blur-2xl opacity-20 animate-ping"></div>
                </div>
                <h3 className="text-2xl font-bold text-white">Entry Validated</h3>
                <p className="text-sm text-slate-400 mt-2">Report Logged in BTU Audit Trail</p>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-8">
                
                {/* Priority Segmentation */}
                <div className="space-y-3">
                  <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                    <AlertTriangle size={14} className="text-red-500"/> Priority Level
                  </label>
                  <div className="flex p-1 bg-surface2 rounded-xl border border-border gap-1">
                    {['Minor', 'Moderate', 'Major'].map((level) => (
                      <button
                        type="button"
                        key={level}
                        onClick={() => setFormData({...formData, severity: level})}
                        className={`flex-1 py-2.5 rounded-lg text-sm font-bold transition-all ${
                          formData.severity === level 
                            ? (level === 'Major' ? 'bg-danger text-white shadow-md' : level === 'Moderate' ? 'bg-warn text-white shadow-md' : 'bg-accent text-white shadow-md')
                            : 'text-slate-400 hover:text-white hover:bg-surface'
                        }`}
                      >
                        {level}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Location Picker */}
                <div className="space-y-3">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <MapPin size={14} className="text-red-500"/> Incident Location
                    </label>
                    <button type="button" onClick={getUserLocation} className="text-xs font-medium text-accent hover:text-accent/80 flex items-center gap-1">
                      <Navigation size={12} /> Use My Location
                    </button>
                  </div>
                  <div className="h-[200px] rounded-xl overflow-hidden border border-border z-0 relative">
                    <MapContainer center={[formData.latitude, formData.longitude]} zoom={14} style={{ height: '100%', width: '100%' }} zoomControl={false}>
                      <TileLayer key="osm-dark-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-map-tiles" />
                      <LocationPicker 
                        position={[formData.latitude, formData.longitude]} 
                        setPosition={(pos) => setFormData({...formData, latitude: pos[0], longitude: pos[1]})} 
                      />
                    </MapContainer>
                  </div>
                  <div className="flex gap-4 text-xs font-mono text-slate-400">
                    <span>Lat: {formData.latitude.toFixed(6)}</span>
                    <span>Lng: {formData.longitude.toFixed(6)}</span>
                  </div>
                </div>

                {/* Steppers & Timestamp */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="space-y-3">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <Users size={14} className="text-warn"/> Injuries
                    </label>
                    <div className="flex items-center justify-between bg-surface2 p-2 rounded-xl border border-border">
                      <button type="button" onClick={() => adjustCount('injuries', -1)} className="p-2 bg-surface hover:bg-bg rounded-lg text-slate-300"><Minus size={16} /></button>
                      <span className="text-xl font-bold">{formData.injuries}</span>
                      <button type="button" onClick={() => adjustCount('injuries', 1)} className="p-2 bg-surface hover:bg-bg rounded-lg text-slate-300"><Plus size={16} /></button>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <Skull size={14} className="text-danger"/> Fatalities
                    </label>
                    <div className="flex items-center justify-between bg-surface2 p-2 rounded-xl border border-border">
                      <button type="button" onClick={() => adjustCount('fatalities', -1)} className="p-2 bg-surface hover:bg-bg rounded-lg text-slate-300"><Minus size={16} /></button>
                      <span className="text-xl font-bold">{formData.fatalities}</span>
                      <button type="button" onClick={() => adjustCount('fatalities', 1)} className="p-2 bg-surface hover:bg-bg rounded-lg text-slate-300"><Plus size={16} /></button>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <Clock size={14} className="text-accent"/> Timestamp
                    </label>
                    <div className="h-12 flex items-center px-4 bg-surface2 rounded-xl border border-border text-sm font-medium text-slate-300">
                      {timestamp}
                    </div>
                  </div>
                </div>

                {/* Description & Photo */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <div className="md:col-span-2 space-y-3">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <FileText size={14} className="text-accent"/> Tactical Summary
                    </label>
                    <textarea 
                      rows={4} required
                      placeholder="Describe vehicle types, specific location details, and visible damages..."
                      className="w-full p-4 bg-surface2 rounded-xl border border-border outline-none font-medium text-white focus:border-accent transition-all placeholder:text-slate-500 resize-none"
                      value={formData.description}
                      onChange={e => setFormData({...formData, description: e.target.value})} 
                    />
                  </div>
                  
                  <div className="space-y-3">
                    <label className="text-xs font-semibold text-slate-400 uppercase tracking-wide flex items-center gap-2">
                      <ImageIcon size={14} className="text-accent"/> Evidence
                    </label>
                    <label className="flex flex-col items-center justify-center w-full h-[106px] bg-surface2 border-2 border-dashed border-border rounded-xl cursor-pointer hover:border-accent transition-colors relative overflow-hidden">
                      {photoPreview ? (
                        <img src={photoPreview} alt="Preview" className="w-full h-full object-cover" />
                      ) : (
                        <div className="flex flex-col items-center text-slate-400">
                          <Upload size={24} className="mb-2" />
                          <span className="text-xs font-medium">Upload Photo</span>
                        </div>
                      )}
                      <input type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />
                    </label>
                  </div>
                </div>

                <button 
                  disabled={status === 'loading'}
                  className="w-full bg-danger hover:bg-danger/80 text-white p-4 rounded-xl font-bold uppercase tracking-wider transition-all shadow-lg active:scale-95 flex items-center justify-center gap-3"
                >
                  {status === 'loading' ? (
                    <Activity className="animate-spin" size={18} />
                  ) : (
                    <>Submit Official Report</>
                  )}
                </button>
              </form>
            )}
          </div>

          {/* Recent Reports Sidebar */}
          <div className="hidden xl:flex w-[400px] flex-col gap-4">
            <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wide mb-2 flex items-center gap-2">
              <Activity size={14} className="text-accent" /> Recent Dispatch Logs
            </h3>
            {recentReports.map(report => (
              <div key={report.id} className="bg-[var(--color-surface)] p-4 rounded-xl border border-border flex flex-col gap-2">
                <div className="flex justify-between items-start">
                  <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded-full ${
                    report.severity === 'Major' ? 'bg-danger/20 text-red-400' :
                    report.severity === 'Moderate' ? 'bg-warn/20 text-amber-400' :
                    'bg-accent/20 text-accent'
                  }`}>
                    {report.severity}
                  </span>
                  <span className="text-[10px] text-slate-500">{new Date(report.reported_at).toLocaleTimeString()}</span>
                </div>
                <p className="text-sm font-medium text-slate-200 line-clamp-2">{report.description}</p>
                <div className="flex gap-4 text-xs font-medium text-slate-400 mt-1">
                  <span className="flex items-center gap-1"><Users size={12}/> {report.injuries || 0}</span>
                  <span className="flex items-center gap-1 text-red-400/80"><Skull size={12}/> {report.fatalities || 0}</span>
                </div>
              </div>
            ))}
            {recentReports.length === 0 && (
              <div className="text-center py-8 text-sm text-slate-500 bg-[var(--color-surface)] rounded-xl border border-border">
                No recent incidents logged.
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};

export default AccidentReport;