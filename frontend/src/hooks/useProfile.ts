import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ProviderProfile } from "@/types/profile";

export function useProfile() {
  return useQuery<ProviderProfile>({
    queryKey: ["profile"],
    queryFn: () => apiFetch<ProviderProfile>("/profile"),
  });
}
