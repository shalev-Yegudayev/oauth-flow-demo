import type { Repository } from '@/types/provider-types/github';
import { RepositoryCard } from './RepositoryCard';

export function RepositoryGrid({ repositories }: { repositories: Repository[] }) {
  if (repositories.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-sm text-gray-500">
        No repositories found.
      </div>
    );
  }

  const sorted = [...repositories].sort((a, b) => b.stars - a.stars);

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {sorted.map((repo) => (
        <RepositoryCard key={repo.name} repo={repo} />
      ))}
    </div>
  );
}
