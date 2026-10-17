const API_BASE = '/api';

export function getAuthToken() {
  return localStorage.getItem('newtonite_token') || '';
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('newtonite_token', token);
  } else {
    localStorage.removeItem('newtonite_token');
  }
}

export function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

async function apiRequest(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  const contentType = response.headers.get('content-type');
  const isJson = contentType && contentType.includes('application/json');
  const data = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    const error = new Error(
      typeof data === 'object' && data.detail
        ? typeof data.detail === 'string'
          ? data.detail
          : JSON.stringify(data.detail)
        : `Request failed with status ${response.status}`
    );
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

export const api = {
  // Auth
  login: async (email, password) => {
    const data = await apiRequest('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(data.access_token);
    return data;
  },

  getMe: () => apiRequest('/auth/me'),
  getDemoUsers: () => apiRequest('/auth/demo-users'),

  // Teams
  getTeams: () => apiRequest('/teams'),
  getTeamMembers: (teamId) => apiRequest(`/teams/${teamId}/members`),

  // Work Items
  getWorkItems: (params = {}) => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null && val !== '') {
        searchParams.append(key, val);
      }
    });
    const qs = searchParams.toString();
    return apiRequest(`/items${qs ? `?${qs}` : ''}`);
  },

  getWorkItem: (id) => apiRequest(`/items/${id}`),

  createWorkItem: (data, idempotencyKey = null) => {
    const key = idempotencyKey || generateUUID();
    return apiRequest('/items', {
      method: 'POST',
      headers: { 'Idempotency-Key': key },
      body: JSON.stringify(data),
    });
  },

  updateWorkItem: (id, data, idempotencyKey = null) => {
    const headers = {};
    if (idempotencyKey) {
      headers['Idempotency-Key'] = idempotencyKey;
    }
    return apiRequest(`/items/${id}`, {
      method: 'PATCH',
      headers,
      body: JSON.stringify(data),
    });
  },

  claimWorkItem: (id) =>
    apiRequest(`/items/${id}/claim`, {
      method: 'POST',
    }),

  transitionWorkItem: (id, targetStatus, comment = '') =>
    apiRequest(`/items/${id}/transition`, {
      method: 'POST',
      body: JSON.stringify({ target_status: targetStatus, comment }),
    }),

  addComment: (id, content) =>
    apiRequest(`/items/${id}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),
};
