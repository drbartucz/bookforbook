import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import axios from 'axios';

let apiClient;
let books;
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
});
