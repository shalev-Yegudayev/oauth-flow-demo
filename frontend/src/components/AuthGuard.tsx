import { Navigate } from 'react-router-dom';
import { useProfile } from '@/hooks/useProfile';
import { ProfileSkeleton } from './ProfileSkeleton';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isLoading, error } = useProfile();

  if (isLoading) return <ProfileSkeleton />;

  if (error) return <Navigate to="/login" replace />;

  return <>{children}</>;
}
