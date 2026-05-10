import { z } from 'zod';
import { GithubSectionsSchema } from "./provider-types/github";

export const LicenseSchema = z.enum(["Pro", "Basic"]);
export type License = z.infer<typeof LicenseSchema>;

const UserSummaryBaseSchema = z.object({
  id: z.string(),
  name: z.string(),
  license: LicenseSchema,
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
