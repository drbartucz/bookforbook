import React from 'react';
import { Link } from 'react-router-dom';

export default function NotFound() {
    return (
        <section className="card" style={{ padding: '2rem', textAlign: 'center' }}>
            <p className="badge badge-gray" style={{ marginBottom: '0.75rem' }}>404</p>
            <h1 className="page-title" style={{ marginBottom: '0.5rem' }}>Page not found</h1>
            <p className="page-subtitle" style={{ marginBottom: '1.5rem' }}>
                The page you are looking for does not exist or may have moved.
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <Link to="/" className="btn btn-primary">Go home</Link>
                <Link to="/dashboard" className="btn btn-secondary">Go to dashboard</Link>
            </div>
        </section>
    );
}
