import type { GithubSections } from "./provider-types/github";

export type Tier = "Pro" | "Basic";

export type UserSummary = {
  id: string;
  name: string;
  provider: string;
  tier: Tier;
  role: string;
};

type Profile<S = unknown> = {
  user: UserSummary;
  sections: S;
};

export type ProviderSectionsMap = {
  github: GithubSections;
};

export type SupportedProvider = keyof ProviderSectionsMap;

export type ProviderProfile = {
  [P in SupportedProvider]: Profile<ProviderSectionsMap[P]> & {
    user: UserSummary & { provider: P };
  };
}[SupportedProvider];
