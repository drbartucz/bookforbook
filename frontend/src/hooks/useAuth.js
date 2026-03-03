import { useEffect } from 'react';
import useAuthStore from '../store/authStore.js';

export default function useAuth() {
  const { user, accessToken, refreshToken, login, logout, updateUser } = useAuthStore();

  // Listen for auth:logout events from the axios interceptor
  useEffect(() => {
    const handleLogout = () => {
      logout();
    };
    window.addEventListener('auth:logout', handleLogout);
    return () => {
      window.removeEventListener('auth:logout', handleLogout);
    };
  }, [logout]);

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated: !!accessToken,
    isIndividual: user?.account_type === 'individual',
    isInstitution: user?.account_type === 'institution',
    login,
    logout,
    updateUser,
  };
}
