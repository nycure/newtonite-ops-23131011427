import React from 'react';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';

export default function ConflictBanner({ conflict, onDismiss, onReload }) {
  if (!conflict) return null;

  return (
    <div className="conflict-banner">
      <div className="conflict-content">
        <AlertTriangle className="conflict-icon" size={24} />
        <div className="conflict-text">
          <h4>Concurrency Conflict Detected (HTTP 409)</h4>
          <p>
            {typeof conflict === 'string'
              ? conflict
              : conflict.message || 'This item was updated or claimed by another user in parallel.'}
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        {onReload && (
          <button className="btn-secondary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }} onClick={onReload}>
            <RefreshCw size={14} />
            Reload Latest State
          </button>
        )}
        <button
          onClick={onDismiss}
          style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: '0.2rem' }}
        >
          <X size={18} />
        </button>
      </div>
    </div>
  );
}
