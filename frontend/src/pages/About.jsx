import React from 'react';
import * as Accordion from '@radix-ui/react-accordion';
import styles from './About.module.css';

const FAQ_DATA = [
  {
    id: 'how-it-works',
    question: 'How does BookForBook work?',
    answer: 'BookForBook is a free book swap platform. You list the books you have and the books you want. Our system automatically matches you with a complementary trade. If you both accept the trade, your addresses are shared. Once you ship the item, you can enter a tracking number for verification. When the items are received, you rate the other user and your addresses disappear!'
  },
  {
    id: 'shipping',
    question: 'How does shipping work?',
    answer: 'Once a trade is confirmed, you will receive the shipping address of your trade partner. You are responsible for shipping your book to them, and in return, someone will ship a book to you. We recommend using USPS Media Mail for cost-effective shipping within the US. You can also use UPS or Fedex and enter those tracking numbers.'
  },
  {
    id: 'is-it-free',
    question: 'Is it free to use?',
    answer: 'Yes! BookForBook is free to use. You only pay for the cost of shipping the books you send to others. There are no subscription fees or per-trade charges.'
  },
  {
    id: 'safety',
    question: 'Is my personal information safe?',
    answer: 'We take privacy seriously. Your shipping address is encrypted in our database and is only revealed to your confirmed trade partner once a trade is agreed upon. Once the trade is complete, the other user can no longer see your address. No other personal information is gathered and we will never share any information with other parties. If you are concered about revealing your home address, we  recommend using a P.O. Box or a work address.'
  },
  {
    id: 'condition',
    question: 'What should be the condition of the books?',
    answer: 'We expect all books to be in "Good" or better condition—meaning no missing pages, excessive highlighting, or significant water damage. Please be honest about the condition of your books when listing them.'
  }
];

export default function About() {
  return (
    <div className={styles.container}>
      <header className={styles.hero}>
        <h1 className={styles.title}>About BookForBook</h1>
        <p className={styles.subtitle}>
          Connecting book lovers one swap at a time.
        </p>
      </header>

      <section className={styles.section}>
        <div className={styles.grid}>
          <div className={styles.card}>
            <span className={styles.icon} aria-hidden="true">🌱</span>
            <h3>Sustainable</h3>
            <p>Give your books a second life and reduce waste!</p>
          </div>
          <div className={styles.card}>
            <span className={styles.icon} aria-hidden="true">🤝</span>
            <h3>Connections</h3>
            <p>Send a personal note with your book. Tell them why you loved it and/or are letting it go...</p>
          </div>
          <div className={styles.card}>
            <span className={styles.icon} aria-hidden="true">💰</span>
            <h3>Cost-Effective</h3>
            <p>Get new-to-you books for just the price of shipping.</p>
          </div>
        </div>
      </section>

      <section className={styles.faqSection}>
        <h2 className={styles.faqTitle}>Frequently Asked Questions</h2>
        <Accordion.Root type="single" collapsible className={styles.accordionRoot}>
          {FAQ_DATA.map((item) => (
            <Accordion.Item key={item.id} value={item.id} className={styles.accordionItem}>
              <Accordion.Header className={styles.accordionHeader}>
                <Accordion.Trigger className={styles.accordionTrigger}>
                  <span>{item.question}</span>
                  <svg
                    className={styles.chevron}
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    aria-hidden="true"
                  >
                    <polyline points="6 9 12 15 18 9"></polyline>
                  </svg>
                </Accordion.Trigger>
              </Accordion.Header>
              <Accordion.Content className={styles.accordionContent}>
                <div className={styles.accordionContentInner}>
                  {item.answer}
                </div>
              </Accordion.Content>
            </Accordion.Item>
          ))}
        </Accordion.Root>
      </section>
    </div>
  );
}
