import React, { useState, useMemo } from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import CategoryFilter from './components/CategoryFilter';
import ProjectCard from './components/ProjectCard';
import ProjectModal from './components/ProjectModal';
import LiveSimulators from './components/LiveSimulators';
import HardwareMatrix from './components/HardwareMatrix';
import Footer from './components/Footer';
import { PROJECTS } from './data/projects';
import { Layers, SearchX } from 'lucide-react';

export default function App() {
  const [selectedCategory, setSelectedCategory] = useState("All Projects");
  const [searchQuery, setSearchQuery] = useState("");
  const [inspectedProject, setInspectedProject] = useState(null);

  // Filter projects based on category and search query
  const filteredProjects = useMemo(() => {
    return PROJECTS.filter(project => {
      const matchesCategory = selectedCategory === "All Projects" || project.category === selectedCategory;
      if (!matchesCategory) return false;

      if (!searchQuery.trim()) return true;

      const q = searchQuery.toLowerCase();
      const matchTitle = project.title.toLowerCase().includes(q);
      const matchTagline = project.tagline.toLowerCase().includes(q);
      const matchDesc = project.description.toLowerCase().includes(q);
      const matchTech = project.tech.some(t => t.toLowerCase().includes(q));
      const matchNodes = project.architecture?.nodes?.some(n => n.name.toLowerCase().includes(q) || n.role.toLowerCase().includes(q));

      return matchTitle || matchTagline || matchDesc || matchTech || matchNodes;
    });
  }, [selectedCategory, searchQuery]);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Header searchQuery={searchQuery} setSearchQuery={setSearchQuery} />

      <main style={{ flex: 1 }}>
        <Hero />

        {/* Projects Section */}
        <section id="projects" style={{ padding: '40px 24px 80px 24px', maxWidth: '1360px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '32px' }}>
            <div className="badge-status badge-cyan" style={{ marginBottom: '12px' }}>
              <Layers size={14} /> Systems & Repositories
            </div>
            <h2 className="font-display" style={{ fontSize: '2.5rem', fontWeight: 700, letterSpacing: '-0.02em', marginBottom: '12px' }}>
              Engineered Deployments
            </h2>
            <p style={{ color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto', fontSize: '1rem' }}>
              Field-tested agricultural robotics, commercial wireless liquid telemetry, enterprise cold chain clusters, and multi-agent AI ecosystems.
            </p>
          </div>

          <CategoryFilter 
            selectedCategory={selectedCategory} 
            setSelectedCategory={setSelectedCategory} 
          />

          {/* Results count & clear search feedback */}
          {searchQuery && (
            <div style={{ textAlign: 'center', marginBottom: '24px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              Found <strong style={{ color: 'var(--accent-cyan)' }}>{filteredProjects.length}</strong> project{filteredProjects.length === 1 ? '' : 's'} matching "{searchQuery}"
              <button 
                onClick={() => setSearchQuery("")} 
                style={{ marginLeft: '12px', background: 'none', border: 'none', color: 'var(--accent-cyan)', cursor: 'pointer', textDecoration: 'underline', fontSize: '0.85rem' }}
              >
                Clear filter
              </button>
            </div>
          )}

          {/* Project Grid */}
          {filteredProjects.length > 0 ? (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))',
              gap: '28px'
            }}>
              {filteredProjects.map(project => (
                <ProjectCard 
                  key={project.id} 
                  project={project} 
                  onInspect={(p) => setInspectedProject(p)} 
                />
              ))}
            </div>
          ) : (
            <div className="glass-panel" style={{ textAlign: 'center', padding: '60px 20px', maxWidth: '500px', margin: '0 auto' }}>
              <SearchX size={48} style={{ color: 'var(--text-muted)', margin: '0 auto 16px auto' }} />
              <h3 style={{ fontSize: '1.2rem', marginBottom: '8px', color: '#ffffff' }}>No matching projects found</h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
                Try adjusting your search query or switching category tabs.
              </p>
              <button onClick={() => { setSearchQuery(""); setSelectedCategory("All Projects"); }} className="cyber-btn">
                Reset All Filters
              </button>
            </div>
          )}
        </section>

        {/* Live Hardware Simulators */}
        <LiveSimulators />

        {/* Hardware & Systems Matrix */}
        <HardwareMatrix />
      </main>

      {/* Deep Inspection Modal */}
      {inspectedProject && (
        <ProjectModal 
          project={inspectedProject} 
          onClose={() => setInspectedProject(null)} 
        />
      )}

      <Footer />
    </div>
  );
}
