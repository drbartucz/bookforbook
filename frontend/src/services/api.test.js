import { describe, expect, it } from 'vitest';

import apiClient from './api';

describe('api client request interceptor', () => {
  it('attaches authorization header when access token exists', async () => {
    localStorage.setItem('accessToken', 'token-123');

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

    expect(requestHeaders.Authorization).toBe('Bearer token-123');
  });

  it('does not attach authorization header when token does not exist', async () => {
    localStorage.removeItem('accessToken');

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
