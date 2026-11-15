import { Navigation, Clock } from 'lucide-react';

const TrafficCongestion = () => {
  return (
    <div className="flex-1 relative flex flex-col items-center justify-center p-8 overflow-hidden bg-[var(--color-bg)] text-white font-sans">
      <div className="absolute inset-0 bg-orange-500/5 blur-[120px] rounded-full pointer-events-none" />
      <div className="relative z-10 p-12 rounded-[2.5rem] border border-white/10 bg-white/[0.02] backdrop-blur-3xl flex flex-col items-center text-center max-w-md shadow-2xl">
        <div className="p-4 bg-orange-500/10 border border-orange-500/20 rounded-2xl text-orange-400 mb-6 shadow-lg shadow-orange-500/10">
          <Navigation size={36} />
        </div>
        <h2 className="text-white/80 font-bold tracking-tight text-lg">
          Traffic Congestion Module
        </h2>
        <p className="text-white/40 text-xs font-medium mt-2 leading-relaxed">
          This module is currently inactive and in standby mode. Road network telemetry and dynamic signal adjustments will be connected in the upcoming phase.
        </p>
        <div className="mt-6 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-[10px] font-bold text-slate-400 flex items-center gap-1.5 uppercase tracking-wider">
          <Clock size={12} /> Offline • Pending Module Work
        </div>
      </div>
    </div>
  );
};

export default TrafficCongestion;