import { backendUrl } from '@/lib/api';
import { GitHubLogoIcon } from '@radix-ui/react-icons';
import { resolveOauthErrorMessage } from '@/lib/oauthErrors';


interface LoginCardProps {
  oauthError?: string;
}

export function LoginCard({ oauthError }: LoginCardProps) {
  return (
    <div className="w-full max-w-sm rounded-xl border border-gray-200 bg-white p-8 shadow-md">
      <h1 className="text-center text-2xl font-semibold text-gray-900">Welcome</h1>
      <p className="mt-2 text-center text-sm text-gray-500">
        Sign in to view your GitHub repositories.
      </p>
      {oauthError && (
        <p
          role="alert"
          className="mt-4 rounded-md bg-amber-50 px-3 py-2 text-center text-sm text-amber-800"
        >
          {resolveOauthErrorMessage(oauthError)}
        </p>
      )}
      <a
        href={backendUrl('/auth/github')}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
      >
        <GitHubLogoIcon className="h-4 w-4" />
        Login with GitHub
      </a>
    </div>
  );
}
