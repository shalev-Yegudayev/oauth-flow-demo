import type { License } from '@/types/profile';

const styles: Record<License, string> = {
  Pro: 'bg-amber-100 text-amber-800 ring-amber-300',
  Basic: 'bg-gray-100 text-gray-700 ring-gray-300',
};

export function LicenseBadge({ license }: { license: License }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${styles[license]}`}
    >
      {license}
    </span>
  );
}
