import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const useAuthStore = create(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,

      login: (tokens, user) => {
        // Also store tokens in localStorage for the axios interceptor
        if (tokens.access) {
          localStorage.setItem('accessToken', tokens.access);
        }
        if (tokens.refresh) {
          localStorage.setItem('refreshToken', tokens.refresh);
        }
        set({
          user,
          accessToken: tokens.access || null,
          refreshToken: tokens.refresh || null,
        });
      },

      logout: () => {
        localStorage.removeItem('accessToken');
        localStorage.removeItem('refreshToken');
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
        localStorage.setItem('accessToken', accessToken);
        set({ accessToken });
      },
    }),
    {
      name: 'bookforbook-auth',
      // Only persist user data, not tokens (tokens are in localStorage via interceptors)
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
      }),
    }
  )
);

export default useAuthStore;
