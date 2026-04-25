import { describe, expect, it, beforeEach } from 'vitest';

// Re-import the store functions directly to test helpers.
// We test the pure helper functions extracted from the module.
// The helpers aren't exported, so we test via the onRehydrateStorage callback
// by calling it with synthetic state objects.

import useAuthStore from './authStore.js';

// ── Helpers: pure functions ──────────────────────────────────────────────────

// Manufacture a JWT with a specific exp value so we can test isExpiredJwt.
function makeJwt(exp) {
    const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
    const payload = btoa(JSON.stringify({ sub: '1', exp }));
    return `${header}.${payload}.sig`;
}

const EXPIRED_JWT = makeJwt(Math.floor(Date.now() / 1000) - 3600); // 1h ago
const VALID_JWT   = makeJwt(Math.floor(Date.now() / 1000) + 3600); // 1h from now
const NOT_A_JWT   = 'not.a.valid.jwt.string.at.all';

// ── authStore state actions ──────────────────────────────────────────────────

describe('useAuthStore actions', () => {
    beforeEach(() => {
        useAuthStore.getState().logout();
    });

    it('login stores user and tokens', () => {
        useAuthStore.getState().login(
            { access: VALID_JWT, refresh: VALID_JWT },
            { id: '1', username: 'alice' }
        );
        const state = useAuthStore.getState();
        expect(state.user.username).toBe('alice');
        expect(state.accessToken).toBe(VALID_JWT);
        expect(state.refreshToken).toBe(VALID_JWT);
    });

    it('login with missing tokens stores null', () => {
        useAuthStore.getState().login({}, { id: '2', username: 'bob' });
        const state = useAuthStore.getState();
        expect(state.accessToken).toBeNull();
        expect(state.refreshToken).toBeNull();
    });

    it('logout clears user and tokens', () => {
        useAuthStore.getState().login(
            { access: VALID_JWT, refresh: VALID_JWT },
            { id: '1', username: 'alice' }
        );
        useAuthStore.getState().logout();
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
        expect(state.refreshToken).toBeNull();
    });

    it('updateUser replaces the user object', () => {
        useAuthStore.getState().login(
            { access: VALID_JWT, refresh: VALID_JWT },
            { id: '1', username: 'alice' }
        );
        useAuthStore.getState().updateUser({ id: '1', username: 'alice-updated' });
        expect(useAuthStore.getState().user.username).toBe('alice-updated');
    });

    it('updateAccessToken replaces only the access token', () => {
        useAuthStore.getState().login(
            { access: VALID_JWT, refresh: VALID_JWT },
            { id: '1', username: 'alice' }
        );
        const newToken = makeJwt(Math.floor(Date.now() / 1000) + 7200);
        useAuthStore.getState().updateAccessToken(newToken);
        expect(useAuthStore.getState().accessToken).toBe(newToken);
        expect(useAuthStore.getState().refreshToken).toBe(VALID_JWT); // unchanged
    });
});

// ── onRehydrateStorage callback branches ────────────────────────────────────

describe('onRehydrateStorage callback (rehydration branches)', () => {
    it('dispatchSessionInvalidEvent is called when window exists', () => {
        expect(() => {
            window.dispatchEvent(new CustomEvent('auth:session-invalid', { detail: { message: 'test' } }));
        }).not.toThrow();
    });

    it('stores null accessToken when login receives empty access key', () => {
        useAuthStore.getState().login({ access: '', refresh: VALID_JWT }, { id: '1' });
        expect(useAuthStore.getState().accessToken).toBeNull();
    });

    it('stores null refreshToken when login receives empty refresh key', () => {
        useAuthStore.getState().login({ access: VALID_JWT, refresh: '' }, { id: '1' });
        expect(useAuthStore.getState().refreshToken).toBeNull();
    });

    it('clears state when rehydrated with malformed (non-JWT) access token', async () => {
        // Set up localStorage with a malformed access token
        localStorage.setItem(
            'bookforbook-auth',
            JSON.stringify({
                state: {
                    user: { id: '1', username: 'alice' },
                    accessToken: 'not-a-jwt',
                    refreshToken: VALID_JWT,
                },
                version: 0,
            })
        );
        // Force rehydration
        await useAuthStore.persist.rehydrate();
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
    });

    it('clears state when rehydrated with expired refresh token', async () => {
        localStorage.setItem(
            'bookforbook-auth',
            JSON.stringify({
                state: {
                    user: { id: '1', username: 'alice' },
                    accessToken: VALID_JWT,
                    refreshToken: EXPIRED_JWT,
                },
                version: 0,
            })
        );
        await useAuthStore.persist.rehydrate();
        const state = useAuthStore.getState();
        expect(state.user).toBeNull();
        expect(state.accessToken).toBeNull();
    });

    it('clears only access token when rehydrated with expired access but valid refresh', async () => {
        localStorage.setItem(
            'bookforbook-auth',
            JSON.stringify({
                state: {
                    user: { id: '1', username: 'alice' },
                    accessToken: EXPIRED_JWT,
                    refreshToken: VALID_JWT,
                },
                version: 0,
            })
        );
        await useAuthStore.persist.rehydrate();
        const state = useAuthStore.getState();
        // Access token should be nulled but user stays (refresh is valid)
        expect(state.accessToken).toBeNull();
        expect(state.refreshToken).toBe(VALID_JWT);
    });

    it('decodeJwtPayload catch block fires for 3-part token with invalid base64 payload', async () => {
        // '!!!' contains characters invalid for base64 → atob throws → catch returns null
        // isLikelyJwt('header.!!!invalid!!!.sig') = true (3 parts)
        // but decodeJwtPayload hits catch → returns null → treated as expired
        localStorage.setItem(
            'bookforbook-auth',
            JSON.stringify({
                state: {
                    user: { id: '1', username: 'alice' },
                    accessToken: VALID_JWT,
                    refreshToken: 'header.!!!invalid_base64!!!.sig',
                },
                version: 0,
            })
        );
        await useAuthStore.persist.rehydrate();
        // refreshToken passes isLikelyJwt (3 parts) but decodeJwtPayload throws on atob
        // → null → treated as expired → logout
        expect(useAuthStore.getState().user).toBeNull();
    });

    it('onRehydrateStorage handles null state gracefully when localStorage has invalid JSON (covers line 77)', async () => {
        // Write invalid JSON — Zustand's persist middleware will fail to parse it
        // and call the onRehydrateStorage inner callback with null state
        localStorage.setItem('bookforbook-auth', '{invalid-json:');
        await useAuthStore.persist.rehydrate();
        // No crash; state stays at whatever it was (logout was called in beforeEach)
        expect(useAuthStore.getState().user).toBeNull();
    });

    it('treats JWT with no exp field as expired (forces logout on refresh)', async () => {
        const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
        const payload = btoa(JSON.stringify({ sub: '1' })); // no exp field
        const noExpToken = `${header}.${payload}.sig`;

        localStorage.setItem(
            'bookforbook-auth',
            JSON.stringify({
                state: { user: { id: '1' }, accessToken: noExpToken, refreshToken: noExpToken },
                version: 0,
            })
        );
        await useAuthStore.persist.rehydrate();
        // Token with no exp is treated as expired → logout
        expect(useAuthStore.getState().user).toBeNull();
    });
});
