import { describe, expect, it } from 'vitest';

import { buildCounterPayload, mapProposalForCard } from './proposals.js';

describe('proposals adapter', () => {
  const proposal = {
    id: 'p1',
    proposer: { id: 'u2', username: 'alice' },
    recipient: { id: 'u1', username: 'me' },
    message: 'Interested?',
    items: [
      {
        direction: 'proposer_sends',
        user_book: {
          id: 'ub-a',
          condition: 'good',
          book: { title: 'The Dispossessed' },
        },
      },
      {
        direction: 'recipient_sends',
        user_book: {
          id: 'ub-b',
          condition: 'very_good',
          book: { title: 'Kindred' },
        },
      },
    ],
  };

  it('maps card books/conditions from proposal items', () => {
    const vm = mapProposalForCard(proposal, 'u1');

    expect(vm.offeredBook.title).toBe('The Dispossessed');
    expect(vm.requestedBook.title).toBe('Kindred');
    expect(vm.offeredCondition).toBe('good');
    expect(vm.requestedCondition).toBe('very_good');
    expect(vm.note).toBe('Interested?');
  });

  it('builds counter payload using swapped original item IDs', () => {
    const payload = buildCounterPayload(proposal, 'counter offer');

    expect(payload).toEqual({
      proposer_book_id: 'ub-b',
      recipient_book_id: 'ub-a',
      message: 'counter offer',
    });
  });
});
