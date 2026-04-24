/**
 * page-objects/MyBooksPage.js
 */
export class MyBooksPage {
  constructor(page) {
    this.page = page;
    this.heading = page.getByRole('heading', { name: /my books/i });
    this.addBookButton = page.getByRole('button', { name: /\+ add book|add book/i });
    this.isbnInput = page.getByPlaceholder(/isbn/i);
    this.lookupButton = page.getByRole('button', { name: /look up/i });
    this.conditionSelect = page.getByRole('combobox', { name: /condition/i });
    this.addSubmitButton = page.getByRole('button', { name: /^add$/i });
    this.cancelButton = page.getByRole('button', { name: /cancel/i });
    this.errorAlert = page.locator('.alert-error');
  }

  async goto() {
    await this.page.goto('/my-books');
  }

  async openAddForm() {
    await this.addBookButton.click();
  }

  /**
   * Look up a book by ISBN.  The caller should mock the /books/lookup/ route
   * before calling this to avoid network calls to Open Library.
   */
  async lookupIsbn(isbn) {
    await this.isbnInput.fill(isbn);
    await this.lookupButton.click();
  }

  /** Complete the add-book form after a successful lookup. */
  async submitAddBook(condition = 'good') {
    if (condition !== 'good') {
      await this.conditionSelect.selectOption(condition);
    }
    await this.addSubmitButton.click();
  }

  /** Click the Remove button for the first book matching the title. */
  async removeBook(title) {
    const card = this.page.locator('[class*="bookCard"], [class*="bookItem"]').filter({
      hasText: title,
    });
    await card.getByRole('button', { name: /remove/i }).click();
  }

  /** Click the Edit button for the book matching the title. */
  async editBook(title) {
    const card = this.page.locator('[class*="bookCard"], [class*="bookItem"]').filter({
      hasText: title,
    });
    await card.getByRole('button', { name: /edit/i }).click();
  }

  /** Save the currently-open edit form. */
  async saveEdit() {
    await this.page.getByRole('button', { name: /save/i }).click();
  }
}
