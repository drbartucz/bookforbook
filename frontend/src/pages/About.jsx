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
    id: 'discover',
    question: 'What if I don\'t know what books I want?',
    answer: 'Once you list books you have, you can go to the "Discover" tab and it will show all the books being offered by people who want something you have!'
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
  },
  {
    id: 'feedback',
    question: 'Questions? Comments? Suggestions?',
    answer: 'Please visit the contact page and we will get back to you asap.'
  }
];

export default function About() {
  return (
    <div className={styles.container}>
      <header className={styles.hero}>
        <h1 className={styles.title}>About BookForBook</h1>
        <p className={styles.subtitle}>A free platform for swapping books you've read for books you want to read — for just the price of shipping.</p>
      </header>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>How It Works</h2>
        <ol className={styles.stepsList}>
          <li>Create an account and verify your address.</li>
          <li>List the books you have and the books you want.</li>
          <li>If you don't get a match right away, browse the "Discover" tab to find books offered by people that already want what you have.</li>
          <li>When you get a match, you can accept or reject the trade. If you both accept, your addresses are shared and you can ship your book to your trade partner.</li>
          <li>Once you ship your book, please enter a tracking number for verification.</li>
          <li>When you receive your book, mark the trade as "received".</li>
          <li>Finally, rate your trade partner and leave feedback for the community! The more positive reviews you receive, the more books you can trade at once!</li>
        </ol>
      </section>

      <section className={styles.section}>
        <h2 className={styles.sectionTitle}>Why BookForBook?</h2>
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
