import { create } from 'zustand';
import { persist } from 'zustand/middleware';

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
    }
  )
);

export default useAuthStore;
