CREATE TABLE `worker_coverage_snapshots` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project` text NOT NULL,
	`commit_sha` text NOT NULL,
	`git_branch` text NOT NULL,
	`specification_rate` real NOT NULL,
	`structure_rate` real NOT NULL,
	`verification_rate` real NOT NULL,
	`total` integer NOT NULL,
	`non_draft` integer NOT NULL,
	`passing` integer NOT NULL,
	`generated_at` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `worker_coverage_snapshots_project_generated_idx` ON `worker_coverage_snapshots` (`project`,`generated_at`);
