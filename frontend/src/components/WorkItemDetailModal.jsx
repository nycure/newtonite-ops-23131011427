import React, { useState } from 'react';
import { X, CheckCircle2, UserCheck, Clock, MessageSquare, Send, ArrowRight, ShieldCheck, Edit3 } from 'lucide-react';
import ConflictBanner from './ConflictBanner';

export default function WorkItemDetailModal({
  item,
  currentUser,
  onClose,
  onClaim,
  onTransition,
  onUpdate,
  onAddComment,
  onReload,
}) {
  const [commentText, setCommentText] = useState('');
  const [transitionComment, setTransitionComment] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const [editDesc, setEditDesc] = useState(item.description || '');
  const [editPriority, setEditPriority] = useState(item.priority);
  const [conflictError, setConflictError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Check user role on the team
  const userTeamMembership = currentUser?.memberships?.find((m) => m.team_id === item.team_id);
  const userRole = userTeamMembership?.role || 'Viewer';
  const isLeadOrAdmin = userRole === 'Lead' || userRole === 'Admin';
  const isViewer = userRole === 'Viewer';

  const handleClaim = async () => {
    setActionLoading(true);
    setConflictError(null);
    try {
      await onClaim(item.id);
    } catch (err) {
      if (err.status === 409) {
        setConflictError(err.data?.detail || 'Concurrent collision: Item was already claimed!');
      } else {
        alert(err.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleTransition = async (targetStatus) => {
    setActionLoading(true);
    setConflictError(null);
    try {
      await onTransition(item.id, targetStatus, transitionComment);
      setTransitionComment('');
    } catch (err) {
      if (err.status === 409) {
        setConflictError(err.data?.detail || 'Status transition conflict: Item was modified!');
      } else {
        alert(err.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveEdit = async () => {
    setActionLoading(true);
    setConflictError(null);
    try {
      await onUpdate(item.id, {
        title: editTitle,
        description: editDesc,
        priority: editPriority,
        version: item.version, // Required for optimistic locking check!
      });
      setIsEditing(false);
    } catch (err) {
      if (err.status === 409) {
        setConflictError(err.data?.detail || 'Optimistic locking conflict: Item was updated by another user!');
      } else {
        alert(err.message);
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendComment = async (e) => {
    e.preventDefault();
    if (!commentText.trim()) return;
    try {
      await onAddComment(item.id, commentText);
      setCommentText('');
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span className="item-id-badge">#{item.id}</span>
            <span className={`badge-pill status-${item.status}`}>{item.status.replace('_', ' ')}</span>
            <span className={`badge-pill priority-${item.priority}`}>{item.priority}</span>
            <span className="version-pill">Version {item.version}</span>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {conflictError && (
            <ConflictBanner
              conflict={conflictError}
              onDismiss={() => setConflictError(null)}
              onReload={() => onReload(item.id)}
            />
          )}

          {/* Title and Editing */}
          {isEditing ? (
            <div style={{ marginBottom: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <input
                className="search-input"
                style={{ paddingLeft: '1rem' }}
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                placeholder="Work item title"
              />
              <textarea
                className="search-input"
                style={{ paddingLeft: '1rem', minHeight: '80px' }}
                value={editDesc}
                onChange={(e) => setEditDesc(e.target.value)}
                placeholder="Detailed description"
              />
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <select
                  className="filter-select"
                  value={editPriority}
                  onChange={(e) => setEditPriority(e.target.value)}
                >
                  <option value="low">Low Priority</option>
                  <option value="medium">Medium Priority</option>
                  <option value="high">High Priority</option>
                  <option value="urgent">Urgent Priority</option>
                </select>
                <button className="btn-primary" onClick={handleSaveEdit} disabled={actionLoading}>
                  Save Changes (v{item.version})
                </button>
                <button className="btn-secondary" onClick={() => setIsEditing(false)}>
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <h2 style={{ fontSize: '1.4rem', color: '#fff', marginBottom: '0.4rem' }}>{item.title}</h2>
                {!isViewer && (
                  <button
                    className="btn-secondary"
                    style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                    onClick={() => setIsEditing(true)}
                  >
                    <Edit3 size={14} /> Edit
                  </button>
                )}
              </div>
              <p style={{ color: '#cbd5e1', fontSize: '0.95rem', lineHeight: '1.6' }}>
                {item.description || 'No description provided.'}
              </p>
            </div>
          )}

          {/* Metadata Grid */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '0.85rem',
              background: 'rgba(255, 255, 255, 0.02)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Team</div>
              <div style={{ fontSize: '0.9rem', color: '#fff', fontWeight: 600 }}>{item.team_name}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Assignee</div>
              <div style={{ fontSize: '0.9rem', color: item.assignee_id ? '#60a5fa' : '#fb7185', fontWeight: 600 }}>
                {item.assignee_id ? item.assignee_name : 'Unassigned'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Created By</div>
              <div style={{ fontSize: '0.9rem', color: '#fff' }}>{item.creator_name || 'System'}</div>
            </div>
            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-dim)', textTransform: 'uppercase' }}>Your Team Role</div>
              <div style={{ fontSize: '0.9rem', color: isLeadOrAdmin ? '#fbbf24' : '#cbd5e1', fontWeight: 600 }}>
                {userRole}
              </div>
            </div>
          </div>

          {/* Workflow Action Bar */}
          {!isViewer && (
            <div
              style={{
                background: 'rgba(59, 130, 246, 0.06)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                borderRadius: 'var(--radius-md)',
                padding: '1rem',
                marginBottom: '1.5rem',
              }}
            >
              <div style={{ fontSize: '0.8rem', fontWeight: 600, color: '#93c5fd', marginBottom: '0.6rem' }}>
                Workflow Transitions & Actions:
              </div>

              <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap', alignItems: 'center' }}>
                {!item.assignee_id && (
                  <button className="btn-primary" onClick={handleClaim} disabled={actionLoading}>
                    <UserCheck size={15} /> Claim This Item (Atomic)
                  </button>
                )}

                {item.status === 'open' && (
                  <button
                    className="btn-secondary"
                    onClick={() => handleTransition('in_progress')}
                    disabled={actionLoading}
                  >
                    Start Working <ArrowRight size={14} />
                  </button>
                )}

                {item.status === 'in_progress' && (
                  <>
                    <button
                      className="btn-primary"
                      style={{ background: 'linear-gradient(135deg, #f59e0b, #d97706)' }}
                      onClick={() => handleTransition('awaiting_approval')}
                      disabled={actionLoading}
                    >
                      Request Lead Approval <ArrowRight size={14} />
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={() => handleTransition('open')}
                      disabled={actionLoading}
                    >
                      Revert to Open
                    </button>
                  </>
                )}

                {item.status === 'awaiting_approval' && (
                  <>
                    <button
                      className="btn-primary"
                      style={{
                        background: isLeadOrAdmin
                          ? 'linear-gradient(135deg, #10b981, #059669)'
                          : 'rgba(255, 255, 255, 0.1)',
                        cursor: isLeadOrAdmin ? 'pointer' : 'not-allowed',
                      }}
                      onClick={() => handleTransition('resolved')}
                      disabled={actionLoading || !isLeadOrAdmin}
                      title={isLeadOrAdmin ? 'Approve and resolve' : 'Approval requires Lead or Admin role'}
                    >
                      <ShieldCheck size={15} /> Approve & Resolve {isLeadOrAdmin ? '(Lead Authorized)' : '(Lead Only)'}
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={() => handleTransition('in_progress')}
                      disabled={actionLoading}
                    >
                      Return for Rework
                    </button>
                  </>
                )}

                {item.status === 'resolved' && (
                  <>
                    <button
                      className="btn-primary"
                      style={{ background: 'linear-gradient(135deg, #64748b, #475569)' }}
                      onClick={() => handleTransition('closed')}
                      disabled={actionLoading}
                    >
                      Close Item
                    </button>
                    <button
                      className="btn-secondary"
                      onClick={() => handleTransition('in_progress')}
                      disabled={actionLoading}
                    >
                      Re-open Issue
                    </button>
                  </>
                )}

                {item.status === 'closed' && isLeadOrAdmin && (
                  <button
                    className="btn-secondary"
                    onClick={() => handleTransition('in_progress')}
                    disabled={actionLoading}
                  >
                    Reopen (Lead Action)
                  </button>
                )}
              </div>
            </div>
          )}

          {/* Comments Section */}
          <div style={{ marginBottom: '1.5rem' }}>
            <h4 style={{ fontSize: '0.95rem', color: '#fff', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <MessageSquare size={16} color="#60a5fa" />
              Discussion ({item.comments?.length || 0})
            </h4>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '0.85rem' }}>
              {item.comments && item.comments.length > 0 ? (
                item.comments.map((c) => (
                  <div
                    key={c.id}
                    style={{
                      background: 'rgba(255, 255, 255, 0.03)',
                      border: '1px solid var(--border-color)',
                      borderRadius: 'var(--radius-sm)',
                      padding: '0.65rem 0.85rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-dim)', marginBottom: '0.25rem' }}>
                      <strong style={{ color: '#93c5fd' }}>{c.user_name}</strong>
                      <span>{new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#e2e8f0' }}>{c.content}</div>
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-dim)', fontStyle: 'italic' }}>
                  No comments yet on this work item.
                </div>
              )}
            </div>

            {!isViewer && (
              <form onSubmit={handleSendComment} style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  className="search-input"
                  style={{ paddingLeft: '1rem', fontSize: '0.85rem' }}
                  placeholder="Add a comment or operational note..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                />
                <button type="submit" className="btn-primary" style={{ padding: '0.5rem 1rem' }}>
                  <Send size={15} />
                </button>
              </form>
            )}
          </div>

          {/* Append-Only Activity Log Timeline */}
          <div>
            <h4 style={{ fontSize: '0.95rem', color: '#fff', marginBottom: '0.75rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Clock size={16} color="#8b5cf6" />
              Append-Only Audit Timeline ({item.activity_events?.length || 0})
            </h4>

            <div className="timeline">
              {item.activity_events?.map((ev) => (
                <div key={ev.id} className="timeline-item">
                  <div className="timeline-dot" />
                  <div className="timeline-header">
                    <span>
                      <strong style={{ color: '#cbd5e1' }}>{ev.user_name || 'System'}</strong>{' '}
                      <span style={{ color: 'var(--text-dim)' }}>({ev.event_type})</span>
                    </span>
                    <span className="timeline-time">
                      {new Date(ev.created_at).toLocaleString([], {
                        month: 'short',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit',
                      })}
                    </span>
                  </div>
                  <div className="timeline-msg">{ev.message || `State changed to ${ev.to_value}`}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
