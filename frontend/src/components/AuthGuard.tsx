import { Navigate } from 'react-router-dom';
import { useProfile } from '@/hooks/useProfile';
import { UnauthorizedError } from '@/lib/errors';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isLoading, error } = useProfile();

  if (isLoading) return null;

  if (error instanceof UnauthorizedError) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
