import React from 'react';

export default class AppErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError() {
        return { hasError: true };
    }

    componentDidCatch(error, info) {
        console.error('[AppErrorBoundary]', error, info);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div role="alert" style={{ padding: '2rem', textAlign: 'center' }}>
                    <h2>Something went wrong.</h2>
                    <p>Please refresh the page. If the problem persists, contact support.</p>
                    <button onClick={() => this.setState({ hasError: false })}>
                        Try again
                    </button>
                </div>
            );
        }
        return this.props.children;
    }
}
