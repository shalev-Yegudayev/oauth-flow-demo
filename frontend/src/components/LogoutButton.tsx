import { LogOut } from 'lucide-react';
import { useLogout } from '@/hooks/useLogout';

export function LogoutButton() {
  const { mutate, isPending } = useLogout();
  return (
    <button
      type="button"
      onClick={() => mutate()}
      disabled={isPending}
      className="inline-flex items-center gap-2 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 disabled:opacity-50"
    >
      <LogOut className="h-4 w-4" />
      {isPending ? 'Logging out…' : 'Logout'}
    </button>
  );
}
