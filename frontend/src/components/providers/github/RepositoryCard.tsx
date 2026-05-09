import { Star } from 'lucide-react';
import type { Repository } from '@/types/provider-types/github';

export function RepositoryCard({ repo }: { repo: Repository }) {
  return (
    <div className="relative flex h-full flex-col rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:shadow-md">
      <div className="absolute right-3 top-3 flex items-center gap-1 text-xs font-medium text-gray-600">
        <Star className="h-3.5 w-3.5 fill-amber-400 stroke-amber-500" />
        <span>{repo.stars.toLocaleString()}</span>
      </div>
      <h3 className="pr-12 text-base font-semibold text-gray-900 break-words">
        {repo.name}
      </h3>
      <p className="mt-2 text-sm text-gray-600 line-clamp-3">
        {repo.description ?? <span className="italic text-gray-400">No description</span>}
      </p>
    </div>
  );
}
