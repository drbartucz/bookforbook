import axios from 'axios';

import useAuthStore from '../store/authStore';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ── Request interceptor: attach JWT access token ──────────────────────────────
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ── Response interceptor: refresh token on 401 and retry ─────────────────────
let isRefreshing = false;
let failedQueue = [];

export function __resetAuthRefreshStateForTests() {
  isRefreshing = false;
  failedQueue = [];
  delete apiClient.defaults.headers.common.Authorization;
}

export function __getAuthRefreshStateForTests() {
  return {
    isRefreshing,
    failedQueueLength: failedQueue.length,
  };
}

function processQueue(error, token = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          })
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = useAuthStore.getState().refreshToken;
      if (!refreshToken) {
        isRefreshing = false;
        useAuthStore.getState().logout();
        window.dispatchEvent(new CustomEvent('auth:logout', {
          detail: { message: 'You have been automatically logged out.' }
        }));
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(`${BASE_URL}/auth/token/refresh/`, {
          refresh: refreshToken,
        });
        const { access } = response.data;
        useAuthStore.getState().updateAccessToken(access);
        apiClient.defaults.headers.common.Authorization = `Bearer ${access}`;
        originalRequest.headers.Authorization = `Bearer ${access}`;
        processQueue(null, access);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError, null);
        useAuthStore.getState().logout();
        window.dispatchEvent(new CustomEvent('auth:logout', {
          detail: { message: 'You have been automatically logged out.' }
        }));
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  register: (data) => apiClient.post('/auth/register/', data),
  login: (data) => apiClient.post('/auth/token/', data),
  logout: (data) => apiClient.post('/auth/logout/', data),
  verifyEmail: (data) => apiClient.post('/auth/verify-email/', data),
  requestPasswordReset: (data) => apiClient.post('/auth/password-reset/', data),
  confirmPasswordReset: (data) => apiClient.post('/auth/password-reset/confirm/', data),
  refreshToken: (data) => apiClient.post('/auth/token/refresh/', data),
};

// ── Users ─────────────────────────────────────────────────────────────────────
export const users = {
  getMe: () => apiClient.get('/users/me/'),
  updateMe: (data) => apiClient.patch('/users/me/', data),
  verifyAddress: (data) => apiClient.post('/users/me/address/verify/', data),
  exportData: () => apiClient.get('/users/me/export/', { responseType: 'blob' }),
  deleteAccount: () => apiClient.delete('/users/me/'),
  getPublicProfile: (userId) => apiClient.get(`/users/${userId}/`),
  getUserRatings: (userId, params) => apiClient.get(`/users/${userId}/ratings/`, { params }),
  getUserOfferedBooks: (userId, params) => apiClient.get(`/users/${userId}/offered/`, { params }),
  getUserWantedBooks: (userId, params) => apiClient.get(`/users/${userId}/wanted/`, { params }),
};

// ── Books ─────────────────────────────────────────────────────────────────────
export const books = {
  lookupISBN: (isbn) => apiClient.post(`/books/lookup/`, { isbn }),
  searchBooks: (params) => apiClient.get('/books/search/', { params }),
  getBook: (bookId) => apiClient.get(`/books/${bookId}/`),
};

// ── My Books (Have-list) ──────────────────────────────────────────────────────
export const myBooks = {
  list: (params) => apiClient.get('/my-books/', { params }),
  add: (data) => apiClient.post('/my-books/', data),
  update: (id, data) => apiClient.patch(`/my-books/${id}/`, data),
  remove: (id) => apiClient.delete(`/my-books/${id}/`),
};

// ── Wishlist (Want-list) ──────────────────────────────────────────────────────
export const wishlist = {
  list: (params) => apiClient.get('/wishlist/', { params }),
  add: (data) => apiClient.post('/wishlist/', data),
  update: (id, data) => apiClient.patch(`/wishlist/${id}/`, data),
  remove: (id) => apiClient.delete(`/wishlist/${id}/`),
};

// ── Matches ───────────────────────────────────────────────────────────────────
export const matches = {
  list: (params) => apiClient.get('/matches/', { params }),
  getDetail: (id) => apiClient.get(`/matches/${id}/`),
  accept: (id) => apiClient.post(`/matches/${id}/accept/`),
  decline: (id) => apiClient.post(`/matches/${id}/decline/`),
};

// ── Proposals ─────────────────────────────────────────────────────────────────
export const proposals = {
  list: (params) => apiClient.get('/proposals/', { params }),
  create: (data) => apiClient.post('/proposals/', data),
  getDetail: (id) => apiClient.get(`/proposals/${id}/`),
  accept: (id) => apiClient.post(`/proposals/${id}/accept/`),
  decline: (id) => apiClient.post(`/proposals/${id}/decline/`),
  counter: (id, data) => apiClient.post(`/proposals/${id}/counter/`, data),
};

// ── Trades ────────────────────────────────────────────────────────────────────
export const trades = {
  list: (params) => apiClient.get('/trades/', { params }),
  getDetail: (id) => apiClient.get(`/trades/${id}/`),
  markShipped: (id, data) => apiClient.post(`/trades/${id}/mark-shipped/`, data),
  markReceived: (id) => apiClient.post(`/trades/${id}/mark-received/`),
  rate: (id, data) => apiClient.post(`/trades/${id}/rate/`, data),
  getMessages: (id, params) => apiClient.get(`/trades/${id}/messages/`, { params }),
  sendMessage: (id, data) => apiClient.post(`/trades/${id}/messages/`, data),
};

// ── Donations ─────────────────────────────────────────────────────────────────
export const donations = {
  list: (params) => apiClient.get('/donations/', { params }),
  offer: (data) => apiClient.post('/donations/', data),
  accept: (id) => apiClient.post(`/donations/${id}/accept/`),
  decline: (id) => apiClient.post(`/donations/${id}/decline/`),
};

// ── Institutions ──────────────────────────────────────────────────────────────
export const institutions = {
  list: (params) => apiClient.get('/institutions/', { params }),
  getDetail: (id) => apiClient.get(`/institutions/${id}/`),
  getWantedList: (id, params) => apiClient.get(`/institutions/${id}/wanted/`, { params }),
};

// ── Browse ────────────────────────────────────────────────────────────────────
export const browse = {
  available: (params) => apiClient.get('/browse/available/', { params }),
  partnerBooks: (userId, params) => apiClient.get(`/browse/partner/${userId}/`, { params }),
  shippingEstimate: (data) => apiClient.post('/browse/shipping-estimate/', data),
};

// ── Notifications ─────────────────────────────────────────────────────────────
export const notifications = {
  list: (params) => apiClient.get('/notifications/', { params }),
  markRead: (id) => apiClient.post(`/notifications/${id}/read/`),
  markAllRead: () => apiClient.post('/notifications/read-all/'),
  counts: () => apiClient.get('/notifications/counts/'),
};

export default apiClient;
