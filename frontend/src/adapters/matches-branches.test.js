import { describe, expect, it } from 'vitest';
import { mapMatchForCard } from './matches.js';

describe('mapMatchForCard — branch coverage', () => {
    it('returns null yourBook/theirBook when legs array is empty', () => {
        const vm = mapMatchForCard({ id: 'm1', legs: [] }, 'u1');
        expect(vm.yourBook).toBeNull();
        expect(vm.theirBook).toBeNull();
        expect(vm.partner).toBeNull();
    });

    it('falls back to match.your_book when no outgoing leg matches', () => {
        const match = {
            id: 'm1',
            legs: [
                {
                    sender: { id: 'u2' },
                    receiver: { id: 'u3' },
                    user_book: { book: { title: 'Their Book' } },
                },
            ],
            your_book: { book: { title: 'Fallback Your Book' }, condition: 'good' },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.yourBook.title).toBe('Fallback Your Book');
    });

    it('falls back to match.offered_book when no your_book', () => {
        const match = {
            id: 'm1',
            legs: [],
            offered_book: { book: { title: 'Offered Book' } },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.yourBook.title).toBe('Offered Book');
    });

    it('falls back to match.their_book when no incoming leg matches', () => {
        const match = {
            id: 'm1',
            legs: [],
            their_book: { book: { title: 'Their Fallback' }, condition: 'acceptable' },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.theirBook.title).toBe('Their Fallback');
    });

    it('falls back to match.requested_book when no their_book', () => {
        const match = {
            id: 'm1',
            legs: [],
            requested_book: { book: { title: 'Requested Book' } },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.theirBook.title).toBe('Requested Book');
    });

    it('uses match.partner fallback when no legs', () => {
        const match = {
            id: 'm1',
            legs: [],
            partner: { id: 'p1', username: 'partner' },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.partner.username).toBe('partner');
    });

    it('uses match.other_user as secondary partner fallback', () => {
        const match = {
            id: 'm1',
            legs: [],
            other_user: { id: 'p2', username: 'other' },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.partner.username).toBe('other');
    });

    it('handles null/undefined match gracefully (no currentUserId)', () => {
        const vm = mapMatchForCard({ id: 'm1' }, null);
        expect(vm.yourBook).toBeNull();
        expect(vm.theirBook).toBeNull();
        expect(vm.partner).toBeNull();
    });

    it('returns outgoingLeg receiver as partner when no partner field', () => {
        const match = {
            id: 'm1',
            legs: [
                {
                    sender: { id: 'u1' },
                    receiver: { id: 'u2', username: 'alice' },
                    user_book: { book: { title: 'My Book' } },
                },
            ],
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.partner.username).toBe('alice');
    });

    it('returns incomingLeg sender as partner when no partner/other_user/outgoing receiver (covers line 22)', () => {
        const match = {
            id: 'm1',
            legs: [
                {
                    // Incoming leg for user u1 — receiver is u1, sender is someone else
                    sender: { id: 'u2', username: 'incoming-sender' },
                    receiver: { id: 'u1' },
                    user_book: { book: { title: 'Their Book' } },
                },
            ],
        };
        const vm = mapMatchForCard(match, 'u1');
        // outgoingLeg = undefined (no leg where sender.id === 'u1')
        // incomingLeg = leg above (receiver.id === 'u1')
        // partner chain falls through to incomingLeg?.sender (covers left side of ?? at line 22)
        expect(vm.partner.username).toBe('incoming-sender');
    });

    it('returns yourCondition from match.your_book when no outgoing leg', () => {
        const match = {
            id: 'm1',
            legs: [],
            your_book: { condition: 'very_good', book: { title: 'A' } },
        };
        const vm = mapMatchForCard(match, 'u1');
        expect(vm.yourCondition).toBe('very_good');
    });
});
