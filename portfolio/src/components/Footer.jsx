import React, { useState } from 'react';
import { Github, Terminal, Cpu, Heart, Check, Copy } from 'lucide-react';
import { SYSTEM_METRICS } from '../data/projects';

export default function Footer() {
  const [copied, setCopied] = useState(false);

  const copyGitHub = () => {
    navigator.clipboard.writeText('https://github.com/isshin-2');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <footer style={{
      borderTop: '1px solid rgba(0, 229, 255, 0.15)',
      backgroundColor: '#050810',
      padding: '60px 24px 40px 24px',
      position: 'relative'
    }}>
      <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: '40px',
          marginBottom: '50px'
        }}>
          {/* Column 1: Identity */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                background: 'rgba(0, 229, 255, 0.1)',
                border: '1px solid var(--accent-cyan)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Cpu size={18} style={{ color: 'var(--accent-cyan)' }} />
              </div>
              <span className="font-display" style={{ fontWeight: 800, fontSize: '1.2rem', color: '#ffffff' }}>
                {SYSTEM_METRICS.fullName}
              </span>
            </div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', lineHeight: 1.6, marginBottom: '16px' }}>
              {SYSTEM_METRICS.title}. Specializing in industrial telemetry, agricultural robotics, and autonomous AI routing swarms.
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button onClick={copyGitHub} className="cyber-btn cyber-btn-secondary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}>
                {copied ? <Check size={14} style={{ color: '#00e676' }} /> : <Copy size={14} />}
                {copied ? 'Copied URL!' : 'Copy GitHub URL'}
              </button>
            </div>
          </div>

          {/* Column 2: Quick Navigation */}
          <div>
            <h4 style={{ fontSize: '0.85rem', color: '#ffffff', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
              Core Infrastructure
            </h4>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '0.85rem' }}>
              <li><a href="#projects" style={{ color: 'var(--text-secondary)', textDecoration: 'none', transition: 'color 0.2s' }}>Projects Showcase</a></li>
              <li><a href="#simulators" style={{ color: 'var(--text-secondary)', textDecoration: 'none', transition: 'color 0.2s' }}>Hardware Simulators</a></li>
              <li><a href="#matrix" style={{ color: 'var(--text-secondary)', textDecoration: 'none', transition: 'color 0.2s' }}>MCU & Protocol Matrix</a></li>
              <li><a href="https://github.com/isshin-2" target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-cyan)', textDecoration: 'none' }}>GitHub Profile (@isshin-2)</a></li>
            </ul>
          </div>

          {/* Column 3: System Status & Verification */}
          <div>
            <h4 style={{ fontSize: '0.85rem', color: '#ffffff', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '16px' }}>
              Host Telemetry
            </h4>
            <div className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div>ENGINE: <span style={{ color: 'var(--accent-cyan)' }}>HELIOS v3.0 / Vite 6</span></div>
              <div>INGEST PORT: <span style={{ color: 'var(--accent-emerald)' }}>TCP :1024 / ESP-NOW</span></div>
              <div>DISPLAY DRIVER: <span style={{ color: '#ffffff' }}>ST7789 240x320 IPS</span></div>
              <div>FAILSAFE WATCHDOG: <span style={{ color: 'var(--accent-emerald)' }}>ACTIVE (300ms)</span></div>
            </div>
          </div>
        </div>

        {/* Bottom Bar */}
        <div style={{
          borderTop: '1px solid rgba(255, 255, 255, 0.05)',
          paddingTop: '24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          fontSize: '0.8rem',
          color: 'var(--text-muted)'
        }}>
          <div>
            © {new Date().getFullYear()} Krithik Mahesh (@isshin-2). Built for autonomous engineering & high-reliability field deployments.
          </div>
          <div className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
            HELIOS_PORTFOLIO_RELEASE_OK
          </div>
        </div>
      </div>
    </footer>
  );
}
