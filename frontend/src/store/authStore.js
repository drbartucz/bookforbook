import { create } from 'zustand';
import { persist } from 'zustand/middleware';

function dispatchSessionInvalidEvent(message) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent('auth:session-invalid', {
      detail: { message },
    })
  );
}

function isLikelyJwt(token) {
  return typeof token === 'string' && token.split('.').length === 3;
}

function decodeJwtPayload(token) {
  try {
    const [, payloadPart] = token.split('.');
    const normalized = payloadPart.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), '=');
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

function isExpiredJwt(token) {
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload || typeof payload.exp !== 'number') {
    return true;
  }
  const nowInSeconds = Math.floor(Date.now() / 1000);
  return payload.exp <= nowInSeconds;
}

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      login: (tokens, user) => {
        set({
          user,
          accessToken: tokens.access || null,
          refreshToken: tokens.refresh || null,
        });
      },

      logout: () => {
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
        });
      },

      updateUser: (user) => {
        set({ user });
      },

      updateAccessToken: (accessToken) => {
        set({ accessToken });
      },
    }),
    {
      name: 'bookforbook-auth',
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
      onRehydrateStorage: () => (state) => {
        if (!state) return;

        const hasMalformedAccess = !!state.accessToken && !isLikelyJwt(state.accessToken);
        const hasMalformedRefresh = !!state.refreshToken && !isLikelyJwt(state.refreshToken);

        if (hasMalformedAccess || hasMalformedRefresh) {
          state.logout();
          dispatchSessionInvalidEvent('You were logged out because your saved session was invalid. Please sign in again.');
          return;
        }

        if (state.refreshToken && isExpiredJwt(state.refreshToken)) {
          state.logout();
          dispatchSessionInvalidEvent('You were logged out because your session expired. Please sign in again.');
          return;
        }

        if (state.accessToken && isExpiredJwt(state.accessToken)) {
          state.updateAccessToken(null);
        }
      },
    }
  )
);

export default useAuthStore;
