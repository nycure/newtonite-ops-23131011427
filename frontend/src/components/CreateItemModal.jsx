import React, { useState } from 'react';
import { X, Plus, Key } from 'lucide-react';
import { generateUUID } from '../api/client';

export default function CreateItemModal({ teams, onClose, onCreate }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [teamId, setTeamId] = useState(teams[0]?.id || 1);
  const [priority, setPriority] = useState('medium');
  const [type, setType] = useState('incident');
  const [idempotencyKey, setIdempotencyKey] = useState(generateUUID());
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) return;

    setLoading(true);
    try {
      await onCreate(
        {
          title: title.trim(),
          description: description.trim() || null,
          team_id: Number(teamId),
          priority,
          type,
        },
        idempotencyKey
      );
      onClose();
    } catch (err) {
      alert(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" style={{ maxWidth: '580px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ fontSize: '1.2rem', color: '#fff' }}>Create Operational Work Item</h3>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.35rem', display: 'block' }}>
                Item Title *
              </label>
              <input
                className="search-input"
                style={{ paddingLeft: '1rem' }}
                placeholder="e.g. Critical: Payment Gateway GatewayTimeout Spike"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.35rem', display: 'block' }}>
                Detailed Description
              </label>
              <textarea
                className="search-input"
                style={{ paddingLeft: '1rem', minHeight: '90px' }}
                placeholder="Observed behavior, reproduction steps, affected systems..."
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.35rem', display: 'block' }}>
                  Target Team *
                </label>
                <select
                  className="filter-select"
                  style={{ width: '100%' }}
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                >
                  {teams.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.35rem', display: 'block' }}>
                  Item Type *
                </label>
                <select
                  className="filter-select"
                  style={{ width: '100%' }}
                  value={type}
                  onChange={(e) => setType(e.target.value)}
                >
                  <option value="incident">Incident</option>
                  <option value="customer_issue">Customer Issue</option>
                  <option value="payment">Payment</option>
                  <option value="compliance">Compliance</option>
                  <option value="task">Task</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-dim)', marginBottom: '0.35rem', display: 'block' }}>
                Priority Level *
              </label>
              <select
                className="filter-select"
                style={{ width: '100%' }}
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>

            {/* Idempotency Demonstration */}
            <div
              style={{
                background: 'rgba(255, 255, 255, 0.02)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-sm)',
                padding: '0.65rem 0.85rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.6rem',
              }}
            >
              <Key size={16} color="#60a5fa" />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.725rem', color: 'var(--text-dim)' }}>
                  Idempotency-Key Header (Prevents duplicate creation on retry):
                </div>
                <div style={{ fontFamily: 'JetBrains Mono', fontSize: '0.75rem', color: '#93c5fd' }}>
                  {idempotencyKey}
                </div>
              </div>
              <button
                type="button"
                className="btn-secondary"
                style={{ padding: '0.2rem 0.5rem', fontSize: '0.7rem' }}
                onClick={() => setIdempotencyKey(generateUUID())}
              >
                Regenerate
              </button>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={loading}>
              <Plus size={16} /> Create Work Item
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
