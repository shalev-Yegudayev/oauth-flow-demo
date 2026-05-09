import { z } from 'zod';
import { GithubSectionsSchema } from "./provider-types/github";

export const TierSchema = z.enum(["Pro", "Basic"]);
export type Tier = z.infer<typeof TierSchema>;

const UserSummaryBaseSchema = z.object({
  id: z.string(),
  name: z.string(),
  tier: TierSchema,
  role: z.string(),
});

export type UserSummary = z.infer<typeof UserSummaryBaseSchema> & { provider: string };

const GithubProfileSchema = z.object({
  user: UserSummaryBaseSchema.extend({ provider: z.literal('github') }),
  sections: GithubSectionsSchema,
});

export const ProviderProfileSchema = GithubProfileSchema;

export type ProviderSectionsMap = {
  github: z.infer<typeof GithubSectionsSchema>;
};

export type SupportedProvider = keyof ProviderSectionsMap;

export type ProviderProfile = z.infer<typeof ProviderProfileSchema>;
