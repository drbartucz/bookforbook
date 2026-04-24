/**
 * page-objects/MatchesPage.js
 */
export class MatchesPage {
  constructor(page) {
    this.page = page;
    this.heading = page.getByRole('heading', { name: /matches/i });
    this.pendingTab = page.getByRole('button', { name: /^pending$/i });
    this.acceptedTab = page.getByRole('button', { name: /^accepted$/i });
    this.declinedTab = page.getByRole('button', { name: /^declined$/i });
    this.allTab = page.getByRole('button', { name: /^all$/i });
    this.errorAlert = page.locator('.alert-error');
  }

  async goto() {
    await this.page.goto('/matches');
  }

  matchCard(titleFragment) {
    return this.page
      .locator('[class*="matchCard"], [class*="card"]')
      .filter({ hasText: titleFragment });
  }

  async acceptFirstMatch() {
    await this.page
      .getByRole('button', { name: /accept/i })
      .first()
      .click();
  }

  async declineFirstMatch() {
    await this.page
      .getByRole('button', { name: /decline/i })
      .first()
      .click();
  }

  async switchTab(tabName) {
    await this.page.getByRole('button', { name: new RegExp(`^${tabName}$`, 'i') }).click();
  }
}
