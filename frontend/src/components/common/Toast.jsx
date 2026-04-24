import React from 'react';
import useNotificationStore from '../../hooks/useNotification.js';
import styles from './Toast.module.css';

/**
 * Toast component — displays a list of notifications at the top of the screen.
 */
export default function Toast() {
    const { notifications, removeNotification } = useNotificationStore();

    return (
        <div className={styles.container}>
            {notifications.map(({ id, message, type }) => (
                <div key={id} className={`${styles.toast} ${styles[type]}`} role="alert">
                    <div className={styles.content}>{message}</div>
                    <button
                        className={styles.closeButton}
                        onClick={() => removeNotification(id)}
                        aria-label="Close notification"
                    >
                        ✕
                    </button>
                </div>
            ))}
        </div>
    );
}
