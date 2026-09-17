CREATE TABLE `worker_task_gate_refusals` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`project` text NOT NULL,
	`task_external_id` text NOT NULL,
	`operation` text NOT NULL,
	`code` text NOT NULL,
	`message` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE INDEX `worker_task_gate_refusals_project_created_idx` ON `worker_task_gate_refusals` (`project`,`created_at`);--> statement-breakpoint
CREATE INDEX `worker_task_gate_refusals_code_idx` ON `worker_task_gate_refusals` (`code`);
