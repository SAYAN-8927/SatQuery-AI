import { useState, useEffect, useRef, useCallback } from 'react';
import { checkHealth, type HealthResponse } from './api';

export type BackendHealthStatus = 'checking' | 'waking' | 'online' | 'unavailable' | 'disconnected';

export interface UseBackendHealthReturn {
  backendOnline: boolean;
  backendStatus: BackendHealthStatus;
  vlmEnabled?: boolean;
  retryConnection: () => void;
}

// Bounded retry schedule with increasing delays (Task 4):
// Attempt 1: 3s, Attempt 2: 5s, Attempt 3: 8s, Attempt 4: 10s, Attempt 5: 12s, Attempt 6+: 15s
const RETRY_DELAYS_MS = [3000, 5000, 8000, 10000, 12000, 15000];
const MAX_RETRY_DURATION_MS = 180000; // 3-minute window for Render cold start

export function useBackendHealth(): UseBackendHealthReturn {
  const [backendOnline, setBackendOnline] = useState<boolean>(false);
  const [backendStatus, setBackendStatus] = useState<BackendHealthStatus>('checking');
  const [vlmEnabled, setVlmEnabled] = useState<boolean | undefined>(undefined);

  const attemptCountRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inFlightRef = useRef<boolean>(false);
  const isMountedRef = useRef<boolean>(true);

  const clearPendingTimer = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const getNextDelay = (attempt: number): number => {
    const idx = Math.min(attempt, RETRY_DELAYS_MS.length - 1);
    return RETRY_DELAYS_MS[idx];
  };

  const executeHealthCheck = useCallback(async () => {
    if (inFlightRef.current || !isMountedRef.current) return;
    inFlightRef.current = true;

    try {
      const health: HealthResponse = await checkHealth(10000);
      if (!isMountedRef.current) return;

      if (health && health.status === 'ok') {
        setBackendOnline(true);
        setBackendStatus('online');
        if (health.vlm_enabled !== undefined) {
          setVlmEnabled(health.vlm_enabled);
        }
        clearPendingTimer();
        return;
      }
      throw new Error(`Unexpected health payload: ${JSON.stringify(health)}`);
    } catch {
      if (!isMountedRef.current) return;

      const elapsed = Date.now() - startTimeRef.current;
      if (elapsed >= MAX_RETRY_DURATION_MS) {
        // Exceeded bounded retry window (3 minutes)
        setBackendOnline(false);
        setBackendStatus('unavailable');
        clearPendingTimer();
      } else {
        // Cold start in progress — transition to 'waking' and schedule next attempt with increasing delay
        setBackendOnline(false);
        setBackendStatus('waking');
        clearPendingTimer();

        const delay = getNextDelay(attemptCountRef.current);
        attemptCountRef.current += 1;

        timerRef.current = setTimeout(() => {
          executeHealthCheck();
        }, delay);
      }
    } finally {
      inFlightRef.current = false;
    }
  }, []);

  const retryConnection = useCallback(() => {
    clearPendingTimer();
    startTimeRef.current = Date.now();
    attemptCountRef.current = 0;
    setBackendOnline(false);
    setBackendStatus('checking');
    executeHealthCheck();
  }, [executeHealthCheck]);

  useEffect(() => {
    isMountedRef.current = true;
    startTimeRef.current = Date.now();
    attemptCountRef.current = 0;
    executeHealthCheck();

    return () => {
      isMountedRef.current = false;
      clearPendingTimer();
    };
  }, [executeHealthCheck]);

  return {
    backendOnline,
    backendStatus,
    vlmEnabled,
    retryConnection,
  };
}
