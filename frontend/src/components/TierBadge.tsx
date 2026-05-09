import type { Tier } from '@/types/profile';

const styles: Record<Tier, string> = {
  Pro: 'bg-amber-100 text-amber-800 ring-amber-300',
  Basic: 'bg-gray-100 text-gray-700 ring-gray-300',
};

export function TierBadge({ tier }: { tier: Tier }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[tier]}`}
    >
      {tier}
    </span>
  );
}
