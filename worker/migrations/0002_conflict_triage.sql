ALTER TABLE `requirements_conflictlog` ADD `resolution_reason` text DEFAULT 'unspecified' NOT NULL;--> statement-breakpoint
ALTER TABLE `requirements_conflictlog` ADD `last_seen_at` text;--> statement-breakpoint
ALTER TABLE `requirements_conflictlog` ADD `times_detected` integer DEFAULT 1 NOT NULL;
--> statement-breakpoint
UPDATE `requirements_conflictlog` SET `last_seen_at` = `created_at` WHERE `last_seen_at` IS NULL;
