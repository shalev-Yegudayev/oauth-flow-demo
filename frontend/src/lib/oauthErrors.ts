export const oauthErrorMessages: Record<string, string> = {
  access_denied: "Login cancelled. You can try again whenever you're ready.",
  insufficient_scope: 'GitHub login requires the requested permissions. Please try again and allow all permissions when prompted.',
  invalid_or_expired_state: 'Your login session expired. Please try again.',
  missing_code_or_state: 'Login could not be completed. Please try again.',
  provider_mismatch: 'Something went wrong during login. Please try again.',
};

export function resolveOauthErrorMessage(error: string): string {
  return oauthErrorMessages[error] ?? 'Something went wrong during login. Please try again.';
}
