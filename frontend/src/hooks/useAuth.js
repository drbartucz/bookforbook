import { useEffect } from 'react';
import useAuthStore from '../store/authStore.js';
import useNotificationStore from './useNotification.js';

export default function useAuth() {
  const { user, accessToken, refreshToken, login, logout, updateUser } = useAuthStore();
  const { addNotification } = useNotificationStore();

  // Listen for auth:logout events from the axios interceptor
  useEffect(() => {
    const handleLogout = (event) => {
      logout();
      // Show friendly logout message if provided
      const message = event.detail?.message || 'You have been logged out.';
      addNotification(message, 'warning', 5000);
    };
    window.addEventListener('auth:logout', handleLogout);
    return () => {
      window.removeEventListener('auth:logout', handleLogout);
    };
  }, [logout, addNotification]);

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated: !!accessToken,
    isIndividual: user?.account_type === 'individual',
    isInstitution: ['library', 'bookstore'].includes(user?.account_type),
    login,
    logout,
    updateUser,
  };
}
