import { QueryClient } from '@tanstack/react-query';
import { UnauthorizedError } from './errors';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // 401 is definitive — re-auth required before retrying.
        if (error instanceof UnauthorizedError) return false;
        return failureCount < 2;
      },
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});
