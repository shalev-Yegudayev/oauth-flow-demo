export type Repository = {
  name: string;
  description: string | null;
  stars: number;
};

export type GithubSections = {
  repositories: Repository[];
};
