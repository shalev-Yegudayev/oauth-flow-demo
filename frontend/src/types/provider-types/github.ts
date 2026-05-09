import { z } from 'zod';

export const RepositorySchema = z.object({
  name: z.string(),
  description: z.string().nullable(),
  stars: z.number(),
});

export const GithubSectionsSchema = z.object({
  repositories: z.array(RepositorySchema),
});

export type Repository = z.infer<typeof RepositorySchema>;
export type GithubSections = z.infer<typeof GithubSectionsSchema>;
