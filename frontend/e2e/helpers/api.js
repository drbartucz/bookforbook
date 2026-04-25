/**
 * helpers/api.js
 *
 * Direct API helpers for test data creation and inspection.
 * Use these in beforeEach/afterEach blocks to set up specific states
 * without going through the UI.
 *
 * All functions accept a Playwright APIRequestContext so they automatically
 * include the correct base URL.
 */

const API = '/api/v1';

// ── Auth ─────────────────────────────────────────────────────────────────────

export async function apiLogin(request, email, password) {
  const res = await request.post(`${API}/auth/token/`, {
    data: { email, password },
  });
  if (!res.ok()) throw new Error(`Login failed for ${email}: ${await res.text()}`);
  return res.json(); // { access, refresh }
}

export async function apiGetMe(request, accessToken) {
  const res = await request.get(`${API}/users/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`getMe failed: ${await res.text()}`);
  return res.json();
}

// ── My Books ──────────────────────────────────────────────────────────────────

export async function apiAddBook(request, accessToken, isbn, condition = 'good') {
  const res = await request.post(`${API}/my-books/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { isbn, condition },
  });
  if (!res.ok()) throw new Error(`addBook failed: ${await res.text()}`);
  return res.json();
}

export async function apiListMyBooks(request, accessToken) {
  const res = await request.get(`${API}/my-books/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`listMyBooks failed: ${await res.text()}`);
  return res.json();
}

export async function apiRemoveBook(request, accessToken, userBookId) {
  const res = await request.delete(`${API}/my-books/${userBookId}/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`removeBook failed: ${await res.text()}`);
}

// ── Wishlist ──────────────────────────────────────────────────────────────────

export async function apiAddWishlist(request, accessToken, isbn) {
  const res = await request.post(`${API}/wishlist/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { isbn },
  });
  if (!res.ok()) throw new Error(`addWishlist failed: ${await res.text()}`);
  return res.json();
}

export async function apiRemoveWishlist(request, accessToken, wishlistItemId) {
  const res = await request.delete(`${API}/wishlist/${wishlistItemId}/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`removeWishlist failed: ${await res.text()}`);
}

// ── Matches ───────────────────────────────────────────────────────────────────

export async function apiListMatches(request, accessToken, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await request.get(`${API}/matches/${qs ? `?${qs}` : ''}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`listMatches failed: ${await res.text()}`);
  return res.json();
}

export async function apiAcceptMatch(request, accessToken, matchId) {
  const res = await request.post(`${API}/matches/${matchId}/accept/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`acceptMatch failed: ${await res.text()}`);
  return res.json();
}

export async function apiDeclineMatch(request, accessToken, matchId) {
  const res = await request.post(`${API}/matches/${matchId}/decline/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`declineMatch failed: ${await res.text()}`);
  return res.json();
}

// ── Proposals ─────────────────────────────────────────────────────────────────

export async function apiListProposals(request, accessToken, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await request.get(`${API}/proposals/${qs ? `?${qs}` : ''}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`listProposals failed: ${await res.text()}`);
  return res.json();
}

export async function apiAcceptProposal(request, accessToken, proposalId) {
  const res = await request.post(`${API}/proposals/${proposalId}/accept/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`acceptProposal failed: ${await res.text()}`);
  return res.json();
}

export async function apiDeclineProposal(request, accessToken, proposalId) {
  const res = await request.post(`${API}/proposals/${proposalId}/decline/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`declineProposal failed: ${await res.text()}`);
  return res.json();
}

// ── Trades ────────────────────────────────────────────────────────────────────

export async function apiListTrades(request, accessToken, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await request.get(`${API}/trades/${qs ? `?${qs}` : ''}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`listTrades failed: ${await res.text()}`);
  return res.json();
}

export async function apiMarkShipped(request, accessToken, tradeId, trackingNumber = '') {
  const res = await request.post(`${API}/trades/${tradeId}/mark-shipped/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { tracking_number: trackingNumber },
  });
  if (!res.ok()) throw new Error(`markShipped failed: ${await res.text()}`);
  return res.json();
}

export async function apiMarkReceived(request, accessToken, tradeId) {
  const res = await request.post(`${API}/trades/${tradeId}/mark-received/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`markReceived failed: ${await res.text()}`);
  return res.json();
}

// ── Account deletion ──────────────────────────────────────────────────────────

export async function apiDeleteAccount(request, accessToken, password) {
  const res = await request.delete(`${API}/users/me/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    data: { password },
  });
  // 200 OK on both first deletion and idempotent repeat.
  if (!res.ok()) throw new Error(`deleteAccount failed (${res.status()}): ${await res.text()}`);
  return res.json();
}

// ── Notifications ─────────────────────────────────────────────────────────────

export async function apiGetNotificationCounts(request, accessToken) {
  const res = await request.get(`${API}/notifications/counts/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`getNotificationCounts failed: ${await res.text()}`);
  return res.json();
}

export async function apiMarkAllNotificationsRead(request, accessToken) {
  const res = await request.post(`${API}/notifications/mark-all-read/`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`markAllRead failed: ${await res.text()}`);
}

export async function apiGetNotifications(request, accessToken, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const res = await request.get(`${API}/notifications/${qs ? `?${qs}` : ''}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok()) throw new Error(`getNotifications failed: ${await res.text()}`);
  return res.json(); // { count, page, page_size, results: [...] }
}
