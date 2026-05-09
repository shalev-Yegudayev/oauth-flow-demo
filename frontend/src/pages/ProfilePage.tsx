import { useProfile } from '@/hooks/useProfile';
import { UnauthorizedError } from '@/lib/errors';
import { ProfileHeader } from '@/components/ProfileHeader';
import { LogoutButton } from '@/components/LogoutButton';
import { ProfileSkeleton } from '@/components/ProfileSkeleton';
import { ErrorCard } from '@/components/ErrorCard';
import { GithubSectionsView } from '@/components/providers/github/GithubSectionsView';
import type { ProviderProfile } from '@/types/profile';

function ProviderSections({ profile }: { profile: ProviderProfile }) {
  switch (profile.user.provider) {
    case 'github':
      return <GithubSectionsView sections={profile.sections} />;
    default:
      profile.user.provider satisfies never;
      return null;
  }
}

export function ProfilePage() {
  const { data, isLoading, error, refetch } = useProfile();

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-8 flex items-start justify-between gap-4">
          {data && <ProfileHeader user={data.user} />}
          <LogoutButton />
        </div>

        {isLoading && <ProfileSkeleton />}
        {error && !(error instanceof UnauthorizedError) && (
          <ErrorCard
            message="Failed to load your profile."
            onRetry={() => void refetch()}
          />
        )}
        {data && <ProviderSections profile={data} />}
      </div>
    </main>
  );
}
