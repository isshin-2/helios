import React from 'react';
import { ExternalLink, Github, Cpu, GitFork, Star, ArrowUpRight, Layers } from 'lucide-react';

export default function ProjectCard({ project, onInspect }) {
  return (
    <div className="glass-card-interactive" style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between',
      padding: '28px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Top Bar: Category, Status, Version */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
          <span className="badge-status badge-cyan">{project.category}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`badge-status ${project.status.includes('Active') || project.status.includes('Production') ? 'badge-active' : 'badge-amber'}`}>
              <span className="pulse-indicator" style={{ 
                backgroundColor: project.status.includes('Active') || project.status.includes('Production') ? '#00e676' : '#ffb300' 
              }}></span>
              {project.status}
            </span>
            <span className="font-mono" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              {project.version}
            </span>
          </div>
        </div>

        {/* Project Title */}
        <h3 className="font-display" style={{
          fontSize: '1.45rem',
          fontWeight: 700,
          color: '#ffffff',
          marginBottom: '6px',
          letterSpacing: '-0.01em'
        }}>
          {project.title}
        </h3>

        {/* Tagline */}
        <p style={{
          fontSize: '0.85rem',
          color: 'var(--accent-cyan)',
          fontWeight: 500,
          marginBottom: '14px',
          lineHeight: 1.4
        }}>
          {project.tagline}
        </p>

        {/* Short Description */}
        <p style={{
          fontSize: '0.88rem',
          color: 'var(--text-secondary)',
          lineHeight: 1.6,
          marginBottom: '20px'
        }}>
          {project.description}
        </p>

        {/* Quick Highlights Preview */}
        <div style={{ marginBottom: '20px', background: 'rgba(5, 8, 15, 0.4)', padding: '12px 14px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.04)' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '6px' }}>
            Key Hardware / System Innovation
          </div>
          <div style={{ fontSize: '0.82rem', color: '#e2e8f0', display: 'flex', alignItems: 'flex-start', gap: '8px' }}>
            <div style={{ width: '5px', height: '5px', borderRadius: '50%', backgroundColor: 'var(--accent-cyan)', marginTop: '7px', flexShrink: 0 }}></div>
            <span>{project.highlights[0]}</span>
          </div>
        </div>

        {/* Tech Stack Pills */}
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
          marginBottom: '24px'
        }}>
          {project.tech.slice(0, 6).map((t, idx) => (
            <span key={idx} className="font-mono" style={{
              fontSize: '0.72rem',
              backgroundColor: 'rgba(0, 229, 255, 0.06)',
              border: '1px solid rgba(0, 229, 255, 0.2)',
              color: '#cbd5e1',
              padding: '3px 8px',
              borderRadius: '4px'
            }}>
              {t}
            </span>
          ))}
          {project.tech.length > 6 && (
            <span className="font-mono" style={{
              fontSize: '0.72rem',
              color: 'var(--accent-cyan)',
              padding: '3px 6px'
            }}>
              +{project.tech.length - 6} more
            </span>
          )}
        </div>
      </div>

      {/* Card Footer: Stars/Forks & Actions */}
      <div style={{
        borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        paddingTop: '16px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            <Star size={13} style={{ color: 'var(--accent-amber)' }} /> {project.stars}
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
            <GitFork size={13} /> {project.forks}
          </span>
        </div>

        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            onClick={() => onInspect(project)}
            className="cyber-btn cyber-btn-secondary"
            style={{ padding: '6px 12px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Layers size={13} /> Specs
          </button>
          <a
            href={project.github}
            target="_blank"
            rel="noopener noreferrer"
            className="cyber-btn"
            style={{ padding: '6px 12px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '4px' }}
          >
            <Github size={13} /> Repo <ArrowUpRight size={13} />
          </a>
        </div>
      </div>
    </div>
  );
}
