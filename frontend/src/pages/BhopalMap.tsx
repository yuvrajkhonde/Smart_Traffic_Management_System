import React, { useEffect, useState, useMemo, useRef } from 'react';
import { MapContainer, TileLayer, Marker, Popup, LayersControl, Polygon, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet.heat';
import { apiService } from '../api/apiService';
import { Activity, Clock, ChevronDown, ChevronUp, Layers, RotateCw } from 'lucide-react';
import 'leaflet/dist/leaflet.css';

const RESEARCH_BLACKSPOTS = [
  { name: 'Govindpura Turning', latitude: 23.2500, longitude: 77.4500, wsi: 88 },
  { name: 'Balampur Ghati', latitude: 23.3100, longitude: 77.4900, wsi: 82 },
  { name: 'PCR Triangle', latitude: 23.2550, longitude: 77.4200, wsi: 72 },
  { name: 'Lalghati Square', latitude: 23.2800, longitude: 77.3700, wsi: 68 },
  { name: 'Karond Square', latitude: 23.3000, longitude: 77.4100, wsi: 64 }
];

// 🎨 Custom Icon for Nodes
const createPoleIcon = (isActive: boolean, isEmergency: boolean) => {
  const color = isEmergency ? '#ef4444' : (isActive ? '#9333ea' : '#475569');
  return L.divIcon({
    className: 'custom-pole-icon',
    html: `<div style="background-color: ${color}; padding: 8px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 10px rgba(0,0,0,0.3);">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="3">
              <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
              <circle cx="12" cy="13" r="4"/>
            </svg>
           </div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15]
  });
};

// 🔥 BULLETPROOF HEATLAYER: Uses setLatLngs to bypass React rendering bugs
const HeatLayer = ({ 
  data, 
  challans = [],
  hour, 
  mode, 
  isVisible 
}: { 
  data: any[], 
  challans?: any[],
  hour: number, 
  mode: 'hourly' | 'daily', 
  isVisible: boolean 
}) => {
  const map = useMap();
  const heatLayerRef = useRef<any>(null);

  // 1. Calculate the points based on time and mode
  const researchPoints = useMemo(() => {
    return RESEARCH_BLACKSPOTS.map(spot => [
      spot.latitude,
      spot.longitude,
      Math.min(Math.max(spot.wsi / 100, 0), 1)
    ]);
  }, []);

  const heatPoints = useMemo(() => {
    const liveAccidentPoints = data
      .filter(acc => {
        if (!acc.reported_at) return false;
        if (mode === 'daily') return true;
        return new Date(acc.reported_at).getHours() === hour;
      })
      .map(acc => [
        acc.latitude || 23.2599,
        acc.longitude || 77.4126,
        acc.severity === 'Major' ? 1.0 : acc.severity === 'Moderate' ? 0.75 : 0.35
      ]);

    // 🔥 DYNAMIC ENFORCEMENT & CHALLAN POINTS
    const liveChallanPoints = (challans || [])
      .filter(ch => ch.latitude && ch.longitude)
      .map(ch => [
        ch.latitude,
        ch.longitude,
        ch.intensity || 0.85
      ]);

    return [...researchPoints, ...liveAccidentPoints, ...liveChallanPoints];
  }, [data, challans, hour, mode, researchPoints]);

  // 2. Initialize the Canvas EXACTLY ONCE
  useEffect(() => {
    if (!map || !(L as any).heatLayer) return;

    const heatLayer = (L as any).heatLayer([], {
      radius: 70,
      blur: 50,
      maxZoom: 17,
      gradient: { 0.0: '#22c55e', 0.35: '#f59e0b', 0.65: '#ef4444', 1.0: '#991b1b' }
    });

    heatLayerRef.current = heatLayer;

    const attachLayer = () => {
      if (heatLayerRef.current && map && !map.hasLayer(heatLayerRef.current)) {
        heatLayerRef.current.addTo(map);
      }
    };

    if ((map as any)._loaded) {
      attachLayer();
    } else {
      map.whenReady(attachLayer);
    }

    return () => {
      if (heatLayerRef.current && map) {
        map.removeLayer(heatLayerRef.current);
      }
    };
  }, [map]);

  // 3. Update the data flawlessly without destroying the canvas
  useEffect(() => {
    if (!heatLayerRef.current || !map) return;
    if (!(map as any)._loaded) return;
    if (!heatLayerRef.current._map) {
      if (!map.hasLayer(heatLayerRef.current)) {
        heatLayerRef.current.addTo(map);
      }
      if (!heatLayerRef.current._map) return;
    }

    heatLayerRef.current.setOptions({
      radius: 60,
      blur: 40
    });

    if (isVisible && heatPoints.length > 0) {
      heatLayerRef.current.setLatLngs(heatPoints);
    } else {
      // CLEAR the canvas instantly when toggled OFF or if no data exists
      heatLayerRef.current.setLatLngs([]);
    }
  }, [heatPoints, isVisible, mode, map]);

  return null;
};

const BhopalMap = () => {
  const [nodes, setNodes] = useState<any[]>([]);
  const [congestion, setCongestion] = useState<any>({});
  const [accidents, setAccidents] = useState<any[]>([]);
  const [challans, setChallans] = useState<any[]>([]);

  // 🎛️ Control Panel States
  const [selectedHour, setSelectedHour] = useState<number>(new Date().getHours());
  const [showHeatmap, setShowHeatmap] = useState<boolean>(true);
  const [showTrafficFlow, setShowTrafficFlow] = useState<boolean>(true);
  const [timeframeMode, setTimeframeMode] = useState<'hourly' | 'daily'>('hourly');
  const [showLegend, setShowLegend] = useState<boolean>(true);

  // 🔄 Camera FOV Rotation State
  const [cameraAngles, setCameraAngles] = useState<Record<string, number>>(() => {
    try {
      return JSON.parse(localStorage.getItem('btu_fov_angles') || '{}');
    } catch {
      return {};
    }
  });

  const handleRotateNode = (camId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setCameraAngles(prev => {
      const current = prev[camId] || 0;
      const next = (current + 15) % 360;
      const newState = { ...prev, [camId]: next };
      localStorage.setItem('btu_fov_angles', JSON.stringify(newState));
      return newState;
    });
  };  // --- BhopalMap.tsx ---
  const fetchMapData = async () => {
    try {
      const [camRes, conRes, accRes, chRes] = await Promise.all([
        apiService.getCameras(),
        apiService.getCongestion(),
        apiService.getLiveAccidents(),
        apiService.getChallanHeatmap()
      ]);
      setNodes(camRes.data || []);
      setCongestion((conRes.data || []).reduce((acc: any, curr: any) => ({ ...acc, [curr.camera_id]: curr }), {}));
      setAccidents(accRes.data || []);
      setChallans(chRes.data || []);
    } catch (err) {
      console.error("GIS Grid Sync Failed");
    }
  };

  useEffect(() => {
    fetchMapData();
    const interval = setInterval(fetchMapData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getRoadColor = (level: number) => {
    if (level >= 71) return '#ef4444';
    if (level >= 31) return '#f59e0b';
    return '#22c55e';
  };

  const getAccidentSeverityScore = (acc: any) => {
    const severityBase = acc.severity === 'Major' ? 80 : acc.severity === 'Moderate' ? 50 : 25;
    return severityBase + (acc.injuries || 0) * 15 + (acc.fatalities || 0) * 30;
  };

  const getAccidentZoneColor = (acc: any) => {
    const score = getAccidentSeverityScore(acc);
    if (score >= 70) return '#ef4444';
    if (score >= 40) return '#f59e0b';
    return '#22c55e';
  };

  const getAccidentZoneRadius = (acc: any) => {
    const score = getAccidentSeverityScore(acc);
    // Increased base radius to match the bold GIS style of congestion zones
    return Math.min(450, 200 + score * 2.5);
  };

  return (
    <div className="h-full w-full rounded-2xl overflow-hidden border border-border shadow-xl relative bg-bg flex flex-col">
      <MapContainer center={[23.2500, 77.4500]} zoom={14} style={{ height: '100%', width: '100%', flexGrow: 1 }} zoomControl={false}>

        <LayersControl position="topright">
          <LayersControl.BaseLayer checked name="Dark View">
            <TileLayer key="osm-dark-tiles" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" className="dark-map-tiles" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer name="Satellite View">
            <TileLayer url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
        </LayersControl>

        {/* 🔥 The Heatmap is always mounted, but controls its own visibility data */}
        <HeatLayer data={accidents} challans={challans} hour={selectedHour} mode={timeframeMode} isVisible={showHeatmap} />

        {/* 🚨 Challan Enforcement Hotspots (dynamically rendered from issued challans) */}
        {showHeatmap && challans.map((ch: any, idx: number) => {
          if (!ch.latitude || !ch.longitude) return null;
          return (
            <Circle
              key={`ch-${idx}-${ch.latitude}-${ch.longitude}`}
              center={[ch.latitude, ch.longitude]}
              radius={Math.min(350, 160 + (ch.challan_count || 1) * 30)}
              pathOptions={{
                fillColor: '#9333ea',
                color: '#c084fc',
                fillOpacity: 0.22,
                opacity: 0.9,
                weight: 2,
                dashArray: '5 5'
              }}
            >
              <Popup>
                <div className="p-3 bg-slate-900 text-white rounded-xl border border-purple-500/30">
                  <span className="inline-block px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded-md text-[10px] font-black uppercase tracking-wider mb-1">
                    Enforcement Hotspot
                  </span>
                  <h4 className="font-bold text-sm text-white mb-2">{ch.location_name}</h4>
                  <div className="space-y-1 text-xs text-slate-300">
                    <p>• e-Challans Issued: <strong className="text-purple-400 font-bold">{ch.challan_count || 0}</strong></p>
                    <p>• Violations Recorded: <strong>{ch.violation_count || 0}</strong></p>
                    {ch.total_fines > 0 && (
                      <p>• Total Penalties: <strong className="text-green-400">₹{ch.total_fines.toLocaleString()}</strong></p>
                    )}
                    {ch.violation_types && ch.violation_types.length > 0 && (
                      <p className="text-[10px] text-slate-400 mt-1 italic">
                        Types: {ch.violation_types.join(', ')}
                      </p>
                    )}
                  </div>
                </div>
              </Popup>
            </Circle>
          );
        })}

        {/* 🚨 Explicit Accident Zones (ALWAYS VISIBLE, Never removed) */}
        {showHeatmap && accidents.map((acc) => {
          if (!acc.latitude || !acc.longitude) return null; // Safe check against DB nulls
          return (
            <Circle
              key={`acc-${acc.id ?? `${acc.latitude}-${acc.longitude}`}`}
              center={[acc.latitude, acc.longitude]}
              radius={getAccidentZoneRadius(acc)}
              pathOptions={{
                fillColor: getAccidentZoneColor(acc),
                color: getAccidentZoneColor(acc),
                fillOpacity: 0.15,
                opacity: 0.9,
                weight: 2,
                dashArray: '6 6'
              }}
            />
          );
        })}

        {(() => {
          const groupedNodes = nodes.reduce((groups: any, cam: any) => {
            const loc = cam.location_name || 'Unknown Location';
            if (!groups[loc]) groups[loc] = [];
            groups[loc].push(cam);
            return groups;
          }, {});

          return Object.entries(groupedNodes).map(([locationName, groupNodes]: [string, any]) => {
            const node = groupNodes[0];
            const hasEmergency = groupNodes.some((n: any) => (congestion[n.id] || {}).is_emergency);
            const totalVehicles = groupNodes.reduce((sum: number, n: any) => sum + ((congestion[n.id] || {}).vehicle_count || 0), 0);

            return (
              <React.Fragment key={locationName}>
                {showTrafficFlow && groupNodes.map((cam: any) => {
                  const camCongestion = congestion[cam.id] || {};
                  // The camera's individual congestion level
                  const level = camCongestion.congestion_level || 0;
                  const cColor = getRoadColor(level);
                  
                  // Calculate Field of View Cone (Polygon)
                  const lat = cam.latitude;
                  const lng = cam.longitude;
                  const radius = 0.0012; // Length of the cone (~130m)
                  const spread = 45; // Degrees of FOV width
                  
                  let baseAngle = 0;
                  if (cam.direction === 'N') baseAngle = 0;
                  else if (cam.direction === 'E') baseAngle = 90;
                  else if (cam.direction === 'S') baseAngle = 180;
                  else if (cam.direction === 'W') baseAngle = 270;

                  // Apply user-defined rotation offset
                  const finalAngle = baseAngle + (cameraAngles[cam.id] || 0);

                  // Convert degrees to radians for math
                  const radLeft = (finalAngle - spread / 2) * (Math.PI / 180);
                  const radRight = (finalAngle + spread / 2) * (Math.PI / 180);

                  // Calculate the two outer points of the cone
                  const leftLat = lat + radius * Math.cos(radLeft);
                  // Adjust longitude by cos(latitude) to fix aspect ratio projection
                  const lngAspect = Math.cos(lat * Math.PI / 180);
                  const leftLng = lng + (radius * Math.sin(radLeft)) / lngAspect;
                  
                  const rightLat = lat + radius * Math.cos(radRight);
                  const rightLng = lng + (radius * Math.sin(radRight)) / lngAspect;

                  // A triangle originating from the camera
                  const conePositions: [number, number][] = [
                    [lat, lng],
                    [leftLat, leftLng],
                    [rightLat, rightLng]
                  ];

                  return (
                    <Polygon
                      key={`flow-${cam.id}`}
                      positions={conePositions}
                      pathOptions={{
                        fillColor: cColor,
                        fillOpacity: 0.4,
                        color: cColor,
                        weight: 1,
                        opacity: 0.8
                      }}
                    />
                  );
                })}

                <Marker position={[node.latitude, node.longitude]} icon={createPoleIcon(true, hasEmergency)}>
                  <Popup>
                    <div className="w-64 font-sans overflow-hidden rounded-lg bg-surface2 border border-border">
                      <div className="p-4 text-white">
                        <div className="flex items-center gap-2 mb-2">
                          <Activity size={14} className="text-accent" />
                          <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">Junction</span>
                        </div>
                        <h4 className="text-sm font-bold uppercase leading-none">{locationName}</h4>
                        <p className="text-[10px] text-accent font-bold mt-1.5 uppercase tracking-widest bg-accent/10 w-max px-2 py-0.5 rounded-sm">{groupNodes.length} Cameras Installed</p>
                        <div className="flex justify-between mt-4 border-t border-border pt-3 items-center">
                          <span className="text-xs font-bold text-slate-300 flex items-center gap-1">
                            <Activity size={12} /> {totalVehicles} Veh (Avg)
                          </span>
                          <span className={`text-[9px] font-black px-2 py-1 rounded uppercase tracking-wider ${hasEmergency ? 'bg-red-500/20 text-red-500 border border-red-500/30' : 'bg-green-500/20 text-green-400 border border-green-500/30'}`}>
                            {hasEmergency ? 'Emergency' : 'Stable'}
                          </span>
                        </div>
                        <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
                          <span className="text-[10px] uppercase tracking-widest text-slate-400 font-bold mb-1">Adjust Fields of View</span>
                          {groupNodes.map((c: any) => (
                            <div key={c.id} className="flex justify-between items-center text-xs">
                              <span className="text-slate-300 font-semibold">Lane {c.direction || 'Auto'}</span>
                              <button onClick={(e) => handleRotateNode(c.id, e)} className="p-1.5 hover:bg-white/10 rounded bg-surface border border-border transition-colors text-accent flex items-center gap-1 text-[10px] uppercase font-bold tracking-wider">
                                <RotateCw size={12} /> Rotate
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </Popup>
                </Marker>
              </React.Fragment>
            );
          });
        })()}
      </MapContainer>

      {/* 🎛️ ADVANCED CONTROL PANEL */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-[1000] w-[90%] max-w-2xl bg-[var(--color-surface)]/80 backdrop-blur-md p-5 rounded-2xl shadow-2xl border border-border text-white">

        <div className="flex justify-between items-center mb-4">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-2">
            <Clock size={16} className="text-accent" /> GIS Controls
          </span>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs font-medium text-slate-300">Flow</span>
              <div className={`w-10 h-5 flex items-center rounded-full p-1 transition-colors ${showTrafficFlow ? 'bg-accent' : 'bg-surface2 border border-border'}`} onClick={() => setShowTrafficFlow(!showTrafficFlow)}>
                <div className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${showTrafficFlow ? 'translate-x-5' : 'translate-x-0'}`}></div>
              </div>
            </label>

            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs font-medium text-slate-300">Heatmap</span>
              <div className={`w-10 h-5 flex items-center rounded-full p-1 transition-colors ${showHeatmap ? 'bg-red-500' : 'bg-surface2 border border-border'}`} onClick={() => setShowHeatmap(!showHeatmap)}>
                <div className={`bg-white w-3.5 h-3.5 rounded-full shadow-md transform transition-transform ${showHeatmap ? 'translate-x-5' : 'translate-x-0'}`}></div>
              </div>
            </label>

            <button
              onClick={() => setTimeframeMode(m => m === 'hourly' ? 'daily' : 'hourly')}
              className="px-3 py-1.5 rounded-lg text-xs font-semibold border bg-surface2 text-slate-200 border-border hover:bg-surface transition-all shadow-sm"
            >
              {timeframeMode === 'hourly' ? '⏱️ Hourly' : '📅 Daily'}
            </button>

            {timeframeMode === 'hourly' && (
              <span className="text-sm font-bold text-accent min-w-[70px]">
                {selectedHour}:00 {selectedHour >= 12 ? 'PM' : 'AM'}
              </span>
            )}
          </div>
        </div>

        {timeframeMode === 'hourly' ? (
          <input
            type="range" min="0" max="23" value={selectedHour}
            onChange={(e) => setSelectedHour(parseInt(e.target.value))}
            className="w-full h-1.5 bg-surface2 rounded-lg appearance-none cursor-pointer accent-accent"
          />
        ) : (
          <div className="w-full text-center py-2 bg-accent/10 rounded-xl border border-accent/20">
            <span className="text-xs font-semibold text-accent/80">
              Aggregating 24-Hour Accident Data Clusters
            </span>
          </div>
        )}
      </div>

      {/* 🧭 GIS LEGEND */}
      <div className="absolute top-6 left-6 z-[1000] bg-[var(--color-surface)]/90 backdrop-blur-md shadow-lg border border-border p-4 rounded-2xl flex flex-col gap-3 min-w-[200px]">
        <div className="flex justify-between items-center cursor-pointer" onClick={() => setShowLegend(!showLegend)}>
          <span className="text-xs font-bold text-white flex items-center gap-2"><Layers size={14} /> Legend</span>
          {showLegend ? <ChevronUp size={16} className="text-slate-400" /> : <ChevronDown size={16} className="text-slate-400" />}
        </div>
        
        {showLegend && (
          <div className="flex flex-col gap-2 mt-2 border-t border-border pt-3">
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-accent shadow-[0_0_8px_var(--color-accent)]"></div>
              <span className="text-xs font-medium text-slate-300">AI Node</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-purple-500 shadow-[0_0_8px_#a855f7]"></div>
              <span className="text-xs font-medium text-slate-300">Challan Hotspot ({challans.length})</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full bg-gradient-to-r from-blue-500 to-red-500"></div>
              <span className="text-xs font-medium text-slate-300">Heatmap</span>
            </div>
            <div className="flex items-center gap-3 border-t pt-2 border-border mt-1">
              <div className="w-5 h-1.5 rounded-full bg-ok"></div>
              <span className="text-xs font-medium text-slate-300">Clear Flow</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full border border-ok bg-ok/20"></div>
              <span className="text-xs font-medium text-slate-300">Low Risk Accident</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full border border-warn bg-warn/20"></div>
              <span className="text-xs font-medium text-slate-300">Med Risk Accident</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="w-2.5 h-2.5 rounded-full border border-danger bg-danger/20"></div>
              <span className="text-xs font-medium text-slate-300">High Risk Accident</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default BhopalMap;