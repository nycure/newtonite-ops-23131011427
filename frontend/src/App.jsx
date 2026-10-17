import React, { useState, useEffect, useCallback } from 'react';
import {
  Search,
  Filter,
  Plus,
  RefreshCw,
  CheckCircle2,
  AlertOctagon,
  Clock,
  Layers,
  Inbox,
  UserCheck,
} from 'lucide-react';
import Navbar from './components/Navbar';
import WorkItemCard from './components/WorkItemCard';
import WorkItemDetailModal from './components/WorkItemDetailModal';
import CreateItemModal from './components/CreateItemModal';
import ConflictBanner from './components/ConflictBanner';
import { api, getAuthToken, setAuthToken } from './api/client';

export default function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [demoUsers, setDemoUsers] = useState([]);
  const [teams, setTeams] = useState([]);
  const [selectedTeam, setSelectedTeam] = useState(null);

  // Tab & Filters
  const [activeTab, setActiveTab] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [priorityFilter, setPriorityFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  // Items State
  const [items, setItems] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [nextCursor, setNextCursor] = useState(null);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(false);

  // Modal State
  const [selectedItemDetail, setSelectedItemDetail] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [globalConflict, setGlobalConflict] = useState(null);

  // 1. Initial Load: Authenticate default user (Alice Morgan) & load metadata
  useEffect(() => {
    async function init() {
      try {
        const demoList = await api.getDemoUsers();
        setDemoUsers(demoList);

        // If no token, login as Alice Morgan (Lead)
        if (!getAuthToken() && demoList.length > 0) {
          await api.login(demoList[0].email, 'password123');
        }

        const me = await api.getMe();
        setCurrentUser(me);

        const userTeams = await api.getTeams();
        setTeams(userTeams);
        if (userTeams.length > 0) {
          setSelectedTeam(userTeams[0]);
        }
      } catch (err) {
        console.error('Initialization error:', err);
      }
    }
    init();
  }, []);

  // 2. Fetch Work Items (Scoped & Filtered)
  const fetchItems = useCallback(
    async (isCursorAppend = false) => {
      if (!currentUser) return;
      setLoading(true);
      try {
        const params = {
          team_id: selectedTeam?.id,
          limit: 25,
        };

        if (isCursorAppend && nextCursor) {
          params.cursor = nextCursor;
        }

        if (searchQuery.trim()) params.q = searchQuery.trim();
        if (statusFilter) params.status = statusFilter;
        if (priorityFilter) params.priority = priorityFilter;
        if (typeFilter) params.type = typeFilter;

        // Tab Presets
        if (activeTab === 'assigned_to_me') {
          params.assigned_to_me = true;
        } else if (activeTab === 'unassigned_urgent') {
          params.unassigned_only = true;
          params.priority = 'urgent';
        } else if (activeTab === 'awaiting_my_approval') {
          params.awaiting_my_approval = true;
        }

        const data = await api.getWorkItems(params);
        if (isCursorAppend) {
          setItems((prev) => [...prev, ...data.items]);
        } else {
          setItems(data.items);
        }
        setTotalCount(data.total_count);
        setNextCursor(data.next_cursor);
        setHasMore(data.has_more);
      } catch (err) {
        console.error('Fetch items error:', err);
      } finally {
        setLoading(false);
      }
    },
    [currentUser, selectedTeam, activeTab, searchQuery, statusFilter, priorityFilter, typeFilter, nextCursor]
  );

  // Re-fetch on filter changes
  useEffect(() => {
    fetchItems(false);
  }, [currentUser, selectedTeam, activeTab, statusFilter, priorityFilter, typeFilter]);

  // Handle Search Debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchItems(false);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // 3. User Switch Handler (For Reviewer Role Testing)
  const handleSwitchUser = async (email) => {
    try {
      await api.login(email, 'password123');
      const me = await api.getMe();
      setCurrentUser(me);

      const userTeams = await api.getTeams();
      setTeams(userTeams);
      setSelectedTeam(userTeams.length > 0 ? userTeams[0] : null);
      setGlobalConflict(null);
      setSelectedItemDetail(null);
    } catch (err) {
      alert(`Login failed: ${err.message}`);
    }
  };

  // 4. Item Detail Loading
  const handleOpenDetail = async (itemId) => {
    try {
      const detail = await api.getWorkItem(itemId);
      setSelectedItemDetail(detail);
    } catch (err) {
      alert(err.message);
    }
  };

  // 5. Actions: Claim
  const handleClaim = async (itemId) => {
    setGlobalConflict(null);
    try {
      const updated = await api.claimWorkItem(itemId);
      setSelectedItemDetail(updated);
      fetchItems(false);
    } catch (err) {
      if (err.status === 409) {
        const msg = err.data?.detail || 'Concurrent Claim Collision: Another user claimed this item milliseconds ago!';
        setGlobalConflict(msg);
      }
      throw err;
    }
  };

  // 6. Actions: Transition
  const handleTransition = async (itemId, targetStatus, comment) => {
    setGlobalConflict(null);
    try {
      const updated = await api.transitionWorkItem(itemId, targetStatus, comment);
      setSelectedItemDetail(updated);
      fetchItems(false);
    } catch (err) {
      if (err.status === 409) {
        setGlobalConflict('Conflict detected: Work item state changed while you were viewing it.');
      }
      throw err;
    }
  };

  // 7. Actions: Optimistic Update
  const handleUpdate = async (itemId, data) => {
    setGlobalConflict(null);
    try {
      const updated = await api.updateWorkItem(itemId, data);
      setSelectedItemDetail(updated);
      fetchItems(false);
    } catch (err) {
      if (err.status === 409) {
        setGlobalConflict(
          'Optimistic Locking Mismatch (409): The item was modified by another user. Please reload before saving.'
        );
      }
      throw err;
    }
  };

  // 8. Actions: Add Comment
  const handleAddComment = async (itemId, content) => {
    await api.addComment(itemId, content);
    const updated = await api.getWorkItem(itemId);
    setSelectedItemDetail(updated);
  };

  return (
    <div className="app-container">
      {/* Top Navigation */}
      <Navbar
        currentUser={currentUser}
        demoUsers={demoUsers}
        onSwitchUser={handleSwitchUser}
        currentTeam={selectedTeam}
        teams={teams}
        onSelectTeam={setSelectedTeam}
      />

      <main className="main-content">
        {/* Global Concurrency Conflict Banner */}
        {globalConflict && (
          <ConflictBanner
            conflict={globalConflict}
            onDismiss={() => setGlobalConflict(null)}
            onReload={() => {
              setGlobalConflict(null);
              fetchItems(false);
            }}
          />
        )}

        {/* Dashboard Title & Quick Actions */}
        <div className="dashboard-header">
          <div className="dashboard-title-group">
            <h2>Operations Work Items</h2>
            <p>
              Displaying {items.length} of {totalCount.toLocaleString()} total items across your authorized teams.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button className="btn-secondary" onClick={() => fetchItems(false)} disabled={loading}>
              <RefreshCw size={15} className={loading ? 'spin' : ''} /> Refresh
            </button>
            <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
              <Plus size={16} /> New Work Item
            </button>
          </div>
        </div>

        {/* Tabs: Filter Views */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
          <div className="tabs-container">
            <button
              className={`tab-btn ${activeTab === 'all' ? 'active' : ''}`}
              onClick={() => setActiveTab('all')}
            >
              <Inbox size={15} /> All Items
            </button>
            <button
              className={`tab-btn ${activeTab === 'assigned_to_me' ? 'active' : ''}`}
              onClick={() => setActiveTab('assigned_to_me')}
            >
              <UserCheck size={15} /> Assigned to Me
            </button>
            <button
              className={`tab-btn ${activeTab === 'unassigned_urgent' ? 'active' : ''}`}
              onClick={() => setActiveTab('unassigned_urgent')}
            >
              <AlertOctagon size={15} /> Unassigned Urgent
            </button>
            <button
              className={`tab-btn ${activeTab === 'awaiting_my_approval' ? 'active' : ''}`}
              onClick={() => setActiveTab('awaiting_my_approval')}
            >
              <CheckCircle2 size={15} /> Awaiting Approval
            </button>
          </div>
        </div>

        {/* Filter and Search Bar */}
        <div className="filter-bar">
          <div className="search-input-wrapper">
            <Search className="search-icon" size={17} />
            <input
              type="text"
              className="search-input"
              placeholder="Search by title or description..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="awaiting_approval">Awaiting Approval</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>

          <select
            className="filter-select"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
          >
            <option value="">All Priorities</option>
            <option value="urgent">Urgent</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>

          <select
            className="filter-select"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">All Types</option>
            <option value="incident">Incident</option>
            <option value="customer_issue">Customer Issue</option>
            <option value="payment">Payment</option>
            <option value="compliance">Compliance</option>
            <option value="task">Task</option>
          </select>
        </div>

        {/* Work Items Feed */}
        <div style={{ minHeight: '300px' }}>
          {items.length > 0 ? (
            items.map((item) => (
              <WorkItemCard
                key={item.id}
                item={item}
                currentUserId={currentUser?.id}
                onClick={() => handleOpenDetail(item.id)}
                onClaim={handleClaim}
              />
            ))
          ) : (
            <div
              className="glass-panel"
              style={{ padding: '3.5rem', textAlign: 'center', color: 'var(--text-dim)' }}
            >
              <Inbox size={40} style={{ margin: '0 auto 1rem', opacity: 0.5 }} />
              <h3 style={{ color: '#fff', marginBottom: '0.4rem' }}>No Work Items Match Your Criteria</h3>
              <p style={{ fontSize: '0.9rem' }}>
                Try adjusting your search filters, switching teams, or resetting tab views.
              </p>
            </div>
          )}
        </div>

        {/* Cursor Pagination Load More */}
        {hasMore && (
          <div className="pagination-bar">
            <span>
              Showing {items.length} of {totalCount} items
            </span>
            <button
              className="btn-secondary"
              onClick={() => fetchItems(true)}
              disabled={loading}
            >
              Load Next Page <Clock size={14} />
            </button>
          </div>
        )}
      </main>

      {/* Item Detail & Transition Drawer/Modal */}
      {selectedItemDetail && (
        <WorkItemDetailModal
          item={selectedItemDetail}
          currentUser={currentUser}
          onClose={() => setSelectedItemDetail(null)}
          onClaim={handleClaim}
          onTransition={handleTransition}
          onUpdate={handleUpdate}
          onAddComment={handleAddComment}
          onReload={handleOpenDetail}
        />
      )}

      {/* Create Work Item Modal */}
      {showCreateModal && (
        <CreateItemModal
          teams={teams}
          onClose={() => setShowCreateModal(false)}
          onCreate={async (data, key) => {
            await api.createWorkItem(data, key);
            fetchItems(false);
          }}
        />
      )}
    </div>
  );
}
