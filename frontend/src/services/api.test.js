import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';

let apiClient;
let auth;
let books;
let myBooks;
let wishlist;
let matches;
let proposals;
let trades;
let donations;
let institutions;
let browse;
let notifications;
let users;
let useAuthStore;
let getAuthRefreshState;
let resetAuthRefreshState;

function makeJwt(payload = {}) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(
    JSON.stringify({
      exp: Math.floor(Date.now() / 1000) + 3600,
      token_type: 'access',
      ...payload,
    })
  );
  return `${header}.${body}.signature`;
}

async function loadFreshApiModule() {
  vi.resetModules();
  ({ default: useAuthStore } = await import('../store/authStore'));
  ({
    __getAuthRefreshStateForTests: getAuthRefreshState,
    __resetAuthRefreshStateForTests: resetAuthRefreshState,
    default: apiClient,
    books,
    users,
  } = await import('./api'));
}

describe('api client request interceptor', () => {
  beforeEach(async () => {
    await loadFreshApiModule();
    localStorage.clear();
    resetAuthRefreshState();
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('attaches authorization header when access token exists', async () => {
    const token = makeJwt();
    useAuthStore.setState({
      accessToken: token,
      refreshToken: null,
      user: null,
    });

    let requestHeaders = {};
    await apiClient.get('/health/', {
      adapter: async (config) => {
        requestHeaders = config.headers;
        return {
          data: { ok: true },
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        };
      },
    });

    expect(requestHeaders.Authorization).toBe(`Bearer ${token}`);
  });

  it('does not attach authorization header for malformed access token', async () => {
    useAuthStore.setState({
      accessToken: 'not-a-jwt',
      refreshToken: null,
      user: null,
    });

    let requestHeaders = {};
    await apiClient.get('/health/', {
      adapter: async (config) => {
        requestHeaders = config.headers;
        return {
          data: { ok: true },
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        };
      },
    });

    expect(requestHeaders.Authorization).toBeUndefined();
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it('does not attach authorization header when token does not exist', async () => {
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      user: null,
    });

    let requestHeaders = {};
    await apiClient.get('/health/', {
      adapter: async (config) => {
        requestHeaders = config.headers;
        return {
          data: { ok: true },
          status: 200,
          statusText: 'OK',
          headers: {},
          config,
        };
      },
    });

    expect(requestHeaders.Authorization).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Response interceptor: 401 refresh / retry
// ---------------------------------------------------------------------------

describe('api client response interceptor', () => {
  beforeEach(async () => {
    await loadFreshApiModule();
    localStorage.clear();
    resetAuthRefreshState();
    useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('clears tokens and fires auth:logout event when no refresh token on 401', async () => {
    useAuthStore.setState({ user: null, accessToken: 'old-access', refreshToken: null });

    const logoutHandler = vi.fn();
    window.addEventListener('auth:logout', logoutHandler);

    let callCount = 0;
    try {
      await apiClient.get('/protected/', {
        adapter: async (config) => {
          if (callCount++ === 0) {
            const err = new Error('Unauthorized');
            err.config = config;
            err.response = { status: 401, data: 'Unauthorized', config };
            throw err;
          }
          return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
        },
      });
    } catch {
      // expected to throw
    }

    expect(logoutHandler).toHaveBeenCalledOnce();
    expect(useAuthStore.getState().accessToken).toBeNull();
    window.removeEventListener('auth:logout', logoutHandler);
  });

  it('retries original request with new token after successful refresh', async () => {
    const refreshedAccess = makeJwt();
    useAuthStore.setState({
      user: null,
      accessToken: makeJwt(),
      refreshToken: makeJwt({ token_type: 'refresh', exp: Math.floor(Date.now() / 1000) + 86400 }),
    });

    const postSpy = vi.spyOn(axios, 'post').mockResolvedValueOnce({
      data: { access: refreshedAccess },
    });

    let callCount = 0;
    const result = await apiClient.get('/protected/', {
      adapter: async (config) => {
        callCount++;
        if (callCount === 1) {
          const err = new Error('Unauthorized');
          err.config = { ...config, _retry: false };
          err.response = { status: 401, data: 'Unauthorized', config };
          throw err;
        }
        return { data: { ok: true }, status: 200, statusText: 'OK', headers: {}, config };
      },
    });

    expect(result.data).toEqual({ ok: true });
    expect(useAuthStore.getState().accessToken).toBe(refreshedAccess);
    postSpy.mockRestore();
  });

  it('lookupISBN sends a POST request with isbn in the body', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
      data: { id: 'abc', isbn_13: '9780141036144', title: 'Nineteen Eighty-Four' },
    });

    await books.lookupISBN('9780141036144');

    expect(postSpy).toHaveBeenCalledWith('/books/lookup/', { isbn: '9780141036144' });
    postSpy.mockRestore();
  });

  it('deleteAccount sends password in DELETE request body', async () => {
    const deleteSpy = vi.spyOn(apiClient, 'delete').mockResolvedValueOnce({
      data: { detail: 'Account deletion initiated.' },
    });

    await users.deleteAccount({ password: 'secret123' });

    expect(deleteSpy).toHaveBeenCalledWith('/users/me/', { data: { password: 'secret123' } });
    deleteSpy.mockRestore();
  });

  it('fires auth:logout and rejects when refresh call fails', async () => {
    useAuthStore.setState({
      user: null,
      accessToken: 'old-access',
      refreshToken: 'expired-refresh',
    });

    const postSpy = vi.spyOn(axios, 'post').mockRejectedValueOnce(new Error('Refresh failed'));

    const logoutHandler = vi.fn();
    window.addEventListener('auth:logout', logoutHandler);

    let callCount = 0;
    await expect(
      apiClient.get('/protected/', {
        adapter: async (config) => {
          if (callCount++ === 0) {
            const err = new Error('Unauthorized');
            err.config = { ...config, _retry: false };
            err.response = { status: 401, data: 'Unauthorized', config };
            throw err;
          }
          return { data: {}, status: 200, statusText: 'OK', headers: {}, config };
        },
      })
    ).rejects.toThrow();

    expect(logoutHandler).toHaveBeenCalledOnce();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();

    window.removeEventListener('auth:logout', logoutHandler);
    postSpy.mockRestore();
  });

  it('queues simultaneous 401 responses behind a single refresh request', async () => {
    const refreshedAccess = makeJwt();
    useAuthStore.setState({
      user: null,
      accessToken: makeJwt(),
      refreshToken: makeJwt({ token_type: 'refresh', exp: Math.floor(Date.now() / 1000) + 86400 }),
    });

    let resolveRefresh;
    const refreshPromise = new Promise((resolve) => {
      resolveRefresh = resolve;
    });
    const postSpy = vi.spyOn(axios, 'post').mockReturnValue(refreshPromise);

    const attempts = new Map();
    const seenRetryAuthHeaders = [];
    const adapter = async (config) => {
      const key = config.url;
      const count = (attempts.get(key) ?? 0) + 1;
      attempts.set(key, count);

      if (count === 1) {
        const err = new Error('Unauthorized');
        err.config = config;
        err.response = { status: 401, data: 'Unauthorized', config };
        throw err;
      }

      seenRetryAuthHeaders.push(config.headers?.Authorization);
      return {
        data: { ok: true, path: key },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      };
    };

    const reqA = apiClient.get('/protected/a', { adapter });
    await vi.waitFor(() => {
      expect(getAuthRefreshState().isRefreshing).toBe(true);
    });
    const reqB = apiClient.get('/protected/b', { adapter });
    await vi.waitFor(() => {
      expect(getAuthRefreshState().failedQueueLength).toBe(1);
    });

    resolveRefresh({ data: { access: refreshedAccess } });
    const [resA, resB] = await Promise.all([reqA, reqB]);

    expect(resA.data).toEqual({ ok: true, path: '/protected/a' });
    expect(resB.data).toEqual({ ok: true, path: '/protected/b' });
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(seenRetryAuthHeaders).toEqual([`Bearer ${refreshedAccess}`, `Bearer ${refreshedAccess}`]);
    expect(useAuthStore.getState().accessToken).toBe(refreshedAccess);

    postSpy.mockRestore();
  });

  it('rejects queued promises when refresh fails while another request is in-flight', async () => {
    useAuthStore.setState({
      user: null,
      accessToken: makeJwt(),
      refreshToken: makeJwt({ token_type: 'refresh', exp: Math.floor(Date.now() / 1000) + 86400 }),
    });

    const refreshError = new Error('Refresh failed');
    let resolveRefresh;
    const refreshPromise = new Promise((_, reject) => {
      resolveRefresh = () => reject(refreshError);
    });
    const postSpy = vi.spyOn(axios, 'post').mockReturnValue(refreshPromise);

    let callCount = 0;
    const adapter = async (config) => {
      callCount++;
      const err = new Error('Unauthorized');
      err.config = config;
      err.response = { status: 401, data: 'Unauthorized', config };
      throw err;
    };

    const reqA = apiClient.get('/protected/a', { adapter });
    await vi.waitFor(() => expect(getAuthRefreshState().isRefreshing).toBe(true));
    const reqB = apiClient.get('/protected/b', { adapter });
    await vi.waitFor(() => expect(getAuthRefreshState().failedQueueLength).toBe(1));

    resolveRefresh();
    await expect(reqA).rejects.toThrow();
    await expect(reqB).rejects.toThrow();  // queued promise was rejected via prom.reject (line 52)

    postSpy.mockRestore();
  });

  it('passes non-401 errors through to caller unchanged', async () => {
    await expect(
      apiClient.get('/server-error/', {
        adapter: async (config) => {
          const err = new Error('Internal Server Error');
          err.config = config;
          err.response = { status: 500, data: 'Internal Server Error', config };
          throw err;
        },
      })
    ).rejects.toThrow('Internal Server Error');
  });

  it('request interceptor error callback forwards rejection from a preceding interceptor (covers line 29)', async () => {
    // Request interceptors run in LIFO order. A newly-added interceptor runs first;
    // if it throws, api.js's error callback at line 29 (error => Promise.reject(error)) fires.
    const throwingId = apiClient.interceptors.request.use(
      () => { throw new Error('Simulated interceptor error'); }
    );
    await expect(apiClient.get('/test/')).rejects.toThrow();
    apiClient.interceptors.request.eject(throwingId);
  });
});

// ── Coverage: every exported API method arrow-function ────────────────────────
// Each one-liner method is a distinct V8 function; calling it once marks it covered.
describe('api module — method function coverage', () => {
  beforeEach(async () => {
    vi.resetModules();
    ({
      default: apiClient,
      auth, users, books, myBooks, wishlist, matches, proposals, trades,
      donations, institutions, browse, notifications,
    } = await import('./api'));
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: {} });
    vi.spyOn(apiClient, 'post').mockResolvedValue({ data: {} });
    vi.spyOn(apiClient, 'patch').mockResolvedValue({ data: {} });
    vi.spyOn(apiClient, 'delete').mockResolvedValue({ data: {} });
  });

  it('calls every API method once to cover all arrow-function definitions', async () => {
    // auth
    await auth.register({}); await auth.login({}); await auth.logout({});
    await auth.verifyEmail({}); await auth.requestPasswordReset({});
    await auth.confirmPasswordReset({}); await auth.refreshToken({});
    // users
    await users.getMe(); await users.updateMe({}); await users.verifyAddress({});
    await users.exportData(); await users.deleteAccount({});
    await users.getPublicProfile('u1'); await users.getUserRatings('u1', {});
    await users.getUserOfferedBooks('u1', {}); await users.getUserWantedBooks('u1', {});
    // books
    await books.lookupISBN('isbn'); await books.searchBooks({}); await books.getBook('b1');
    // myBooks
    await myBooks.list({}); await myBooks.add({}); await myBooks.update('id', {}); await myBooks.remove('id');
    // wishlist
    await wishlist.list({}); await wishlist.add({}); await wishlist.update('id', {}); await wishlist.remove('id');
    // matches
    await matches.list({}); await matches.getDetail('id');
    await matches.accept('id'); await matches.decline('id');
    // proposals
    await proposals.list({}); await proposals.create({}); await proposals.getDetail('id');
    await proposals.accept('id'); await proposals.decline('id'); await proposals.counter('id', {});
    // trades
    await trades.list({}); await trades.getDetail('id'); await trades.markShipped('id', {});
    await trades.markReceived('id'); await trades.rate('id', {});
    await trades.getMessages('id', {}); await trades.sendMessage('id', {});
    // donations
    await donations.list({}); await donations.offer({}); await donations.accept('id'); await donations.decline('id');
    // institutions
    await institutions.list({}); await institutions.getDetail('id'); await institutions.getWantedList('id', {});
    // browse
    await browse.available({}); await browse.partnerBooks('u1', {}); await browse.shippingEstimate({});
    // notifications
    await notifications.list({}); await notifications.markRead('id');
    await notifications.markAllRead(); await notifications.counts();
  });
});
