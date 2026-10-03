import React from 'react';
import { Cpu, Terminal, Shield, Wifi, ArrowDown, ExternalLink, Activity, Layers } from 'lucide-react';
import { SYSTEM_METRICS } from '../data/projects';

export default function Hero() {
  return (
    <section style={{
      position: 'relative',
      padding: '90px 24px 70px 24px',
      maxWidth: '1280px',
      margin: '0 auto',
      textAlign: 'center'
    }}>
      {/* Background glow orb */}
      <div style={{
        position: 'absolute',
        top: '20%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '500px',
        height: '250px',
        background: 'radial-gradient(circle, rgba(0, 229, 255, 0.12) 0%, transparent 70%)',
        pointerEvents: 'none',
        zIndex: -1
      }}></div>

      {/* Top Terminal Badge */}
      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '6px 14px', borderRadius: '9999px', background: 'rgba(0, 229, 255, 0.08)', border: '1px solid rgba(0, 229, 255, 0.25)', marginBottom: '24px' }}>
        <Terminal size={14} style={{ color: 'var(--accent-cyan)' }} />
        <span className="font-mono" style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
          SYSTEM_ARCHITECT // EMBEDDED_IOT_ROBOTICS
        </span>
      </div>

      {/* Primary Headline */}
      <h1 className="font-display" style={{
        fontSize: 'clamp(2.5rem, 5.5vw, 4.5rem)',
        fontWeight: 800,
        letterSpacing: '-0.03em',
        lineHeight: 1.1,
        marginBottom: '20px',
        color: '#ffffff'
      }}>
        Krithik Mahesh
        <span style={{
          display: 'block',
          background: 'linear-gradient(90deg, #00e5ff 0%, #00e676 50%, #b388ff 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          marginTop: '6px'
        }}>
          Embedded Systems & IoT Architect
        </span>
      </h1>

      {/* Bio / Description */}
      <p style={{
        fontSize: 'clamp(1rem, 1.8vw, 1.25rem)',
        color: 'var(--text-secondary)',
        maxWidth: '780px',
        margin: '0 auto 36px auto',
        lineHeight: 1.6
      }}>
        Engineering mission-critical distributed systems from bare-metal microcontrollers to cloud streaming backends. Specializing in high-throughput raw TCP socket ingestion, fail-safe field robotics, sub-millimeter ultrasonic telemetry, and multi-agent AI ecosystems.
      </p>

      {/* Action Buttons */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', flexWrap: 'wrap', marginBottom: '60px' }}>
        <a href="#projects" className="cyber-btn" style={{ padding: '12px 28px', fontSize: '0.95rem' }}>
          Explore Projects <ArrowDown size={16} />
        </a>
        <a href="#simulators" className="cyber-btn cyber-btn-secondary" style={{ padding: '12px 28px', fontSize: '0.95rem' }}>
          <Activity size={16} style={{ color: 'var(--accent-cyan)' }} /> Launch Live Simulators
        </a>
        <a href="https://github.com/isshin-2" target="_blank" rel="noopener noreferrer" className="cyber-btn cyber-btn-secondary" style={{ padding: '12px 24px', fontSize: '0.95rem' }}>
          GitHub Profile <ExternalLink size={16} />
        </a>
      </div>

      {/* Hardware Telemetry Metric Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
        gap: '20px',
        textAlign: 'left'
      }}>
        <div className="glass-panel" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>HARDWARE DEPLOYMENTS</span>
            <Cpu size={18} style={{ color: 'var(--accent-cyan)' }} />
          </div>
          <div className="font-display" style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {SYSTEM_METRICS.activeMcuDeployments}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            ESP32-S3, C3, AVR & Gateway units
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>PACKETS INGESTED</span>
            <Wifi size={18} style={{ color: 'var(--accent-emerald)' }} />
          </div>
          <div className="font-display" style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {SYSTEM_METRICS.packetsIngested}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Port 1024 TCP & ESP-NOW Mesh frames
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>FIELD UPTIME</span>
            <Shield size={18} style={{ color: 'var(--accent-cyan)' }} />
          </div>
          <div className="font-display" style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--accent-emerald)' }}>
            {SYSTEM_METRICS.uptimeRate}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Cold chain pharmaceutical reliability
          </div>
        </div>

        <div className="glass-panel" style={{ padding: '20px 24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>CODEBASE VOLUME</span>
            <Layers size={18} style={{ color: 'var(--accent-purple)' }} />
          </div>
          <div className="font-display" style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            {SYSTEM_METRICS.linesOfFirmware}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            C++, FreeRTOS, Node, React & Python
          </div>
        </div>
      </div>
    </section>
  );
}
