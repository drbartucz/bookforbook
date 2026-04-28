import React, { useState, useEffect } from 'react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import useAuth from '../../hooks/useAuth.js';
import { notifications as notificationsApi } from '../../services/api.js';
import Tooltip from '../common/Tooltip.jsx';
import styles from './Navbar.module.css';

export default function Navbar() {
  const queryClient = useQueryClient();
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // Fetch consolidated pending counts for navbar badges.
  const { data: pendingCounts } = useQuery({
    queryKey: ['notifications', 'counts'],
    queryFn: async () => {
      const res = await notificationsApi.counts();
      return res.data ?? {};
    },
    enabled: isAuthenticated,
    refetchInterval: 60_000, // refresh every minute
  });

  const { data: notificationsData } = useQuery({
    queryKey: ['notifications', 'recent'],
    queryFn: async () => {
      const res = await notificationsApi.list({ page: 1, page_size: 5 });
      return res.data ?? {};
    },
    enabled: isAuthenticated && notificationsOpen,
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications', 'counts'] });
      queryClient.invalidateQueries({ queryKey: ['notifications', 'recent'] });
    },
  });

  const totalPending = pendingCounts?.total_pending ?? 0;
  const unreadNotifications = pendingCounts?.unread_notifications ?? 0;
  const recentNotifications = Array.isArray(notificationsData)
    ? notificationsData
    : (notificationsData?.results ?? []);

  useEffect(() => {
    function handleKeyDown(e) {
      if (e.key === 'Escape') {
        setMenuOpen(false);
        setNotificationsOpen(false);
      }
    }
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  function handleLogout() {
    logout();
    setMenuOpen(false);
    setNotificationsOpen(false);
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
                  <Tooltip content={`${totalPending} match${totalPending === 1 ? '' : 'es'} waiting for your response.`} position="bottom">
                    <span className={styles.badge}>{totalPending > 99 ? '99+' : totalPending}</span>
                  </Tooltip>
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
            <div className={styles.authActions}>
              <div className={styles.notificationsMenu}>
                <button
                  className={styles.notificationsButton}
                  onClick={() => {
                    setNotificationsOpen((o) => !o);
                    setMenuOpen(false);
                  }}
                  aria-expanded={notificationsOpen}
                  aria-haspopup="true"
                  aria-label="Notifications"
                >
                  <svg viewBox="0 0 20 20" fill="currentColor" width="18" height="18" aria-hidden="true">
                    <path d="M10 2.5a4.75 4.75 0 00-4.75 4.75v2.035c0 .796-.316 1.559-.879 2.121L3.78 12a1.5 1.5 0 001.06 2.56h10.32A1.5 1.5 0 0016.22 12l-.59-.59a3 3 0 01-.88-2.12V7.25A4.75 4.75 0 0010 2.5z" />
                    <path d="M7.75 15.5a2.25 2.25 0 004.5 0h-4.5z" />
                  </svg>
                  {unreadNotifications > 0 && (
                    <Tooltip content={`${unreadNotifications} unread notification${unreadNotifications === 1 ? '' : 's'}.`} position="bottom">
                      <span className={styles.notificationsBadge}>
                        {unreadNotifications > 99 ? '99+' : unreadNotifications}
                      </span>
                    </Tooltip>
                  )}
                </button>

                {notificationsOpen && (
                  <div className={styles.notificationsDropdown}>
                    <div className={styles.notificationsHeader}>
                      <span>Notifications</span>
                      <button
                        className={styles.dropdownItem}
                        onClick={() => markAllReadMutation.mutate()}
                        disabled={markAllReadMutation.isPending}
                        type="button"
                      >
                        {markAllReadMutation.isPending ? 'Marking...' : 'Mark all read'}
                      </button>
                    </div>
                    <div className={styles.notificationsList}>
                      {recentNotifications.length === 0 ? (
                        <p className={styles.emptyNotifications}>No notifications yet.</p>
                      ) : (
                        recentNotifications.map((n) => (
                          <div key={n.id} className={styles.notificationItem}>
                            <p className={styles.notificationTitle}>{n.title}</p>
                            {n.body && <p className={styles.notificationBody}>{n.body}</p>}
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>

              <div className={styles.userMenu}>
                <button
                  className={styles.userMenuButton}
                  onClick={() => {
                    setMenuOpen((o) => !o);
                    setNotificationsOpen(false);
                  }}
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
                  <div className={styles.dropdown}>
                    <Link
                      to="/dashboard"
                      className={styles.dropdownItem}
                      onClick={() => setMenuOpen(false)}
                    >
                      Dashboard
                    </Link>
                    <Link
                      to="/account"
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
                )}
              </div>
              {(menuOpen || notificationsOpen) && (
                <div className={styles.backdrop} onClick={() => {
                  setMenuOpen(false);
                  setNotificationsOpen(false);
                }} />
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
              <NavLink to="/account" className={navLinkClass} onClick={() => setMobileOpen(false)}>
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
