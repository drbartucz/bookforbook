/**
 * page-objects/AuthPage.js
 *
 * Encapsulates selectors and actions for the Login and Register pages.
 */
export class LoginPage {
  constructor(page) {
    this.page = page;
    this.emailInput = page.getByLabel('Email address');
    this.passwordInput = page.getByLabel('Password');
    this.submitButton = page.getByRole('button', { name: /sign in/i });
    this.forgotPasswordLink = page.getByRole('link', { name: /forgot password/i });
    this.registerLink = page.getByRole('link', { name: /create.*account|sign up|register/i });
    this.errorAlert = page.locator('.alert-error');
  }

  async goto() {
    await this.page.goto('/login');
  }

  async login(email, password) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}

export class RegisterPage {
  constructor(page) {
    this.page = page;
    this.emailInput = page.getByLabel('Email address');
    this.usernameInput = page.getByLabel('Username');
    this.passwordInput = page.getByLabel(/^Password$/, { exact: false });
    this.confirmPasswordInput = page.getByLabel(/confirm password/i);
    this.submitButton = page.getByRole('button', { name: /create account|register/i });
    this.errorAlert = page.locator('.alert-error');
    this.successBox = page.getByText(/Please check your email/i);
  }

  async goto() {
    await this.page.goto('/register');
  }

  async register({ email, username, password, accountType = 'individual' }) {
    // Select account type radio
    await this.page
      .getByRole('radio', { name: new RegExp(accountType, 'i') })
      .click();
    await this.emailInput.fill(email);
    await this.usernameInput.fill(username);
    await this.passwordInput.fill(password);
    await this.confirmPasswordInput.fill(password);
    await this.submitButton.click();
  }
}
