import { useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Trash2, TriangleAlert, X } from 'lucide-react';
import { useDeleteAccount } from '@/hooks/useDeleteAccount';

export function DeleteAccountButton() {
  const [open, setOpen] = useState(false);
  const { mutate, isPending } = useDeleteAccount();

  function handleConfirm() {
    mutate(undefined, { onSettled: () => setOpen(false) });
  }

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-md border border-red-300 bg-white px-3 py-2 text-sm font-medium text-red-600 shadow-sm hover:bg-red-50"
        >
          <Trash2 className="h-4 w-4" />
          Delete account
        </button>
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />

        <Dialog.Content className="fixed left-1/2 top-1/2 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl bg-white p-6 shadow-xl focus:outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95">
          <Dialog.Close className="absolute right-4 top-4 rounded p-1 text-gray-400 hover:text-gray-600">
            <X className="h-4 w-4" />
          </Dialog.Close>

          <div className="flex items-start gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-100">
              <TriangleAlert className="h-5 w-5 text-red-600" />
            </div>
            <div>
              <Dialog.Title className="text-base font-semibold text-gray-900">
                Delete account
              </Dialog.Title>
              <Dialog.Description className="mt-1 text-sm text-gray-500">
                Are you sure you want to delete your account? All your data will be permanently removed. This action cannot be undone.
              </Dialog.Description>
            </div>
          </div>

          <div className="mt-6 flex justify-end gap-3">
            <Dialog.Close asChild>
              <button
                type="button"
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
            </Dialog.Close>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isPending}
              className="inline-flex items-center gap-2 rounded-md bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              <Trash2 className="h-4 w-4" />
              {isPending ? 'Deleting…' : 'Yes, delete my account'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
