import React, { useState } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import useAuth from '../../hooks/useAuth.js';
import { matches as matchesApi, proposals as proposalsApi } from '../../services/api.js';
import styles from './Navbar.module.css';

export default function Navbar() {
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Fetch pending counts for notification badge
  const { data: pendingMatches } = useQuery({
    queryKey: ['matches', 'pending-count'],
    queryFn: async () => {
      const res = await matchesApi.list({ status: 'pending', page_size: 1 });
      return res.data?.count ?? 0;
    },
    enabled: isAuthenticated,
    refetchInterval: 60_000, // refresh every minute
  });

  const { data: pendingProposals } = useQuery({
    queryKey: ['proposals', 'pending-count'],
    queryFn: async () => {
      const res = await proposalsApi.list({ status: 'pending', direction: 'received', page_size: 1 });
      return res.data?.count ?? 0;
    },
    enabled: isAuthenticated,
    refetchInterval: 60_000,
  });

  const totalPending = (pendingMatches ?? 0) + (pendingProposals ?? 0);

  function handleLogout() {
    logout();
    setMenuOpen(false);
    navigate('/');
  }

  function navLinkClass({ isActive }) {
    return isActive ? `${styles.navLink} ${styles.navLinkActive}` : styles.navLink;
  }

  return (
    <nav className={styles.navbar}>
      <div className={`container ${styles.navInner}`}>
        {/* Logo */}
        <Link to="/" className={styles.logo}>
          <span className={styles.logoIcon}>📚</span>
          <span className={styles.logoText}>BookForBook</span>
        </Link>

        {/* Desktop nav links */}
        <div className={styles.navLinks}>
          <NavLink to="/" end className={navLinkClass}>
            Browse
          </NavLink>
          <NavLink to="/institutions" className={navLinkClass}>
            Institutions
          </NavLink>
          {isAuthenticated && (
            <>
              <NavLink to="/my-books" className={navLinkClass}>
                My Books
              </NavLink>
              <NavLink to="/wishlist" className={navLinkClass}>
                Wishlist
              </NavLink>
              <NavLink to="/matches" className={navLinkClass}>
                Matches
                {totalPending > 0 && (
                  <span className={styles.badge}>{totalPending > 99 ? '99+' : totalPending}</span>
                )}
              </NavLink>
              <NavLink to="/trades" className={navLinkClass}>
                Trades
              </NavLink>
            </>
          )}
        </div>

        {/* Desktop auth area */}
        <div className={styles.authArea}>
          {isAuthenticated ? (
            <div className={styles.userMenu}>
              <button
                className={styles.userMenuButton}
                onClick={() => setMenuOpen((o) => !o)}
                aria-expanded={menuOpen}
                aria-haspopup="true"
              >
                <span className={styles.userAvatar}>
                  {user?.username?.[0]?.toUpperCase() ?? 'U'}
                </span>
                <span className={styles.username}>{user?.username ?? 'Account'}</span>
                <svg className={styles.chevron} viewBox="0 0 20 20" fill="currentColor" width="16" height="16">
                  <path fillRule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clipRule="evenodd" />
                </svg>
              </button>
              {menuOpen && (
                <>
                  <div className={styles.backdrop} onClick={() => setMenuOpen(false)} />
                  <div className={styles.dropdown}>
                    <Link
                      to="/dashboard"
                      className={styles.dropdownItem}
                      onClick={() => setMenuOpen(false)}
                    >
                      Dashboard
                    </Link>
                    <Link
                      to={`/profile/${user?.id}`}
                      className={styles.dropdownItem}
                      onClick={() => setMenuOpen(false)}
                    >
                      My Profile
                    </Link>
                    <Link
                      to="/proposals"
                      className={styles.dropdownItem}
                      onClick={() => setMenuOpen(false)}
                    >
                      Proposals
                    </Link>
                    <Link
                      to="/donations"
                      className={styles.dropdownItem}
                      onClick={() => setMenuOpen(false)}
                    >
                      Donations
                    </Link>
                    <hr className={styles.dropdownDivider} />
                    <button className={styles.dropdownItem} onClick={handleLogout}>
                      Sign out
                    </button>
                  </div>
                </>
              )}
            </div>
          ) : (
            <div className={styles.guestButtons}>
              <Link to="/login" className="btn btn-secondary btn-sm">
                Log in
              </Link>
              <Link to="/register" className="btn btn-primary btn-sm">
                Sign up
              </Link>
            </div>
          )}
        </div>

        {/* Mobile hamburger */}
        <button
          className={styles.hamburger}
          onClick={() => setMobileOpen((o) => !o)}
          aria-label="Toggle menu"
          aria-expanded={mobileOpen}
        >
          <span className={styles.hamburgerLine} />
          <span className={styles.hamburgerLine} />
          <span className={styles.hamburgerLine} />
        </button>
      </div>

      {/* Mobile menu */}
      {mobileOpen && (
        <div className={styles.mobileMenu}>
          <NavLink to="/" end className={navLinkClass} onClick={() => setMobileOpen(false)}>
            Browse
          </NavLink>
          <NavLink to="/institutions" className={navLinkClass} onClick={() => setMobileOpen(false)}>
            Institutions
          </NavLink>
          {isAuthenticated ? (
            <>
              <NavLink to="/dashboard" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Dashboard
              </NavLink>
              <NavLink to="/my-books" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                My Books
              </NavLink>
              <NavLink to="/wishlist" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Wishlist
              </NavLink>
              <NavLink to="/matches" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Matches {totalPending > 0 && `(${totalPending})`}
              </NavLink>
              <NavLink to="/proposals" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Proposals
              </NavLink>
              <NavLink to="/trades" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Trades
              </NavLink>
              <NavLink to="/donations" className={navLinkClass} onClick={() => setMobileOpen(false)}>
                Donations
              </NavLink>
              <NavLink to={`/profile/${user?.id}`} className={navLinkClass} onClick={() => setMobileOpen(false)}>
                My Profile
              </NavLink>
              <button
                className={`${styles.navLink} ${styles.mobileLogout}`}
                onClick={() => {
                  setMobileOpen(false);
                  handleLogout();
                }}
              >
                Sign out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className={styles.navLink} onClick={() => setMobileOpen(false)}>
                Log in
              </Link>
              <Link to="/register" className={styles.navLink} onClick={() => setMobileOpen(false)}>
                Sign up
              </Link>
            </>
          )}
        </div>
      )}
    </nav>
  );
}
