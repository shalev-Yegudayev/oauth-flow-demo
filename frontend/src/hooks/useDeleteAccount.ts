import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiFetch } from '@/lib/api';

export function useDeleteAccount() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  return useMutation({
    mutationFn: () => apiFetch<void>('/auth/account', { method: 'DELETE' }),
    onSettled: () => {
      qc.clear();
      navigate('/login', { replace: true });
    },
  });
}
