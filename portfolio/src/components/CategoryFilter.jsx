import React from 'react';
import { CATEGORIES, PROJECTS } from '../data/projects';

export default function CategoryFilter({ selectedCategory, setSelectedCategory }) {
  const getCategoryCount = (category) => {
    if (category === "All Projects") return PROJECTS.length;
    return PROJECTS.filter(p => p.category === category).length;
  };

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '10px',
      flexWrap: 'wrap',
      margin: '0 auto 40px auto',
      maxWidth: '1280px'
    }}>
      {CATEGORIES.map(category => {
        const isSelected = selectedCategory === category;
        const count = getCategoryCount(category);

        return (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`cyber-btn ${isSelected ? '' : 'cyber-btn-secondary'}`}
            style={{
              padding: '8px 18px',
              borderRadius: '24px',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >
            <span>{category}</span>
            <span style={{
              background: isSelected ? 'var(--accent-cyan)' : 'rgba(255, 255, 255, 0.1)',
              color: isSelected ? '#080c14' : 'var(--text-secondary)',
              padding: '1px 7px',
              borderRadius: '12px',
              fontSize: '0.72rem',
              fontWeight: 700
            }}>
              {count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
