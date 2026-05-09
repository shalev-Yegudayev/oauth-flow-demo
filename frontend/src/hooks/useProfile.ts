import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { ProviderProfileSchema } from "@/types/profile";
import type { ProviderProfile } from "@/types/profile";

export function useProfile() {
  return useQuery<ProviderProfile>({
    queryKey: ["profile"],
    queryFn: () => apiFetch("/profile", undefined, ProviderProfileSchema),
  });
}
