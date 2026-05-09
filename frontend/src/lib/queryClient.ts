import { QueryClient } from '@tanstack/react-query';
import { UnauthorizedError } from './errors';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // 401s are definitive — the session cookie is missing or expired, so retrying
        // the same request will keep failing until the user re-authenticates.
        if (error instanceof UnauthorizedError) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});
