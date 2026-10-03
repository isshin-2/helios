import React, { useState, useEffect, useRef } from 'react';
import { 
  Droplets, Thermometer, Radio, Activity, AlertTriangle, ShieldCheck, 
  RotateCcw, Sliders, Play, Pause, Compass, Zap, Eye, BatteryCharging,
  Maximize2, Terminal
} from 'lucide-react';

export default function LiveSimulators() {
  const [activeSim, setActiveSim] = useState('aquapulse');

  return (
    <section id="simulators" style={{ padding: '80px 24px', maxWidth: '1280px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '40px' }}>
        <div className="badge-status badge-cyan" style={{ marginBottom: '12px' }}>
          <Activity size={14} /> Interactive Hardware Simulators
        </div>
        <h2 className="font-display" style={{ fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '12px' }}>
          Live Firmware & Telemetry Emulators
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '640px', margin: '0 auto', fontSize: '1.05rem' }}>
          Interact with simulated sensor hardware running the actual packet protocols, EMA filter pipelines, and failsafe routines built into my physical projects.
        </p>
      </div>

      {/* Simulator Switcher Tabs */}
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        gap: '12px', 
        marginBottom: '36px',
        flexWrap: 'wrap'
      }}>
        <button 
          onClick={() => setActiveSim('aquapulse')}
          className={`cyber-btn ${activeSim === 'aquapulse' ? '' : 'cyber-btn-secondary'}`}
          style={{ padding: '10px 20px', borderRadius: '10px', fontSize: '0.9rem' }}
        >
          <Droplets size={16} /> AquaPulse Tank Level Hub
        </button>
        <button 
          onClick={() => setActiveSim('tempsense')}
          className={`cyber-btn ${activeSim === 'tempsense' ? '' : 'cyber-btn-secondary'}`}
          style={{ padding: '10px 20px', borderRadius: '10px', fontSize: '0.9rem' }}
        >
          <Thermometer size={16} /> TEMPSENSE Cold Chain Port 1024
        </button>
        <button 
          onClick={() => setActiveSim('rover')}
          className={`cyber-btn ${activeSim === 'rover' ? '' : 'cyber-btn-secondary'}`}
          style={{ padding: '10px 20px', borderRadius: '10px', fontSize: '0.9rem' }}
        >
          <Compass size={16} /> AgriTech Rover Telemetry Deck
        </button>
      </div>

      {/* Active Simulator Container */}
      <div className="glass-panel" style={{ padding: '32px', position: 'relative', overflow: 'hidden' }}>
        {activeSim === 'aquapulse' && <AquaPulseSimulator />}
        {activeSim === 'tempsense' && <TempSenseSimulator />}
        {activeSim === 'rover' && <RoverSimulator />}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. AQUAPULSE SIMULATOR
// ─────────────────────────────────────────────────────────────────────────────
function AquaPulseSimulator() {
  const [tankHeight, setTankHeight] = useState(250); // cm
  const [waterLevel, setWaterLevel] = useState(175); // cm
  const [filterEnabled, setFilterEnabled] = useState(true);
  const [noiseEnabled, setNoiseEnabled] = useState(true);
  const [rawHistory, setRawHistory] = useState([]);
  const [filteredDist, setFilteredDist] = useState(750); // distance in mm
  const [packetStream, setPacketStream] = useState([]);

  // Tank radius in cm (for volume calculation: pi * r^2 * h)
  const tankRadius = 60; // 60cm radius
  const maxVolumeLiters = Math.round((Math.PI * Math.pow(tankRadius, 2) * tankHeight) / 1000);
  const currentVolumeLiters = Math.round((Math.PI * Math.pow(tankRadius, 2) * waterLevel) / 1000);
  const percentage = Math.min(100, Math.max(0, Math.round((waterLevel / tankHeight) * 100)));

  // Simulated ultrasonic sensor reading loop
  useEffect(() => {
    const interval = setInterval(() => {
      // Physical distance from sensor (at top) to water surface = (tankHeight - waterLevel) in mm
      const trueDistanceMM = Math.max(100, (tankHeight - waterLevel) * 10);
      let noise = 0;
      if (noiseEnabled) {
        // occasional acoustic echo spike or random water ripple noise
        const spike = Math.random() < 0.15 ? (Math.random() - 0.5) * 180 : (Math.random() - 0.5) * 20;
        noise = Math.round(spike);
      }
      const rawDistance = Math.max(50, trueDistanceMM + noise);

      setRawHistory(prev => {
        const next = [...prev.slice(-4), rawDistance];
        
        // Median-of-5 calculation
        let medianVal = rawDistance;
        if (next.length === 5) {
          const sorted = [...next].sort((a, b) => a - b);
          medianVal = sorted[2];
        }

        // EMA smoothing: EMA = alpha * sample + (1 - alpha) * prevEMA
        const alpha = 0.25;
        setFilteredDist(prevEMA => {
          if (!filterEnabled) return rawDistance;
          return Math.round(alpha * medianVal + (1 - alpha) * prevEMA);
        });

        return next;
      });

      // Generate DYP-A02YYTW 4-byte serial packet: [0xFF, High, Low, Checksum]
      const distToSend = filterEnabled ? filteredDist : rawDistance;
      const dataHigh = (distToSend >> 8) & 0xFF;
      const dataLow = distToSend & 0xFF;
      const checksum = (0xFF + dataHigh + dataLow) & 0xFF;
      const hexPacket = `[ 0xFF, 0x${dataHigh.toString(16).padStart(2, '0').toUpperCase()}, 0x${dataLow.toString(16).padStart(2, '0').toUpperCase()}, 0x${checksum.toString(16).padStart(2, '0').toUpperCase()} ]`;

      setPacketStream(prev => [
        { time: new Date().toLocaleTimeString(), packet: hexPacket, mm: distToSend },
        ...prev.slice(0, 5)
      ]);
    }, 600);

    return () => clearInterval(interval);
  }, [tankHeight, waterLevel, filterEnabled, noiseEnabled, filteredDist]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h3 className="font-display" style={{ fontSize: '1.4rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Droplets style={{ color: 'var(--accent-cyan)' }} />
            AquaPulse WLMS Digital Twin
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            ESP32 ST7789 Dual-Core Hub & Seeed XIAO C3 DYP-A02YYTW Ultrasonic Link
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button 
            onClick={() => setFilterEnabled(!filterEnabled)}
            className={`cyber-btn ${filterEnabled ? '' : 'cyber-btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            {filterEnabled ? '✓ Median-of-5 + EMA ACTIVE' : 'Filter Disabled (Raw)'}
          </button>
          <button 
            onClick={() => setNoiseEnabled(!noiseEnabled)}
            className={`cyber-btn ${noiseEnabled ? '' : 'cyber-btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            {noiseEnabled ? 'Acoustic Ripple ON' : 'Noise OFF'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '28px' }}>
        {/* Left: Tank Visualization */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', background: 'rgba(5, 8, 15, 0.6)', padding: '24px', borderRadius: '12px', border: '1px solid rgba(0, 229, 255, 0.1)' }}>
          <div style={{ 
            position: 'relative', 
            width: '180px', 
            height: '260px', 
            borderRadius: '16px 16px 20px 20px', 
            border: '3px solid rgba(0, 229, 255, 0.4)',
            overflow: 'hidden',
            background: 'rgba(15, 23, 42, 0.6)',
            boxShadow: 'inset 0 0 20px rgba(0, 0, 0, 0.8), 0 0 15px rgba(0, 229, 255, 0.15)'
          }}>
            {/* Top sensor badge */}
            <div style={{ 
              position: 'absolute', 
              top: '4px', 
              left: '50%', 
              transform: 'translateX(-50%)', 
              background: '#1e293b', 
              padding: '2px 8px', 
              borderRadius: '4px', 
              fontSize: '0.65rem', 
              color: 'var(--accent-cyan)',
              border: '1px solid rgba(0, 229, 255, 0.3)',
              zIndex: 10
            }}>
              DYP-A02YYTW
            </div>

            {/* Ultrasonic wave animation */}
            <div style={{
              position: 'absolute',
              top: '24px',
              left: '50%',
              transform: 'translateX(-50%)',
              width: '120px',
              height: `${Math.max(10, 260 - (260 * (percentage / 100)) - 24)}px`,
              borderBottom: '2px dashed rgba(0, 229, 255, 0.5)',
              opacity: 0.6,
              zIndex: 5,
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-around',
              alignItems: 'center'
            }}>
              <span style={{ fontSize: '0.65rem', color: 'var(--accent-cyan)', background: 'rgba(8, 12, 20, 0.8)', padding: '1px 4px', borderRadius: '2px' }}>
                Distance: {filteredDist} mm
              </span>
            </div>

            {/* Animated Water Level */}
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: `${percentage}%`,
              background: 'linear-gradient(180deg, rgba(0, 229, 255, 0.75) 0%, rgba(0, 119, 255, 0.85) 100%)',
              transition: 'height 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
              boxShadow: '0 -4px 15px rgba(0, 229, 255, 0.5)'
            }}>
              {/* Surface line */}
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                height: '4px',
                background: '#ffffff',
                opacity: 0.8,
                filter: 'blur(1px)'
              }}></div>
            </div>

            {/* Level percentage overlay */}
            <div style={{
              position: 'absolute',
              bottom: '12px',
              left: '50%',
              transform: 'translateX(-50%)',
              fontFamily: 'var(--font-display)',
              fontSize: '1.8rem',
              fontWeight: 800,
              color: '#ffffff',
              textShadow: '0 2px 8px rgba(0, 0, 0, 0.8)',
              zIndex: 10
            }}>
              {percentage}%
            </div>
          </div>

          <div style={{ marginTop: '16px', display: 'flex', gap: '20px', textAlign: 'center' }}>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>CURRENT VOLUME</div>
              <div className="font-mono" style={{ fontSize: '1.1rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                {currentVolumeLiters} L
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>MAX CAPACITY</div>
              <div className="font-mono" style={{ fontSize: '1.1rem', color: 'var(--text-primary)', fontWeight: 600 }}>
                {maxVolumeLiters} L
              </div>
            </div>
          </div>
        </div>

        {/* Middle: Controls & Thresholds */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              <span>Simulated Water Level (cm)</span>
              <span className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{waterLevel} cm / {tankHeight} cm</span>
            </label>
            <input 
              type="range" 
              min="0" 
              max={tankHeight} 
              value={waterLevel} 
              onChange={(e) => setWaterLevel(Number(e.target.value))} 
            />
          </div>

          <div>
            <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              <span>Tank Total Height (cm)</span>
              <span className="font-mono">{tankHeight} cm</span>
            </label>
            <input 
              type="range" 
              min="100" 
              max="400" 
              value={tankHeight} 
              onChange={(e) => {
                const newH = Number(e.target.value);
                setTankHeight(newH);
                if (waterLevel > newH) setWaterLevel(newH);
              }} 
            />
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.4)', padding: '16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ST7789 Hub Display Status
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div className={`pulse-indicator`} style={{ backgroundColor: percentage < 20 ? '#ff1744' : percentage > 90 ? '#ffb300' : '#00e676' }}></div>
                <span style={{ fontSize: '0.9rem', fontWeight: 600 }}>
                  {percentage < 20 ? 'CRITICAL LOW TANK' : percentage > 90 ? 'OVERFLOW WARNING' : 'NOMINAL LEVEL'}
                </span>
              </div>
              <span className="badge-status badge-cyan font-mono">ESP-NOW MESH</span>
            </div>
          </div>
        </div>

        {/* Right: DYP-A02YYTW Serial Stream */}
        <div style={{ background: '#050810', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.15)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
              <Terminal size={14} /> RS485 UART Stream (9600 8N1)
            </div>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>0x55 Reply Frame</span>
          </div>

          <div className="font-mono" style={{ fontSize: '0.75rem', display: 'flex', flexDirection: 'column', gap: '6px', overflowY: 'hidden', flex: 1 }}>
            {packetStream.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', opacity: 1 - idx * 0.15 }}>
                <span style={{ color: 'var(--text-muted)' }}>{item.time}</span>
                <span style={{ color: 'var(--accent-cyan)' }}>{item.packet}</span>
                <span style={{ color: '#00e676' }}>{item.mm}mm</span>
              </div>
            ))}
          </div>

          <div style={{ marginTop: '12px', paddingTop: '8px', borderTop: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
            Header: 0xFF | HighByte | LowByte | Checksum: (0xFF + H + L) & 0xFF
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. TEMPSENSE SIMULATOR
// ─────────────────────────────────────────────────────────────────────────────
function TempSenseSimulator() {
  const [temperature, setTemperature] = useState(-18.5); // Deep freeze default
  const [humidity, setHumidity] = useState(42.0);
  const [autoDrift, setAutoDrift] = useState(true);
  const [roomType, setRoomType] = useState('vaccine_deep_freeze'); // vaccine vs ambient
  const [eventLogs, setEventLogs] = useState([]);

  // Safe limits based on room type
  const thresholds = roomType === 'vaccine_deep_freeze' 
    ? { min: -25, max: -15, label: "Cold Chain Deep Freeze (-25°C to -15°C)" }
    : { min: 2, max: 8, label: "Pharmaceutical Cold Room (2°C to 8°C)" };

  const isExcursion = temperature < thresholds.min || temperature > thresholds.max;

  useEffect(() => {
    let timer;
    if (autoDrift) {
      timer = setInterval(() => {
        setTemperature(prev => {
          // slight thermal perturbation
          const delta = (Math.random() - 0.48) * 0.4;
          return Number((prev + delta).toFixed(2));
        });
      }, 800);
    }
    return () => clearInterval(timer);
  }, [autoDrift]);

  // Log events on excursion
  useEffect(() => {
    const timestamp = new Date().toLocaleTimeString();
    const packet = `SITE_01|RM_02|T:${temperature.toFixed(1)}|H:${humidity.toFixed(1)}|CRC:0x${Math.floor(Math.random() * 255).toString(16).toUpperCase()}`;
    
    setEventLogs(prev => [
      {
        time: timestamp,
        temp: temperature,
        isAlert: isExcursion,
        packet: packet
      },
      ...prev.slice(0, 6)
    ]);
  }, [temperature, humidity, isExcursion]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h3 className="font-display" style={{ fontSize: '1.4rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Thermometer style={{ color: isExcursion ? '#ff1744' : 'var(--accent-emerald)' }} />
            TEMPSENSE Cold Chain Live Daemon
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            High-Throughput Raw TCP Ingestion (Port 1024) & PostgreSQL 15 Alert Engine
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button 
            onClick={() => {
              setRoomType(roomType === 'vaccine_deep_freeze' ? 'pharma_cold' : 'vaccine_deep_freeze');
              setTemperature(roomType === 'vaccine_deep_freeze' ? 4.5 : -18.5);
            }}
            className="cyber-btn cyber-btn-secondary"
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            Switch Profile: {roomType === 'vaccine_deep_freeze' ? 'Deep Freeze (-20°C)' : 'Cold Room (+4°C)'}
          </button>
          <button 
            onClick={() => setAutoDrift(!autoDrift)}
            className={`cyber-btn ${autoDrift ? '' : 'cyber-btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            {autoDrift ? 'Thermal Drift: ACTIVE' : 'Thermal Drift: PAUSED'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
        {/* Gauge & Excursion Alert */}
        <div style={{ background: 'rgba(5, 8, 15, 0.6)', padding: '24px', borderRadius: '12px', border: `1px solid ${isExcursion ? 'rgba(255, 23, 68, 0.5)' : 'rgba(0, 230, 118, 0.3)'}`, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
            {thresholds.label}
          </div>
          
          <div className="font-display" style={{ 
            fontSize: '3.5rem', 
            fontWeight: 800, 
            color: isExcursion ? '#ff1744' : '#00e676',
            textShadow: isExcursion ? '0 0 20px rgba(255, 23, 68, 0.5)' : '0 0 20px rgba(0, 230, 118, 0.3)',
            lineHeight: 1
          }}>
            {temperature.toFixed(1)}°C
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '14px' }}>
            <span className={`badge-status ${isExcursion ? 'badge-amber' : 'badge-active'}`} style={{ backgroundColor: isExcursion ? 'rgba(255, 23, 68, 0.15)' : undefined, color: isExcursion ? '#ff1744' : undefined, borderColor: isExcursion ? 'rgba(255, 23, 68, 0.4)' : undefined }}>
              {isExcursion ? '⚠️ CRITICAL TEMPERATURE EXCURSION' : '✓ COMPLIANCE ENVELOPE SAFE'}
            </span>
          </div>

          <div style={{ width: '100%', marginTop: '24px', display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <span>Relative Humidity: <strong className="font-mono" style={{ color: 'var(--accent-cyan)' }}>{humidity.toFixed(1)}%</strong></span>
            <span>Site ID: <strong className="font-mono">BLR-STORAGE-01</strong></span>
          </div>
        </div>

        {/* Interactive Sliders */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div>
            <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              <span>Manual Temperature Perturbation</span>
              <span className="font-mono">{temperature.toFixed(1)}°C</span>
            </label>
            <input 
              type="range" 
              min="-35" 
              max="20" 
              step="0.1"
              value={temperature} 
              onChange={(e) => {
                setAutoDrift(false);
                setTemperature(Number(e.target.value));
              }} 
            />
          </div>

          <div>
            <label style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
              <span>Humidity Chamber Level</span>
              <span className="font-mono">{humidity.toFixed(1)}%</span>
            </label>
            <input 
              type="range" 
              min="10" 
              max="95" 
              step="0.5"
              value={humidity} 
              onChange={(e) => setHumidity(Number(e.target.value))} 
            />
          </div>

          <div style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '0.8rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Automated SMTP Dispatch:</span>
              <span style={{ color: isExcursion ? '#ff1744' : '#00e676', fontWeight: 600 }}>
                {isExcursion ? 'FIRING ALERT (Site Admin)' : 'IDLE / STANDBY'}
              </span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span style={{ color: 'var(--text-muted)' }}>PDF Compliance Audit:</span>
              <span style={{ color: 'var(--accent-cyan)' }}>SHA-256 Digest Active</span>
            </div>
          </div>
        </div>

        {/* Port 1024 TCP Socket Stream */}
        <div style={{ background: '#050810', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.15)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
              Raw TCP Stream :1024
            </span>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Net.Server Ingest</span>
          </div>

          <div className="font-mono" style={{ fontSize: '0.7rem', display: 'flex', flexDirection: 'column', gap: '6px', flex: 1 }}>
            {eventLogs.map((log, idx) => (
              <div key={idx} style={{ 
                padding: '4px 6px', 
                borderRadius: '4px',
                background: log.isAlert ? 'rgba(255, 23, 68, 0.12)' : 'transparent',
                borderLeft: log.isAlert ? '2px solid #ff1744' : '2px solid rgba(0, 229, 255, 0.2)'
              }}>
                <span style={{ color: 'var(--text-muted)', marginRight: '6px' }}>{log.time}</span>
                <span style={{ color: log.isAlert ? '#ff1744' : '#94a3b8' }}>{log.packet}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. AGRITECH ROVER SIMULATOR
// ─────────────────────────────────────────────────────────────────────────────
function RoverSimulator() {
  const [throttle, setThrottle] = useState(0); // -255 to +255
  const [steering, setSteering] = useState(0); // -255 to +255
  const [pumpActive, setPumpActive] = useState(false);
  const [obstacles, setObstacles] = useState({
    frontCenter: 85,
    frontLeft: 120,
    frontRight: 110,
    rear: 160,
    left: 95,
    right: 90
  });

  const isHardStop = obstacles.frontCenter < 25 || obstacles.frontLeft < 20 || obstacles.frontRight < 20;

  // Handle virtual joystick controls
  const handleDrive = (th, st) => {
    if (isHardStop && th > 0) {
      setThrottle(0); // Failsafe hard-stop prevents forward motion
    } else {
      setThrottle(th);
    }
    setSteering(st);
  };

  const stopMotors = () => {
    setThrottle(0);
    setSteering(0);
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <h3 className="font-display" style={{ fontSize: '1.4rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Compass style={{ color: 'var(--accent-cyan)' }} />
            AgriTech Rover Telemetry Deck
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
            ESP32-C (RC) ──► ESP32-D (FreeRTOS) ──► Arduino Mega (BTS7960 Motors & 6x Sonar)
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button 
            onClick={() => setPumpActive(!pumpActive)}
            className={`cyber-btn ${pumpActive ? '' : 'cyber-btn-secondary'}`}
            style={{ fontSize: '0.75rem', padding: '6px 12px' }}
          >
            {pumpActive ? '💧 Irrigation Pump: ON' : 'Pump: OFF'}
          </button>
          <button 
            onClick={stopMotors}
            className="cyber-btn"
            style={{ fontSize: '0.75rem', padding: '6px 12px', background: 'rgba(255, 23, 68, 0.2)', borderColor: '#ff1744', color: '#ff1744' }}
          >
            ESTOP
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '24px' }}>
        {/* Left: 6x Ultrasonic Obstacle Radar Graphic */}
        <div style={{ background: 'rgba(5, 8, 15, 0.6)', padding: '20px', borderRadius: '12px', border: '1px solid rgba(0, 229, 255, 0.15)', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '12px', textTransform: 'uppercase' }}>
            6x HC-SR04 Sonar Radar Array
          </div>

          <div style={{ 
            position: 'relative', 
            width: '200px', 
            height: '200px', 
            borderRadius: '50%', 
            border: '1px solid rgba(0, 229, 255, 0.3)',
            background: 'radial-gradient(circle, rgba(0, 229, 255, 0.05) 0%, rgba(5, 8, 15, 0.9) 70%)',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            {/* Radar scanner sweep line */}
            <div className="radar-scanner" style={{
              position: 'absolute',
              width: '100px',
              height: '100px',
              top: 0,
              right: 0,
              transformOrigin: 'bottom left',
              background: 'linear-gradient(45deg, rgba(0, 229, 255, 0.3) 0%, transparent 70%)',
              pointerEvents: 'none'
            }}></div>

            {/* Rover Chassis Graphic in Center */}
            <div style={{
              width: '60px',
              height: '80px',
              background: '#1e293b',
              borderRadius: '8px',
              border: '2px solid rgba(0, 229, 255, 0.5)',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              fontSize: '0.65rem',
              fontWeight: 700,
              color: '#00e5ff',
              zIndex: 10
            }}>
              MEGA
              <span style={{ fontSize: '0.55rem', color: 'var(--text-muted)' }}>BTS7960</span>
            </div>

            {/* Front-Center Sonar Node */}
            <div style={{
              position: 'absolute',
              top: '10px',
              background: obstacles.frontCenter < 25 ? '#ff1744' : '#00e676',
              padding: '2px 6px',
              borderRadius: '4px',
              fontSize: '0.65rem',
              fontWeight: 700,
              color: '#080c14'
            }}>
              FC: {obstacles.frontCenter}cm
            </div>

            {/* Front-Left Sonar */}
            <div style={{
              position: 'absolute',
              top: '30px',
              left: '10px',
              background: '#00e5ff',
              padding: '1px 5px',
              borderRadius: '4px',
              fontSize: '0.6rem',
              color: '#080c14'
            }}>
              FL: {obstacles.frontLeft}cm
            </div>

            {/* Front-Right Sonar */}
            <div style={{
              position: 'absolute',
              top: '30px',
              right: '10px',
              background: '#00e5ff',
              padding: '1px 5px',
              borderRadius: '4px',
              fontSize: '0.6rem',
              color: '#080c14'
            }}>
              FR: {obstacles.frontRight}cm
            </div>

            {/* Rear Sonar */}
            <div style={{
              position: 'absolute',
              bottom: '10px',
              background: '#00e5ff',
              padding: '1px 5px',
              borderRadius: '4px',
              fontSize: '0.6rem',
              color: '#080c14'
            }}>
              R: {obstacles.rear}cm
            </div>
          </div>

          {/* Hard Stop indicator */}
          <div style={{ marginTop: '16px' }}>
            {isHardStop ? (
              <span className="badge-status badge-amber" style={{ background: 'rgba(255, 23, 68, 0.2)', color: '#ff1744', border: '1px solid #ff1744' }}>
                🛑 FAILSAFE OVERRIDE: OBSTACLE BLOCKED (&lt;25cm)
              </span>
            ) : (
              <span className="badge-status badge-active">
                ✓ ALL SECTORS CLEAR
              </span>
            )}
          </div>
        </div>

        {/* Middle: Virtual Joystick Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', alignItems: 'center' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            ESP32-C Virtual RC Transmitter
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 60px)', gap: '10px' }}>
            <div></div>
            <button 
              onMouseDown={() => handleDrive(200, 0)} 
              onMouseUp={stopMotors}
              className="cyber-btn" 
              style={{ height: '60px', padding: 0, justifyContent: 'center' }}
            >
              ▲
            </button>
            <div></div>

            <button 
              onMouseDown={() => handleDrive(0, -180)} 
              onMouseUp={stopMotors}
              className="cyber-btn" 
              style={{ height: '60px', padding: 0, justifyContent: 'center' }}
            >
              ◀
            </button>
            <button 
              onClick={stopMotors}
              className="cyber-btn cyber-btn-secondary" 
              style={{ height: '60px', padding: 0, justifyContent: 'center', fontSize: '0.75rem' }}
            >
              STOP
            </button>
            <button 
              onMouseDown={() => handleDrive(0, 180)} 
              onMouseUp={stopMotors}
              className="cyber-btn" 
              style={{ height: '60px', padding: 0, justifyContent: 'center' }}
            >
              ▶
            </button>

            <div></div>
            <button 
              onMouseDown={() => handleDrive(-180, 0)} 
              onMouseUp={stopMotors}
              className="cyber-btn" 
              style={{ height: '60px', padding: 0, justifyContent: 'center' }}
            >
              ▼
            </button>
            <div></div>
          </div>

          <div style={{ width: '100%', display: 'flex', justifyContent: 'space-around', marginTop: '8px' }}>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>THROTTLE</div>
              <div className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{throttle}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>STEERING</div>
              <div className="font-mono" style={{ color: 'var(--accent-cyan)', fontWeight: 600 }}>{steering}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>MOTOR PWM</div>
              <div className="font-mono" style={{ color: '#00e676', fontWeight: 600 }}>{Math.abs(throttle)}</div>
            </div>
          </div>
        </div>

        {/* Right: In-Situ Soil Telemetry & Packet Preview */}
        <div style={{ background: '#050810', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.15)', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
              ESP-NOW 8-Byte Frame (30Hz)
            </span>
            <span className="badge-status badge-active" style={{ fontSize: '0.65rem' }}>CRC16 OK</span>
          </div>

          <div className="font-mono" style={{ fontSize: '0.7rem', background: 'rgba(255,255,255,0.03)', padding: '8px', borderRadius: '4px' }}>
            <div>struct ControlPacket_t &#123;</div>
            <div style={{ paddingLeft: '12px', color: 'var(--accent-cyan)' }}>throttle: {throttle},</div>
            <div style={{ paddingLeft: '12px', color: 'var(--accent-cyan)' }}>steering: {steering},</div>
            <div style={{ paddingLeft: '12px', color: '#00e676' }}>buttons: 0x{pumpActive ? '01' : '00'},</div>
            <div style={{ paddingLeft: '12px', color: 'var(--text-muted)' }}>seq: 148, crc: 0x8DF2</div>
            <div>&#125;</div>
          </div>

          <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.05)', paddingTop: '10px' }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '6px' }}>
              Mega USB Ground Telemetry:
            </div>
            <div className="font-mono" style={{ fontSize: '0.7rem', color: '#94a3b8' }}>
              M:452 | W:0 | AT:28.4°C | ST:23.8°C | H:64%
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
