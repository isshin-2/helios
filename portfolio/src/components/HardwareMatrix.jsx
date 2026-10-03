import React from 'react';
import { HARDWARE_SKILLS } from '../data/projects';
import { Cpu, Radio, Server, CheckCircle2 } from 'lucide-react';

export default function HardwareMatrix() {
  const getCategoryIcon = (category) => {
    if (category.includes('Microcontrollers')) return <Cpu size={18} style={{ color: 'var(--accent-cyan)' }} />;
    if (category.includes('Protocols')) return <Radio size={18} style={{ color: 'var(--accent-emerald)' }} />;
    return <Server size={18} style={{ color: 'var(--accent-purple)' }} />;
  };

  return (
    <section id="matrix" style={{ padding: '80px 24px', maxWidth: '1280px', margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: '50px' }}>
        <div className="badge-status badge-cyan" style={{ marginBottom: '12px' }}>
          <Cpu size={14} /> Architecture & Hardware Core
        </div>
        <h2 className="font-display" style={{ fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '12px' }}>
          Hardware & Systems Matrix
        </h2>
        <p style={{ color: 'var(--text-secondary)', maxWidth: '640px', margin: '0 auto', fontSize: '1.05rem' }}>
          Deep engineering experience spanning silicon registers, industrial noise-immune differential buses, and high-concurrency cloud ingestion engines.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
        {HARDWARE_SKILLS.map((sec, idx) => (
          <div key={idx} className="glass-panel" style={{ padding: '28px', display: 'flex', flexDirection: 'column' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px', borderBottom: '1px solid rgba(0, 229, 255, 0.15)', paddingBottom: '14px' }}>
              {getCategoryIcon(sec.category)}
              <h3 className="font-display" style={{ fontSize: '1.25rem', fontWeight: 700, color: '#ffffff' }}>
                {sec.category}
              </h3>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>
              {sec.items.map((item, itemIdx) => (
                <div key={itemIdx} style={{
                  background: 'rgba(5, 8, 15, 0.4)',
                  padding: '12px 14px',
                  borderRadius: '8px',
                  border: '1px solid rgba(255, 255, 255, 0.04)',
                  transition: 'border-color 0.2s, transform 0.2s'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                    <span className="font-mono" style={{ fontSize: '0.88rem', fontWeight: 600, color: '#ffffff' }}>
                      {item.name}
                    </span>
                    <span className="badge-status badge-active" style={{ fontSize: '0.68rem', padding: '2px 8px' }}>
                      {item.level}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                    {item.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
