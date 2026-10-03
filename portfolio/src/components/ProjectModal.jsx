import React, { useState, useEffect } from 'react';
import { X, ExternalLink, Github, Cpu, GitFork, Star, Activity, Layers, Radio, Shield, Terminal } from 'lucide-react';

export default function ProjectModal({ project, onClose }) {
  const [activeTab, setActiveTab] = useState('overview');

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!project) return null;

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(5, 8, 15, 0.85)',
      backdropFilter: 'blur(12px)',
      WebkitBackdropFilter: 'blur(12px)',
      zIndex: 1000,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '24px'
    }} onClick={onClose}>
      <div 
        className="glass-panel"
        style={{
          width: '100%',
          maxWidth: '900px',
          maxHeight: '90vh',
          overflowY: 'auto',
          backgroundColor: '#0a0f1d',
          borderColor: 'var(--accent-cyan)',
          padding: '32px',
          position: 'relative'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '20px',
            right: '20px',
            background: 'rgba(255, 255, 255, 0.05)',
            border: '1px solid rgba(255, 255, 255, 0.1)',
            color: 'var(--text-secondary)',
            borderRadius: '50%',
            width: '36px',
            height: '36px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: 'pointer',
            transition: 'all 0.2s'
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#fff'; e.currentTarget.style.borderColor = 'var(--accent-cyan)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.1)'; }}
        >
          <X size={20} />
        </button>

        {/* Modal Header */}
        <div style={{ marginBottom: '24px', paddingRight: '40px' }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap' }}>
            <span className="badge-status badge-cyan">{project.category}</span>
            <span className="badge-status badge-active">{project.status}</span>
            <span className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{project.version}</span>
          </div>

          <h2 className="font-display" style={{ fontSize: '1.9rem', fontWeight: 800, color: '#ffffff', marginBottom: '6px' }}>
            {project.title}
          </h2>
          <p style={{ color: 'var(--accent-cyan)', fontSize: '0.95rem', fontWeight: 500 }}>
            {project.tagline}
          </p>
        </div>

        {/* Modal Tabs */}
        <div style={{
          display: 'flex',
          gap: '8px',
          borderBottom: '1px solid rgba(0, 229, 255, 0.15)',
          marginBottom: '24px',
          overflowX: 'auto',
          paddingBottom: '8px'
        }}>
          {[
            { id: 'overview', label: 'Overview & Highlights', icon: Activity },
            { id: 'architecture', label: 'Architecture & Nodes', icon: Layers },
            { id: 'pinouts', label: 'Hardware Pinouts', icon: Cpu },
            { id: 'protocols', label: 'Protocol Specs', icon: Terminal }
          ].map(tab => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`cyber-btn ${isActive ? '' : 'cyber-btn-secondary'}`}
                style={{ padding: '8px 14px', fontSize: '0.8rem', borderRadius: '6px' }}
              >
                <Icon size={14} /> {tab.label}
              </button>
            );
          })}
        </div>

        {/* Modal Tab Content */}
        <div style={{ minHeight: '260px' }}>
          {activeTab === 'overview' && (
            <div>
              <p style={{ color: 'var(--text-secondary)', lineHeight: 1.7, fontSize: '0.95rem', marginBottom: '20px' }}>
                {project.description}
              </p>
              
              <h4 style={{ fontSize: '0.9rem', color: '#ffffff', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Technical Innovations & Fail-Safes
              </h4>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {project.highlights.map((hl, i) => (
                  <li key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: 'var(--accent-cyan)', marginTop: '8px', flexShrink: 0 }}></div>
                    <span>{hl}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {activeTab === 'architecture' && (
            <div>
              <div style={{ background: '#050812', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.2)', marginBottom: '20px' }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginBottom: '8px', fontFamily: 'var(--font-mono)' }}>
                  DATA & TELEMETRY FLOW:
                </div>
                <div className="font-mono" style={{ fontSize: '0.85rem', color: '#ffffff' }}>
                  {project.architecture.flow}
                </div>
              </div>

              <h4 style={{ fontSize: '0.9rem', color: '#ffffff', marginBottom: '12px', textTransform: 'uppercase' }}>
                Node Topology Breakdown
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {project.architecture.nodes.map((node, i) => (
                  <div key={i} style={{ background: 'rgba(255, 255, 255, 0.02)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                    <div className="font-mono" style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-cyan)', marginBottom: '4px' }}>
                      {node.name}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {node.role}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === 'pinouts' && (
            <div>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(0, 229, 255, 0.2)', color: 'var(--accent-cyan)' }}>
                    <th style={{ padding: '10px 12px' }}>Interface / Pin</th>
                    <th style={{ padding: '10px 12px' }}>Function</th>
                    <th style={{ padding: '10px 12px' }}>Implementation Note</th>
                  </tr>
                </thead>
                <tbody>
                  {project.pinouts.map((p, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <td className="font-mono" style={{ padding: '10px 12px', color: '#ffffff', fontWeight: 600 }}>{p.pin}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{p.func}</td>
                      <td style={{ padding: '10px 12px', color: 'var(--text-muted)' }}>{p.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'protocols' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {project.protocols.map((proto, i) => (
                <div key={i} style={{ background: '#050812', padding: '16px', borderRadius: '8px', border: '1px solid rgba(0, 229, 255, 0.15)' }}>
                  <div className="font-mono" style={{ fontSize: '0.85rem', color: 'var(--accent-cyan)', fontWeight: 600, marginBottom: '6px' }}>
                    {proto.name}
                  </div>
                  <div className="font-mono" style={{ fontSize: '0.78rem', color: '#cbd5e1', background: 'rgba(0, 0, 0, 0.4)', padding: '8px', borderRadius: '4px' }}>
                    {proto.spec}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div style={{
          marginTop: '32px',
          paddingTop: '20px',
          borderTop: '1px solid rgba(255, 255, 255, 0.08)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px'
        }}>
          <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <Star size={14} style={{ color: 'var(--accent-amber)' }} /> {project.stars} stars
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <GitFork size={14} /> {project.forks} forks
            </span>
          </div>

          <div style={{ display: 'flex', gap: '12px' }}>
            <button onClick={onClose} className="cyber-btn cyber-btn-secondary" style={{ padding: '8px 16px', fontSize: '0.85rem' }}>
              Close
            </button>
            <a
              href={project.github}
              target="_blank"
              rel="noopener noreferrer"
              className="cyber-btn"
              style={{ padding: '8px 18px', fontSize: '0.85rem' }}
            >
              <Github size={16} /> Open Repository <ExternalLink size={14} />
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
