import React, { useState, useEffect } from 'react';
import { Terminal, Shield, Github, Search, Radio, Cpu, ExternalLink } from 'lucide-react';

export default function Header({ searchQuery, setSearchQuery }) {
  const [time, setTime] = useState('');

  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setTime(now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC');
    };
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header style={{
      position: 'sticky',
      top: 0,
      zIndex: 100,
      backgroundColor: 'rgba(8, 12, 20, 0.88)',
      backdropFilter: 'blur(16px)',
      WebkitBackdropFilter: 'blur(16px)',
      borderBottom: '1px solid rgba(0, 229, 255, 0.18)',
      padding: '12px 24px'
    }}>
      <div style={{
        maxWidth: '1360px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '16px'
      }}>
        {/* Logo & Operational Status */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <a href="#" style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '38px',
              height: '38px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.25) 0%, rgba(13, 20, 34, 0.9) 100%)',
              border: '1px solid var(--accent-cyan)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 0 15px rgba(0, 229, 255, 0.25)'
            }}>
              <Cpu size={20} style={{ color: 'var(--accent-cyan)' }} />
            </div>
            <div>
              <div className="font-display" style={{ fontWeight: 800, fontSize: '1.1rem', letterSpacing: '-0.01em', color: '#ffffff' }}>
                KRITHIK MAHESH
              </div>
              <div className="font-mono" style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', letterSpacing: '0.08em' }}>
                @isshin-2 // HELIOS CORE
              </div>
            </div>
          </a>

          <div className="badge-status badge-active" style={{ fontSize: '0.7rem' }}>
            <span className="pulse-indicator"></span>
            ALL SYSTEMS OPERATIONAL
          </div>
        </div>

        {/* Live Search Bar */}
        <div style={{ position: 'relative', flex: '1 1 260px', maxWidth: '360px' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search projects, MCUs, protocols..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              width: '100%',
              backgroundColor: 'rgba(13, 20, 34, 0.8)',
              border: '1px solid rgba(0, 229, 255, 0.25)',
              borderRadius: '8px',
              padding: '8px 12px 8px 36px',
              color: '#ffffff',
              fontSize: '0.85rem',
              outline: 'none',
              fontFamily: 'var(--font-sans)',
              transition: 'border-color 0.2s, box-shadow 0.2s'
            }}
            onFocus={(e) => {
              e.target.style.borderColor = 'var(--accent-cyan)';
              e.target.style.boxShadow = '0 0 12px rgba(0, 229, 255, 0.25)';
            }}
            onBlur={(e) => {
              e.target.style.borderColor = 'rgba(0, 229, 255, 0.25)';
              e.target.style.boxShadow = 'none';
            }}
          />
        </div>

        {/* Quick Nav & GitHub Link */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div className="font-mono" style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'none', lgDisplay: 'block' }}>
            {time}
          </div>
          <nav style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <a href="#projects" className="cyber-btn cyber-btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
              Projects
            </a>
            <a href="#simulators" className="cyber-btn cyber-btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
              Simulators
            </a>
            <a href="#matrix" className="cyber-btn cyber-btn-secondary" style={{ padding: '6px 12px', fontSize: '0.8rem' }}>
              Hardware Matrix
            </a>
            <a
              href="https://github.com/isshin-2"
              target="_blank"
              rel="noopener noreferrer"
              className="cyber-btn"
              style={{ padding: '6px 14px', fontSize: '0.8rem' }}
            >
              <Github size={16} /> GitHub
            </a>
          </nav>
        </div>
      </div>
    </header>
  );
}
