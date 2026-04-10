import { beforeEach, describe, expect, it } from 'vitest';

import useAuthStore from './authStore';

describe('authStore', () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({
      user: null,
      accessToken: null,
      refreshToken: null,
    });
  });

  it('stores user and tokens on login', () => {
    const user = { id: 'u1', username: 'alice' };
    const tokens = { access: 'access-token', refresh: 'refresh-token' };

    useAuthStore.getState().login(tokens, user);

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.accessToken).toBe('access-token');
    expect(state.refreshToken).toBe('refresh-token');
    expect(localStorage.getItem('accessToken')).toBe('access-token');
    expect(localStorage.getItem('refreshToken')).toBe('refresh-token');
  });

  it('clears user and tokens on logout', () => {
    useAuthStore.getState().login(
      { access: 'access-token', refresh: 'refresh-token' },
      { id: 'u1', username: 'alice' }
    );

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(localStorage.getItem('accessToken')).toBeNull();
    expect(localStorage.getItem('refreshToken')).toBeNull();
  });

  it('updateUser replaces user object without touching tokens', () => {
    const tokens = { access: 'tok', refresh: 'ref' };
    useAuthStore.getState().login(tokens, { id: 'u1', username: 'alice' });

    useAuthStore.getState().updateUser({ id: 'u1', username: 'alice-updated' });

    expect(useAuthStore.getState().user.username).toBe('alice-updated');
    expect(useAuthStore.getState().accessToken).toBe('tok');
  });

  it('updateAccessToken persists new token to localStorage', () => {
    useAuthStore.getState().login(
      { access: 'old-access', refresh: 'ref' },
      { id: 'u1', username: 'alice' }
    );

    useAuthStore.getState().updateAccessToken('new-access');

    expect(useAuthStore.getState().accessToken).toBe('new-access');
    expect(localStorage.getItem('accessToken')).toBe('new-access');
    // refresh and user unchanged
    expect(useAuthStore.getState().refreshToken).toBe('ref');
  });

  it('login with null user is allowed', () => {
    useAuthStore.getState().login({ access: 'tok', refresh: 'ref' }, null);
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().accessToken).toBe('tok');
  });
});
