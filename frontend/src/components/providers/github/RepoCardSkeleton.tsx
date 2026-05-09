export function RepoCardSkeleton() {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="h-5 w-2/3 animate-pulse rounded bg-gray-200" />
      <div className="mt-3 h-4 w-full animate-pulse rounded bg-gray-100" />
      <div className="mt-2 h-4 w-4/5 animate-pulse rounded bg-gray-100" />
    </div>
  );
}
