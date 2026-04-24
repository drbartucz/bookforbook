/**
 * E2E Test Users
 *
 * These identities are created by the Django management command:
 *   python manage.py seed_e2e
 *
 * Password is the same for all e2e test users.
 */
export const E2E_PASSWORD = 'E2eTestPass1!';

export const ALICE = {
  email: 'alice@e2e.test',
  password: E2E_PASSWORD,
  username: 'alice_e2e',
  // Address-verified individual user.  Used for all flows requiring address.
};

export const BOB = {
  email: 'bob@e2e.test',
  password: E2E_PASSWORD,
  username: 'bob_e2e',
  // Address-verified individual user.  Trading partner for alice.
};

export const CAROL = {
  email: 'carol@e2e.test',
  password: E2E_PASSWORD,
  username: 'carol_e2e',
  // Individual user WITHOUT address verification.  Tests gating flows.
};

export const LIBRARY = {
  email: 'library@e2e.test',
  password: E2E_PASSWORD,
  username: 'library_e2e',
  // Institution account.  Tests donation flows.
};

/** ISBN that the backend has already seeded via seed_e2e. */
export const SEEDED_ISBN = '9780451524935'; // 1984 – George Orwell

/** Fake book data returned by the route-intercepted lookup call. */
export const MOCK_BOOK_LOOKUP = {
  isbn_13: '9780743273565',
  isbn_10: '0743273567',
  title: 'The Great Gatsby',
  authors: ['F. Scott Fitzgerald'],
  publish_year: 1925,
  physical_format: 'Paperback',
  cover_url: null,
};
