import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from './Navbar.jsx';
import styles from './Layout.module.css';

export default function Layout() {
  return (
    <div className={styles.layoutRoot}>
      <Navbar />
      <main className={styles.main}>
        <div className="container">
          <Outlet />
        </div>
      </main>
      <footer className={styles.footer}>
        <div className="container">
          <p className={styles.footerText}>
            &copy; {new Date().getFullYear()} BookForBook &mdash; Trade books 1-for-1, no money needed.
          </p>
        </div>
      </footer>
    </div>
  );
}
