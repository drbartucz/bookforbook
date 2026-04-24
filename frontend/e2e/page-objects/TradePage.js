/**
 * page-objects/TradePage.js
 *
 * Page object for /trades/:id (TradeDetail)
 */
export class TradePage {
  constructor(page) {
    this.page = page;
    this.markShippedButton = page.getByRole('button', { name: /mark as shipped|mark shipped/i });
    this.markReceivedButton = page.getByRole('button', { name: /mark.*received/i });
    this.rateButton = page.getByRole('button', { name: /rate.*trade|leave.*rating|submit rating/i });
    this.trackingInput = page.getByPlaceholder(/tracking/i);
    this.confirmShipButton = page.getByRole('button', { name: /confirm.*ship|submit.*ship/i });
    this.sendMessageButton = page.getByRole('button', { name: /send message|send/i });
    this.messageTextarea = page.getByPlaceholder(/message|write a note/i);
    this.errorAlert = page.locator('.alert-error');
  }

  async goto(tradeId) {
    await this.page.goto(`/trades/${tradeId}`);
  }

  async markShipped(trackingNumber = 'USPS12345678') {
    await this.markShippedButton.click();
    if (await this.trackingInput.isVisible()) {
      await this.trackingInput.fill(trackingNumber);
    }
    await this.confirmShipButton.click();
  }

  async markReceived() {
    await this.markReceivedButton.click();
  }

  async submitRating(score = 5, comment = 'Great trade!') {
    await this.rateButton.click();
    // Star rating selector — look for the star radio/button with the right value
    const starInput = this.page
      .getByRole('radio', { name: new RegExp(`${score}.*star`, 'i') })
      .or(this.page.locator(`[data-rating="${score}"], [aria-label="${score} stars"]`));
    if (await starInput.count()) {
      await starInput.first().click();
    }
    const commentField = this.page.getByPlaceholder(/comment|feedback/i).or(
      this.page.getByLabel(/comment/i)
    );
    if (await commentField.isVisible()) {
      await commentField.fill(comment);
    }
    await this.page.getByRole('button', { name: /submit rating|rate/i }).last().click();
  }

  async sendMessage(content) {
    await this.messageTextarea.fill(content);
    await this.sendMessageButton.click();
  }
}
