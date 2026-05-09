import type { GithubSections } from '@/types/provider-types/github';
import { RepositoryGrid } from './RepositoryGrid';

export function GithubSectionsView({ sections }: { sections: GithubSections }) {
  return (
    <section>
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Repositories</h2>
      <RepositoryGrid repositories={sections.repositories} />
    </section>
  );
}
