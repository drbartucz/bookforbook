import { describe, expect, it } from 'vitest';

import { buildTradeRatingPayload, mapTradeForView } from './trades.js';

describe('trades adapter', () => {
  it('maps shipment-derived fields for the current user', () => {
    const trade = {
      id: 't1',
      status: 'shipping',
      shipments: [
        {
          sender: { id: 'u1', username: 'me' },
          receiver: { id: 'u2', username: 'alice' },
          status: 'shipped',
          tracking_number: 'TRACK123',
          shipped_at: '2026-04-20T00:00:00Z',
          user_book: { condition: 'good', book: { title: 'Kindred' } },
        },
        {
          sender: { id: 'u2', username: 'alice' },
          receiver: { id: 'u1', username: 'me' },
          status: 'received',
          tracking_number: 'TRACK999',
          shipped_at: '2026-04-21T00:00:00Z',
          user_book: { condition: 'very_good', book: { title: 'Earthsea' } },
        },
      ],
      partner_addresses: {
        u2: {
          full_name: 'Alice Reader',
          address_line_1: '123 Main St',
          city: 'Denver',
          state: 'CO',
          zip_code: '80202',
        },
      },
    };

    const vm = mapTradeForView(trade, 'u1');

    expect(vm.partner.username).toBe('alice');
    expect(vm.myBook.book.title).toBe('Kindred');
    expect(vm.theirBook.book.title).toBe('Earthsea');
    expect(vm.myShipped).toBe(true);
    expect(vm.iReceived).toBe(true);
    expect(vm.partnerAddress.name).toBe('Alice Reader');
    expect(vm.partnerAddress.street).toBe('123 Main St');
  });

  it('builds backend-compatible rating payload', () => {
    const payload = buildTradeRatingPayload(
      { partner: { id: 'u2' } },
      { score: 5, comment: 'Great trade', bookConditionAccurate: true }
    );

    expect(payload).toEqual({
      rated_user_id: 'u2',
      score: 5,
      comment: 'Great trade',
      book_condition_accurate: true,
    });
  });
});
