import { 
  LayoutDashboard, Camera, Car, AlertTriangle, 
  FileText, BarChart3, LogOut, ParkingCircle, Shield,Map as MapIcon
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onLogout: () => void;
  role: string | null; 
}

import { useState, useEffect } from 'react';
import { apiService } from '../api/apiService';

const Sidebar = ({ activeTab, setActiveTab, onLogout, role }: SidebarProps) => {
  const design = {
    sidebarBg: "var(--color-surface)", 
    border: "var(--color-border)",
  };

  const [criticalTraffic, setCriticalTraffic] = useState(0);
  const [pendingChallans, setPendingChallans] = useState(0);

  useEffect(() => {
    if (!role) return;
    const fetchStats = async () => {
      try {
        const [tRes, vRes] = await Promise.all([
          apiService.getCongestion(),
          apiService.getViolations()
        ]);
        const criticalCount = (tRes.data || []).filter((t: any) => t.is_emergency || t.congestion_level >= 80).length;
        setCriticalTraffic(criticalCount);
        
        const pendingCount = (vRes.data || []).filter((v: any) => v.status === 'pending').length;
        setPendingChallans(pendingCount);
      } catch (err) {
        // fail silently
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, [role]);

  const menuItems = [
    { id: 'overview', label: 'Overview', icon: <LayoutDashboard size={18} />, roles: ['admin', 'officer'] },
    { id: 'surveillance', label: 'Surveillance', icon: <Camera size={18} />, roles: ['admin', 'officer'] },
    { id: 'live-map', label: 'Live Grid Map', icon: <MapIcon size={18} />, roles: ['admin', 'officer'] },
    { id: 'traffic', label: 'Traffic', icon: <Car size={18} />, roles: ['admin', 'officer'], badge: criticalTraffic > 0 ? { text: `${criticalTraffic} critical`, tone: 'bg-red-500/20 text-red-400' } : null },
    { id: 'accidents', label: 'Accidents', icon: <AlertTriangle size={18} />, roles: ['admin', 'officer'] },
    { id: 'parking', label: 'Parking', icon: <ParkingCircle size={18} />, roles: ['admin', 'officer'] },
    { id: 'e-challan', label: 'E-Challan', icon: <FileText size={18} />, roles: ['admin', 'officer'], badge: pendingChallans > 0 ? { text: `${pendingChallans} pending`, tone: 'bg-amber-500/20 text-amber-400' } : null },
    { id: 'reports', label: 'Reports', icon: <BarChart3 size={18} />, roles: ['admin'] },
  ];

  return (
    <div 
      style={{ backgroundColor: design.sidebarBg, borderColor: design.border }}
      className="w-64 h-screen flex flex-col border-r z-50 transition-all duration-500"
    >
      {/* 🏙️ FIXED: BTU Branding Section (Does not scroll) */}
      <div className="p-8 flex flex-col items-center text-center shrink-0">
        <div className="w-16 h-16 bg-accent rounded-2xl flex items-center justify-center mb-4">
          <Shield className="text-white" size={28} />
        </div>
        <h1 className="text-xl font-bold text-white tracking-wide uppercase leading-none">BTU</h1>
        <div className="flex items-center gap-2 mt-3 bg-white/5 px-3 py-1 rounded-full border border-border">
            <div className="h-1.5 w-1.5 rounded-full bg-accent"></div>
            <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wide">
                {role ? `BTU ${role}` : 'AUTH_REQD'}
            </p>
        </div>
      </div>

      {/* 🚀 SCROLLABLE: Navigation Items Section */}
      <nav className="flex-1 px-6 space-y-3 mt-6 overflow-y-auto 
                      scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent 
                      hover:scrollbar-thumb-purple-500/30 transition-all duration-300">
        {menuItems.map((item) => {
          if (role && !item.roles.includes(role.toLowerCase())) return null;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-300 group ${
                isActive ? 'bg-accent/10 text-white' : 'text-slate-400 hover:text-white hover:bg-white/5'
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`${isActive ? 'text-accent' : 'text-slate-500 group-hover:text-slate-300'} transition-colors`}>
                  {item.icon}
                </div>
                <span className="text-[13px] font-medium">
                  {item.label}
                </span>
              </div>
              {item.badge && (
                <span className={`text-[9px] font-medium px-1.5 py-0.5 rounded-md ${item.badge.tone}`}>
                  {item.badge.text}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* 🚪 FIXED: Logout Section (Always visible at bottom) */}
      <div className="p-6 border-t border-border shrink-0">
        <button 
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-red-400/80 hover:bg-red-500/10 hover:text-red-400 transition-all duration-300 group"
        >
          <LogOut size={18} className="group-hover:-translate-x-1 transition-transform" />
          <span className="text-[13px] font-medium">Close Session</span>
        </button>
      </div>
    </div>
  );
};

export default Sidebar;