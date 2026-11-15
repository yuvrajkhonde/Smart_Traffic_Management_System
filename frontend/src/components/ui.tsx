import React from 'react';

const tone = {
  ok: 'bg-green-500/10 text-green-400 ring-green-500/20',
  warn: 'bg-amber-500/10 text-amber-400 ring-amber-500/20',
  danger: 'bg-red-500/10 text-red-400 ring-red-500/20',
};

export const Chip = ({ t, children }: { t: keyof typeof tone; children: React.ReactNode }) => (
  <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ring-1 ${tone[t]}`}>
    <span className="h-1.5 w-1.5 rounded-full bg-current" />{children}
  </span>
);

export const Kpi = ({ icon, label, value, delta }: any) => (
  <div className="bg-surface border border-border rounded-2xl p-5">
    <div className="flex items-center justify-between text-slate-400">
      <span className="text-xs font-medium uppercase tracking-wide">{label}</span>{icon}
    </div>
    <div className="mt-3 text-3xl font-semibold text-white tabular-nums">{value}</div>
    {delta && <div className="mt-1 text-xs text-slate-400">{delta}</div>}
  </div>
);

export const barColor = (p: number) => p > 85 ? 'bg-danger' : p > 60 ? 'bg-warn' : 'bg-ok';

export const Card = ({ children, className = '' }: { children: React.ReactNode; className?: string }) => (
  <div className={`bg-surface border border-border rounded-2xl p-5 ${className}`}>
    {children}
  </div>
);
