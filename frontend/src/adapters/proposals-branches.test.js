import { describe, expect, it } from 'vitest';
import { buildCounterPayload, mapProposalForCard } from './proposals.js';

describe('mapProposalForCard — branch coverage', () => {
    it('handles missing items array (no items field)', () => {
        const proposal = { id: 'p1', proposer: { id: 'u1' } };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.offeredBook).toBeNull();
        expect(vm.requestedBook).toBeNull();
        expect(vm.isMine).toBe(true);
    });

    it('handles null items field', () => {
        const proposal = { id: 'p1', proposer: { id: 'u2' }, items: null };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.offeredBook).toBeNull();
        expect(vm.isMine).toBe(false);
    });

    it('falls back to proposal.offered_book when proposerSends has no user_book', () => {
        const proposal = {
            id: 'p1',
            proposer: { id: 'u1' },
            items: [],
            offered_book: { book: { title: 'Offered Fallback' } },
        };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.offeredBook.title).toBe('Offered Fallback');
    });

    it('falls back to proposal.requested_book when recipientSends has no user_book', () => {
        const proposal = {
            id: 'p1',
            proposer: { id: 'u1' },
            items: [],
            requested_book: { book: { title: 'Requested Fallback' } },
        };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.requestedBook.title).toBe('Requested Fallback');
    });

    it('uses offeredBook directly when no nested .book', () => {
        const proposal = {
            id: 'p1',
            proposer: { id: 'u1' },
            items: [
                { direction: 'proposer_sends', user_book: { title: 'Flat Book', condition: 'good' } },
            ],
        };
        const vm = mapProposalForCard(proposal, 'u1');
        // offered = proposerSends.user_book (no .book sub-key) → falls to offered itself
        expect(vm.offeredBook).toEqual({ title: 'Flat Book', condition: 'good' });
    });

    it('prefers proposal.message over proposal.note', () => {
        const proposal = {
            id: 'p1',
            proposer: { id: 'u1' },
            items: [],
            message: 'the message',
            note: 'the note',
        };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.note).toBe('the message');
    });

    it('falls back to proposal.note when message is absent', () => {
        const proposal = {
            id: 'p1',
            proposer: { id: 'u1' },
            items: [],
            note: 'the note',
        };
        const vm = mapProposalForCard(proposal, 'u1');
        expect(vm.note).toBe('the note');
    });
});

describe('buildCounterPayload — branch coverage', () => {
    it('returns null when proposerBookId is missing', () => {
        const proposal = {
            items: [
                { direction: 'proposer_sends', user_book: { id: 'b1' } },
                // no recipient_sends item
            ],
        };
        expect(buildCounterPayload(proposal)).toBeNull();
    });

    it('returns null when recipientBookId is missing', () => {
        const proposal = {
            items: [
                // no proposer_sends item
                { direction: 'recipient_sends', user_book: { id: 'b2' } },
            ],
        };
        expect(buildCounterPayload(proposal)).toBeNull();
    });

    it('returns null when items is not an array', () => {
        expect(buildCounterPayload({ items: null })).toBeNull();
    });

    it('uses user_book id when id is a string', () => {
        const proposal = {
            items: [
                { direction: 'proposer_sends', user_book: { id: 'bA' } },
                { direction: 'recipient_sends', user_book: { id: 'bB' } },
            ],
        };
        // The payload swaps directions: proposerBookId = recipientSends, recipientBookId = proposerSends
        const payload = buildCounterPayload(proposal, 'hi there');
        expect(payload.proposer_book_id).toBe('bB');
        expect(payload.recipient_book_id).toBe('bA');
        expect(payload.message).toBe('hi there');
    });

    it('uses the user_book object directly when it has no id field', () => {
        const proposal = {
            items: [
                { direction: 'proposer_sends', user_book: 'rawIdA' },
                { direction: 'recipient_sends', user_book: 'rawIdB' },
            ],
        };
        const payload = buildCounterPayload(proposal);
        expect(payload.proposer_book_id).toBe('rawIdB');
        expect(payload.recipient_book_id).toBe('rawIdA');
    });
});
