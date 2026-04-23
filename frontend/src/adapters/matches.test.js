import { describe, expect, it } from 'vitest';

import { mapMatchForCard } from './matches.js';

describe('matches adapter', () => {
  it('maps books and partner from legs for the current user', () => {
    const match = {
      id: 'm1',
      status: 'pending',
      legs: [
        {
          sender: { id: 'u1', username: 'me' },
          receiver: { id: 'u2', username: 'alice' },
          user_book: { condition: 'good', book: { title: 'Kindred' } },
        },
        {
          sender: { id: 'u2', username: 'alice' },
          receiver: { id: 'u1', username: 'me' },
          user_book: { condition: 'very_good', book: { title: 'Earthsea' } },
        },
      ],
    };

    const vm = mapMatchForCard(match, 'u1');

    expect(vm.yourBook.title).toBe('Kindred');
    expect(vm.theirBook.title).toBe('Earthsea');
    expect(vm.yourCondition).toBe('good');
    expect(vm.theirCondition).toBe('very_good');
    expect(vm.partner.username).toBe('alice');
  });
});
