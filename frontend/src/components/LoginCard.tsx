import { backendUrl } from '@/lib/api';

function GithubMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={className}
      fill="currentColor"
    >
      <path d="M12 .5C5.73.5.75 5.48.75 11.75c0 4.97 3.22 9.18 7.69 10.67.56.1.77-.24.77-.54v-1.9c-3.13.68-3.79-1.5-3.79-1.5-.51-1.3-1.25-1.65-1.25-1.65-1.02-.7.08-.69.08-.69 1.13.08 1.72 1.16 1.72 1.16 1 1.72 2.63 1.22 3.27.93.1-.73.39-1.22.71-1.5-2.5-.28-5.13-1.25-5.13-5.57 0-1.23.44-2.24 1.16-3.03-.12-.28-.5-1.43.11-2.97 0 0 .95-.3 3.1 1.16a10.78 10.78 0 0 1 5.64 0c2.15-1.46 3.1-1.16 3.1-1.16.61 1.54.23 2.69.11 2.97.72.79 1.16 1.8 1.16 3.03 0 4.33-2.64 5.28-5.15 5.56.4.35.76 1.04.76 2.1v3.11c0 .3.21.65.78.54 4.46-1.49 7.68-5.7 7.68-10.67C23.25 5.48 18.27.5 12 .5Z" />
    </svg>
  );
}

const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  access_denied: 'Login cancelled. You can try again whenever you\'re ready.',
  insufficient_scope: 'GitHub login requires the requested permissions. Please try again and allow all permissions when prompted.',
  invalid_or_expired_state: 'Your login session expired. Please try again.',
  missing_code_or_state: 'Login could not be completed. Please try again.',
  provider_mismatch: 'Something went wrong during login. Please try again.',
};

function resolveErrorMessage(error: string): string {
  return OAUTH_ERROR_MESSAGES[error] ?? 'Something went wrong during login. Please try again.';
}

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
          {resolveErrorMessage(oauthError)}
        </p>
      )}
      <a
        href={backendUrl('/auth/github')}
        className="mt-6 inline-flex w-full items-center justify-center gap-2 rounded-md bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-800"
      >
        <GithubMark className="h-4 w-4" />
        Login with GitHub
      </a>
    </div>
  );
}
