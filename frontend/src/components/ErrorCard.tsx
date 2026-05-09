import { AlertTriangle } from 'lucide-react';

type Props = {
  title?: string;
  message?: string;
  onRetry?: () => void;
};

export function ErrorCard({ title = 'Something went wrong', message, onRetry }: Props) {
  return (
    <div className="mx-auto max-w-md rounded-lg border border-red-200 bg-red-50 p-6 text-center">
      <AlertTriangle className="mx-auto h-8 w-8 text-red-500" />
      <h3 className="mt-3 text-base font-semibold text-red-900">{title}</h3>
      {message && <p className="mt-1 text-sm text-red-700">{message}</p>}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-500"
        >
          Retry
        </button>
      )}
    </div>
  );
}
