import React from 'react';
import { UserCheck, Clock, AlertCircle, CheckCircle2, ShieldAlert } from 'lucide-react';

export default function WorkItemCard({ item, onClick, onClaim, currentUserId }) {
  const isUrgent = item.priority === 'urgent' && item.status === 'open';
  const isAwaitingApproval = item.status === 'awaiting_approval';

  const cardClasses = [
    'work-item-card',
    isUrgent ? 'urgent-highlight' : '',
    isAwaitingApproval ? 'approval-highlight' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={cardClasses} onClick={onClick}>
      <div className="item-left">
        <span className="item-id-badge">#{item.id}</span>
        <div className="item-details">
          <h3>
            {item.title}
            <span className={`badge-pill status-${item.status}`}>
              {item.status.replace('_', ' ')}
            </span>
            <span className={`badge-pill priority-${item.priority}`}>
              {item.priority}
            </span>
          </h3>

          <div className="item-meta">
            <span className="type-pill">{item.type.replace('_', ' ')}</span>
            <span>Team: <strong style={{ color: '#cbd5e1' }}>{item.team_name}</strong></span>
            <span>
              {item.assignee_id ? (
                <>
                  <UserCheck size={13} color="#60a5fa" />
                  Assigned to: <strong style={{ color: item.assignee_id === currentUserId ? '#60a5fa' : '#cbd5e1' }}>
                    {item.assignee_id === currentUserId ? 'You' : item.assignee_name}
                  </strong>
                </>
              ) : (
                <strong style={{ color: '#fb7185' }}>Unassigned</strong>
              )}
            </span>
            <span>
              <Clock size={13} />
              {new Date(item.created_at).toLocaleDateString()}
            </span>
            <span className="version-pill">v{item.version}</span>
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }} onClick={(e) => e.stopPropagation()}>
        {!item.assignee_id && (
          <button
            className="btn-primary"
            style={{ padding: '0.4rem 0.85rem', fontSize: '0.8rem' }}
            onClick={() => onClaim(item.id)}
          >
            Claim Item
          </button>
        )}
      </div>
    </div>
  );
}
