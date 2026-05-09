import type { UserSummary } from '@/types/profile';
import { TierBadge } from './TierBadge';

export function ProfileHeader({ user }: { user: UserSummary }) {
  return (
    <div className="flex items-center gap-4">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold text-gray-900">{user.name}</h1>
          <TierBadge tier={user.tier} />
        </div>
        <p className="mt-0.5 text-sm text-gray-500">
          {user.role} · via {user.provider}
        </p>
      </div>
    </div>
  );
}
