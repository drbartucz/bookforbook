import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';

import useNotificationStore from './useNotification.js';

describe('useNotificationStore', () => {
  beforeEach(() => {
    useNotificationStore.setState({ notifications: [] });
  });

  it('starts with empty notifications', () => {
    const { result } = renderHook(() => useNotificationStore());
    expect(result.current.notifications).toEqual([]);
  });

  it('adds a notification with a unique id', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.addNotification('Test message', 'info');
    });

    expect(result.current.notifications).toHaveLength(1);
    expect(result.current.notifications[0]).toMatchObject({
      message: 'Test message',
      type: 'info',
    });
    expect(result.current.notifications[0].id).toBeDefined();
  });

  it('removes a notification by id', () => {
    const { result } = renderHook(() => useNotificationStore());

    let id;
    act(() => {
      id = result.current.addNotification('Test message', 'info');
    });

    expect(result.current.notifications).toHaveLength(1);

    act(() => {
      result.current.removeNotification(id);
    });

    expect(result.current.notifications).toHaveLength(0);
  });

  it('auto-removes notification after duration (default 5000ms)', async () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.addNotification('Auto-remove message', 'success', 100); // 100ms for testing
    });

    expect(result.current.notifications).toHaveLength(1);

    // Wait for auto-remove
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(result.current.notifications).toHaveLength(0);
  });

  it('does not auto-remove notification when duration is 0', async () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.addNotification('Persistent message', 'info', 0);
    });

    expect(result.current.notifications).toHaveLength(1);

    // Wait to verify it doesn't auto-remove
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(result.current.notifications).toHaveLength(1);
  });

  it('supports multiple simultaneous notifications', () => {
    const { result } = renderHook(() => useNotificationStore());

    act(() => {
      result.current.addNotification('Message 1', 'info');
      result.current.addNotification('Message 2', 'success');
      result.current.addNotification('Message 3', 'error');
    });

    expect(result.current.notifications).toHaveLength(3);
  });
});
