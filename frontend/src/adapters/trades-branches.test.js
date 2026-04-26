import { describe, expect, it } from 'vitest';
import { buildTradeRatingPayload, mapTradeForView } from './trades.js';

describe('mapTradeForView — branch coverage', () => {
    it('handles missing shipments array gracefully', () => {
        const vm = mapTradeForView({ id: 't1' }, 'u1');
        expect(vm.myOutgoing).toBeFalsy();   // undefined from empty Array.find
        expect(vm.myIncoming).toBeFalsy();
        expect(vm.partner).toBeNull();
        expect(vm.partnerAddress).toBeNull();
    });

    it('uses trade.partner fallback when no shipments match', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], partner: { id: 'p1', username: 'alice' } },
            'u1'
        );
        expect(vm.partner.username).toBe('alice');
    });

    it('uses trade.other_user as secondary partner fallback', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], other_user: { id: 'p2', username: 'bob' } },
            'u1'
        );
        expect(vm.partner.username).toBe('bob');
    });

    it('uses myOutgoing.receiver as partner when no trade.partner', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [
                    {
                        sender: { id: 'u1' },
                        receiver: { id: 'u2', username: 'carol' },
                        status: 'pending',
                        user_book: {},
                    },
                ],
            },
            'u1'
        );
        expect(vm.partner.username).toBe('carol');
    });

    it('uses myIncoming.sender as partner when no outgoing shipment', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [
                    {
                        sender: { id: 'u2', username: 'dave' },
                        receiver: { id: 'u1' },
                        status: 'pending',
                        user_book: {},
                    },
                ],
            },
            'u1'
        );
        expect(vm.partner.username).toBe('dave');
    });

    it('returns null partnerAddress when partner has no id', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], partner: null },
            'u1'
        );
        expect(vm.partnerAddress).toBeNull();
    });

    it('returns null partnerAddress when partner_addresses does not include partner', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                partner: { id: 'u2' },
                partner_addresses: {},
            },
            'u1'
        );
        expect(vm.partnerAddress).toBeNull();
    });

    it('uses partnerAddressRaw.institution_name as name fallback', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                partner: { id: 'u2' },
                partner_addresses: {
                    u2: { institution_name: 'City Library', address_line_1: '1 Ave', city: 'Portland', state: 'OR', zip_code: '97201' },
                },
            },
            'u1'
        );
        expect(vm.partnerAddress.name).toBe('City Library');
    });

    it('falls back to trade.my_book when no myOutgoing', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                my_book: { book: { title: 'My Fallback Book' } },
            },
            'u1'
        );
        expect(vm.myBook.book.title).toBe('My Fallback Book');
    });

    it('falls back to trade.initiator_book when no my_book', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                initiator_book: { book: { title: 'Initiator' } },
            },
            'u1'
        );
        expect(vm.myBook.book.title).toBe('Initiator');
    });

    it('falls back to trade.their_book when no myIncoming', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                their_book: { book: { title: 'Their Fallback' } },
            },
            'u1'
        );
        expect(vm.theirBook.book.title).toBe('Their Fallback');
    });

    it('falls back to trade.responder_book when no their_book', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                responder_book: { book: { title: 'Responder' } },
            },
            'u1'
        );
        expect(vm.theirBook.book.title).toBe('Responder');
    });

    it('uses Boolean(trade.my_shipped) fallback when no myOutgoing', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], my_shipped: true },
            'u1'
        );
        expect(vm.myShipped).toBe(true);
    });

    it('uses Boolean(trade.i_received) fallback when no myIncoming', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], i_received: true },
            'u1'
        );
        expect(vm.iReceived).toBe(true);
    });

    it('uses Boolean(trade.they_shipped) fallback when no myIncoming', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], they_shipped: true },
            'u1'
        );
        expect(vm.theyShipped).toBe(true);
    });

    it('uses Boolean(trade.they_received) fallback when no myOutgoing', () => {
        const vm = mapTradeForView(
            { id: 't1', shipments: [], they_received: true },
            'u1'
        );
        expect(vm.theyReceived).toBe(true);
    });

    it('handles null currentUserId (no shipment matching)', () => {
        const vm = mapTradeForView({ id: 't1', shipments: [] }, null);
        expect(vm.myOutgoing).toBeNull();
        expect(vm.myIncoming).toBeNull();
    });
});

    it('builds partnerAddress with full_name, address_line_2, and empty city/state (covers lines 37,39 left and 40,41 right)', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                partner: { id: 'u2' },
                partner_addresses: {
                    u2: {
                        full_name: 'Jane Doe',    // covers line 37 left branch (full_name truthy)
                        address_line_1: '123 Main',
                        address_line_2: 'Suite 4', // covers line 39 left branch (address_line_2 truthy)
                        city: '',                  // empty → covers line 40 right branch ("" fallback)
                        state: '',                 // empty → covers line 41 right branch ("" fallback)
                        zip_code: '97201',
                    },
                },
            },
            'u1'
        );
        expect(vm.partnerAddress.name).toBe('Jane Doe');
        expect(vm.partnerAddress.street2).toBe('Suite 4');
        expect(vm.partnerAddress.city).toBe('');
        expect(vm.partnerAddress.state).toBe('');
    });

    it('builds partnerAddress with no name fields (covers line 36 || "" right branch)', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                partner: { id: 'u2' },
                partner_addresses: {
                    u2: {
                        // No full_name, no institution_name → covers || "" fallback at line 36
                        address_line_1: '1 Ave',
                        city: 'Portland',
                        state: 'OR',
                        zip_code: '97201',
                    },
                },
            },
            'u1'
        );
        expect(vm.partnerAddress.name).toBe('');
    });

    it('builds partnerAddress with no address_line_1 and no zip_code (covers lines 37, 41 right branches)', () => {
        const vm = mapTradeForView(
            {
                id: 't1',
                shipments: [],
                partner: { id: 'u2' },
                partner_addresses: {
                    u2: {
                        institution_name: 'No Street Library',
                        // No address_line_1 → line 37: undefined || "" → "" (right branch)
                        city: 'Portland',
                        state: 'OR',
                        // No zip_code → line 41: undefined || "" → "" (right branch)
                    },
                },
            },
            'u1'
        );
        expect(vm.partnerAddress.street).toBe('');
        expect(vm.partnerAddress.zip).toBe('');
    });

describe('buildTradeRatingPayload — branch coverage', () => {
    it('returns null when tradeView has no partner', () => {
        expect(buildTradeRatingPayload({}, {})).toBeNull();
        expect(buildTradeRatingPayload(null, {})).toBeNull();
    });

    it('uses empty string for missing comment', () => {
        const payload = buildTradeRatingPayload(
            { partner: { id: 'u2' } },
            { score: 4, bookConditionAccurate: false }
        );
        expect(payload.comment).toBe('');
    });
});
