import React from 'react';
import { Shield, Users, RefreshCw } from 'lucide-react';

export default function Navbar({ currentUser, demoUsers, onSwitchUser, currentTeam, teams, onSelectTeam }) {
  return (
    <header className="navbar">
      <div className="brand-section">
        <div className="brand-logo">N</div>
        <div>
          <div className="brand-title">
            Newtonite Ops
            <span className="brand-badge">Full-Stack Challenge</span>
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)' }}>
            Operations Under Pressure
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {/* Team Selector */}
        {teams && teams.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase', fontWeight: 600 }}>
              Team:
            </span>
            <select
              className="role-select"
              value={currentTeam?.id || ''}
              onChange={(e) => {
                const selected = teams.find((t) => t.id === Number(e.target.value));
                if (selected) onSelectTeam(selected);
              }}
            >
              <option value="">All My Teams</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Demo Reviewer Role Switcher */}
        <div className="role-switcher-bar">
          <Shield size={14} color="#3b82f6" />
          <span className="role-switcher-label">Reviewer Role:</span>
          <select
            className="role-select"
            value={currentUser?.email || ''}
            onChange={(e) => onSwitchUser(e.target.value)}
          >
            {demoUsers.map((u) => {
              const rolesSummary = u.roles.map((r) => `${r.role} (${r.team.split(' ')[0]})`).join(', ');
              return (
                <option key={u.id} value={u.email}>
                  {u.name} — {rolesSummary || 'External / No Teams'}
                </option>
              );
            })}
          </select>
        </div>
      </div>
    </header>
  );
}
