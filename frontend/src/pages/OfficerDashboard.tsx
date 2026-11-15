import { useEffect, useState } from "react";
import { 
  ResponsiveContainer, PieChart, Pie, Cell, Tooltip, 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend 
} from "recharts";
import { apiService } from "../api/apiService";
import { 
  AlertCircle, Camera, FileText, Car, Activity,
  ShieldCheck, PlusCircle, X, Send, ShieldAlert, AlertTriangle
} from "lucide-react";
import { Kpi, Card, Chip } from "../components/ui";

const monthOrder: Record<string, number> = {
  Jan: 1, Feb: 2, Mar: 3, Apr: 4, May: 5, Jun: 6,
  Jul: 7, Aug: 8, Sep: 9, Oct: 10, Nov: 11, Dec: 12
};

const OfficerDashboard = () => {
  const [stats, setStats] = useState({ violations: 0, activeNodes: 0, accidents: 0, congestion: 0 });
  const [parkingData, setParkingData] = useState<any[]>([]);
  const [analytics, setAnalytics] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isSystemOnline, setIsSystemOnline] = useState(true);
  const [selectedCam, setSelectedCam] = useState<any>(null);

  const [showTerminal, setShowTerminal] = useState(false);
  const [challanForm, setChallanForm] = useState({ 
    plate: "", 
    type: "No Helmet",
    owner: "Unknown" 
  });

  useEffect(() => {
    const fetchDashboardData = async (isHeartbeat = false) => {
      const token = localStorage.getItem("access_token");
      if (!token) return;

      const saved = localStorage.getItem("selected_camera");
      if (saved) setSelectedCam(JSON.parse(saved));

      try {
        if (!isHeartbeat) setLoading(true);
        const [vRes, cRes, tRes, pRes, aRes] = await Promise.all([
          apiService.getViolations(),
          apiService.getCameras(),
          apiService.getCongestion(),
          apiService.getParking(),
          apiService.getAccidentAnalytics() 
        ]);

        const totalAccidentImpact = aRes.data?.reduce((sum: number, m: any) => 
            sum + (m.injuries || 0) + (m.fatalities || 0), 0) || 0;

        setStats({
          violations: vRes.data?.length || 0,
          activeNodes: cRes.data?.filter((cam: any) => cam.is_active).length || 0,
          accidents: totalAccidentImpact,
          congestion: tRes.data?.filter((r: any) => r.is_closed).length || 0
        });

        const sortedAnalytics = (aRes.data || []).sort((a: any, b: any) => {
          return (monthOrder[a.name] || 0) - (monthOrder[b.name] || 0);
        });
        setAnalytics(sortedAnalytics);
        
        let newAlerts = [];
        if (tRes.data?.some((r: any) => r.is_closed)) {
            newAlerts.push({ id: 1, type: "danger", msg: "Critical congestion detected on multiple junctions" });
        }
        if (vRes.data?.filter((v:any) => v.status === "pending").length > 0) {
            newAlerts.push({ id: 2, type: "warn", msg: `${vRes.data.filter((v:any) => v.status === "pending").length} unreviewed violations pending` });
        }
        setAlerts(newAlerts);

        if (pRes.data && pRes.data.length > 0) {
          const mainLot = pRes.data[0];
          const capacity = mainLot.total_capacity || mainLot.total_slots || 0;
          const occupied = mainLot.occupied || 0;
          setParkingData([
            { name: "Occupied", value: occupied, capacity },
            { name: "Available", value: Math.max(0, capacity - occupied), capacity },
          ]);
        }
        setIsSystemOnline(true);
        setLoading(false);
      } catch (err) {
        setIsSystemOnline(false);
        setLoading(false);
      }
    };
    fetchDashboardData();
    const heartbeat = setInterval(() => fetchDashboardData(true), 15000);
    return () => clearInterval(heartbeat);
  }, []);

  const handleIssueChallan = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        violation_type: challanForm.type,
        plate_number: challanForm.plate.toUpperCase(),
        camera_id: selectedCam.id,
        evidence_image_url: "manual_entry",
        confidence_score: 1.0
      };
      
      await apiService.issueChallan(payload);
      alert(`SUCCESS: Challan issued at ${selectedCam.location_name}`);
      setShowTerminal(false);
      setChallanForm({ plate: "", type: "No Helmet", owner: "Unknown" });
    } catch (err) {
      alert("Enforcement Sync Failed.");
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-[var(--color-bg)]">
        <Activity className="animate-spin text-accent mb-4" size={48} />
        <span className="text-sm font-medium text-slate-400">Syncing Command Center...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-8 bg-[var(--color-bg)] text-white">
      
      <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end gap-6 mb-8">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Bhopal Traffic HQ</h2>
          <p className="text-sm text-slate-400 mt-1">Central AI Surveillance Terminal</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-4">
           {selectedCam && (
              <div className="flex items-center gap-4 bg-accent/10 border border-accent/20 px-4 py-2 rounded-xl">
                  <div className="flex items-center gap-3">
                      <ShieldCheck className="text-accent" size={16} />
                      <div>
                          <p className="text-[10px] font-semibold uppercase text-accent tracking-wide">Patrolling Hotspot</p>
                          <p className="text-sm font-semibold">{selectedCam.location_name}</p>
                      </div>
                  </div>
                  <button 
                    onClick={() => setShowTerminal(true)}
                    className="bg-white text-black px-4 py-1.5 rounded-lg font-semibold text-xs hover:bg-accent hover:text-white transition-all flex items-center gap-2"
                  >
                    <PlusCircle size={14} /> Issue Challan
                  </button>
              </div>
           )}

           <Chip t={isSystemOnline ? "ok" : "danger"}>
              Network {isSystemOnline ? "Online" : "Offline"}
           </Chip>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">
        <Kpi label="Violations" icon={<FileText size={20} className="text-accent" />} value={stats.violations} delta="Total registered" />
        <Kpi label="Nodes Active" icon={<Camera size={20} className="text-blue-500" />} value={stats.activeNodes} delta="All nodes reporting" />
        <Kpi label="Accident Impact" icon={<AlertCircle size={20} className="text-red-400" />} value={stats.accidents} delta="Total lives affected" />
        <Kpi label="Congestion (Closed)" icon={<Car size={20} className="text-amber-500" />} value={stats.congestion} delta="Critical junctions" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-lg font-semibold">Accident Analytics (Monthly)</h3>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={analytics}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--color-border)" />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: "#94a3b8", fontSize: 12}} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{fill: "#94a3b8", fontSize: 12}} dx={-10} />
                  <Tooltip cursor={{fill: "rgba(255,255,255,0.02)"}} contentStyle={{ backgroundColor: "var(--color-surface)", borderRadius: "12px", border: "1px solid var(--color-border)", color: "#fff" }} />
                  <Legend verticalAlign="top" align="right" iconType="circle" wrapperStyle={{paddingBottom: "20px", fontSize: "12px", color: "#94a3b8"}} />
                  <Bar dataKey="injuries" fill="#F59E0B" radius={[4, 4, 0, 0]} barSize={16} name="Injuries" />
                  <Bar dataKey="fatalities" fill="#EF4444" radius={[4, 4, 0, 0]} barSize={16} name="Fatalities" />
                </BarChart>
              </ResponsiveContainer>
            </div>
        </Card>

        <div className="space-y-6">
            <Card className="flex flex-col items-center">
              <h3 className="text-lg font-semibold mb-4 w-full text-left">Parking Load</h3>
              <div className="h-48 w-full flex flex-col items-center justify-center relative">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={parkingData} innerRadius={60} outerRadius={80} paddingAngle={4} dataKey="value" stroke="none">
                      <Cell fill="#8B5CF6" />
                      <Cell fill="rgba(255,255,255,0.05)" />
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none mt-2">
                    <span className="text-2xl font-bold tabular-nums">
                        {parkingData[0]?.value || 0} <span className="text-sm text-slate-400 font-normal">/ {parkingData[0]?.capacity || 0}</span>
                    </span>
                    <span className="text-xs text-slate-400 mt-1">{parkingData[0]?.capacity ? Math.round(((parkingData[0]?.value||0)/parkingData[0]?.capacity)*100) : 0}% Occupied</span>
                </div>
              </div>
              <div className="mt-4 w-full">
                <div className="flex justify-between items-center text-sm p-2 bg-[var(--color-surface2)] rounded-lg">
                    <span className="text-slate-400">DB-MALL-LOT1</span>
                    <Chip t={(parkingData[0]?.value||0) > 85 ? "danger" : "ok"}>Active</Chip>
                </div>
              </div>
            </Card>

            <Card>
                <h3 className="text-lg font-semibold mb-4">Active Alerts</h3>
                <div className="space-y-3">
                    {alerts.length === 0 ? (
                        <p className="text-sm text-slate-400 text-center py-4">No active alerts ✓</p>
                    ) : (
                        alerts.map(alert => (
                            <div key={alert.id} className="flex gap-3 items-start p-3 bg-[var(--color-surface2)] rounded-xl">
                                {alert.type === "danger" ? <AlertTriangle className="text-red-400 shrink-0 mt-0.5" size={16} /> : <AlertCircle className="text-amber-400 shrink-0 mt-0.5" size={16} />}
                                <p className="text-sm text-slate-300">{alert.msg}</p>
                            </div>
                        ))
                    )}
                </div>
            </Card>
        </div>
      </div>

      {showTerminal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex items-center justify-center p-6">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-2xl p-8 w-full max-w-md relative">
            <button onClick={() => setShowTerminal(false)} className="absolute top-6 right-6 text-slate-400 hover:text-white transition-colors">
              <X size={24}/>
            </button>
            <div className="flex items-center gap-4 mb-6">
              <div className="p-3 bg-accent/20 rounded-xl"><ShieldAlert className="text-accent" size={20} /></div>
              <div>
                <h3 className="text-xl font-bold">Enforcement Terminal</h3>
                <p className="text-xs text-slate-400 mt-1">{selectedCam.location_name}</p>
              </div>
            </div>
            <form onSubmit={handleIssueChallan} className="space-y-5">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-400">Vehicle Plate Number</label>
                <input required placeholder="MP04AB1234" className="w-full bg-[var(--color-surface2)] border border-[var(--color-border)] rounded-xl p-3 text-sm font-mono focus:border-accent transition-all outline-none"
                       onChange={e => setChallanForm({...challanForm, plate: e.target.value})} />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-slate-400">Violation Type</label>
                <select className="w-full bg-[var(--color-surface2)] border border-[var(--color-border)] rounded-xl p-3 text-sm focus:border-accent transition-all outline-none appearance-none"
                        onChange={e => setChallanForm({...challanForm, type: e.target.value})}>
                  <option value="No Helmet">No Helmet</option>
                  <option value="Triple Riding">Triple Riding</option>
                  <option value="Wrong Side">Wrong Side</option>
                  <option value="Speeding">Speeding</option>
                </select>
              </div>
              <button className="w-full bg-[#8B5CF6] text-white p-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 hover:bg-[#7c3aed] transition-all">
                <Send size={16} /> Authorize & Sync
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default OfficerDashboard;