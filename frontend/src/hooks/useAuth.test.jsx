import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import useAuth from './useAuth';
import useAuthStore from '../store/authStore';
import useNotificationStore from './useNotification';

describe('useAuth', () => {
    beforeEach(() => {
        localStorage.clear();
        useAuthStore.setState({ user: null, accessToken: null, refreshToken: null });
        useNotificationStore.setState({ notifications: [] });
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it('isAuthenticated is false when no access token', () => {
        const { result } = renderHook(() => useAuth());
        expect(result.current.isAuthenticated).toBe(false);
    });

    it('isAuthenticated is true after login', () => {
        useAuthStore.getState().login({ access: 'tok', refresh: 'ref' }, { id: 'u1', username: 'alice' });
        const { result } = renderHook(() => useAuth());
        expect(result.current.isAuthenticated).toBe(true);
    });

    it('isIndividual reflects account_type', () => {
        useAuthStore.getState().login(
            { access: 'tok', refresh: 'ref' },
            { id: 'u1', username: 'alice', account_type: 'individual' }
        );
        const { result } = renderHook(() => useAuth());
        expect(result.current.isIndividual).toBe(true);
        expect(result.current.isInstitution).toBe(false);
    });

    it.each([
        [false, 'individual'],
        [true, 'library'],
        [true, 'bookstore'],
    ])('isInstitution is %s for account_type=%s', (expectedIsInstitution, accountType) => {
        useAuthStore.getState().login(
            { access: 'tok', refresh: 'ref' },
            { id: 'u1', username: 'user', account_type: accountType }
        );
        const { result } = renderHook(() => useAuth());
        expect(result.current.isInstitution).toBe(expectedIsInstitution);
        expect(result.current.isIndividual).toBe(accountType === 'individual');
    });

    it('listens for auth:logout event and clears state', async () => {
        useAuthStore.getState().login({ access: 'tok', refresh: 'ref' }, { id: 'u1', username: 'alice' });
        const { result } = renderHook(() => useAuth());

        expect(result.current.isAuthenticated).toBe(true);

        // Dispatch the global event that the axios interceptor would fire
        await act(async () => {
            window.dispatchEvent(new CustomEvent('auth:logout'));
        });

        expect(result.current.isAuthenticated).toBe(false);
        expect(result.current.user).toBeNull();
    });

    it('shows warning notification when auth:session-invalid event is dispatched', async () => {
        const { result } = renderHook(() => useAuth());

        expect(result.current.isAuthenticated).toBe(false);
        expect(useNotificationStore.getState().notifications).toHaveLength(0);

        await act(async () => {
            window.dispatchEvent(
                new CustomEvent('auth:session-invalid', {
                    detail: { message: 'You were logged out because your session expired. Please sign in again.' },
                })
            );
        });

        const notifications = useNotificationStore.getState().notifications;
        expect(notifications).toHaveLength(1);
        expect(notifications[0]).toMatchObject({
            type: 'warning',
            message: 'You were logged out because your session expired. Please sign in again.',
        });
        expect(result.current.isAuthenticated).toBe(false);
    });
});
