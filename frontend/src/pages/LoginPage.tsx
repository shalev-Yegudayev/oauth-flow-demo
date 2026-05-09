import { useSearchParams } from 'react-router-dom';
import { LoginCard } from '@/components/LoginCard';

export function LoginPage() {
  const [searchParams] = useSearchParams();
  const oauthError = searchParams.get('error') ?? undefined;

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <LoginCard oauthError={oauthError} />
    </main>
  );
}
