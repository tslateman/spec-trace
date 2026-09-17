CREATE TABLE `worker_drift_reports` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project` text NOT NULL,
	`payload` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `worker_drift_reports_project_created_idx` ON `worker_drift_reports` (`project`,`created_at`);--> statement-breakpoint
CREATE TABLE `worker_impact_reports` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project` text NOT NULL,
	`base_ref` text NOT NULL,
	`head_ref` text NOT NULL,
	`payload` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `worker_impact_reports_project_created_idx` ON `worker_impact_reports` (`project`,`created_at`);--> statement-breakpoint
CREATE TABLE `worker_task_outcomes` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project` text NOT NULL,
	`task_external_id` text NOT NULL,
	`status` text NOT NULL,
	`payload` text NOT NULL,
	`drained_at` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `worker_task_outcomes_project_id_idx` ON `worker_task_outcomes` (`project`,`id`);