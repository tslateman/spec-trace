CREATE TABLE `requirements_agentsprint` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`description` text NOT NULL,
	`goal_description` text NOT NULL,
	`is_active` integer NOT NULL,
	`completed_at` text,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `requirements_agenttask_depends_on` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`from_agenttask_id` integer NOT NULL,
	`to_agenttask_id` integer NOT NULL,
	FOREIGN KEY (`from_agenttask_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`to_agenttask_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_agenttask_depends_on_uniq` ON `requirements_agenttask_depends_on` (`from_agenttask_id`,`to_agenttask_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_depends_on_from_agenttask_id_idx` ON `requirements_agenttask_depends_on` (`from_agenttask_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_depends_on_to_agenttask_id_idx` ON `requirements_agenttask_depends_on` (`to_agenttask_id`);--> statement-breakpoint
CREATE TABLE `requirements_agenttaskhistory` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`timestamp` text NOT NULL,
	`action` text NOT NULL,
	`from_status` text NOT NULL,
	`to_status` text NOT NULL,
	`details` text NOT NULL,
	`agent_id` integer,
	`task_id` integer NOT NULL,
	FOREIGN KEY (`agent_id`) REFERENCES `requirements_agent`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`task_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_agenttaskhistory_timestamp_idx` ON `requirements_agenttaskhistory` (`timestamp`);--> statement-breakpoint
CREATE INDEX `requirements_agenttaskhistory_agent_id_idx` ON `requirements_agenttaskhistory` (`agent_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttaskhistory_task_id_idx` ON `requirements_agenttaskhistory` (`task_id`);--> statement-breakpoint
CREATE TABLE `requirements_agenttask_requirements` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`agenttask_id` integer NOT NULL,
	`requirement_id` integer NOT NULL,
	FOREIGN KEY (`agenttask_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_agenttask_requirements_uniq` ON `requirements_agenttask_requirements` (`agenttask_id`,`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_requirements_agenttask_id_idx` ON `requirements_agenttask_requirements` (`agenttask_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_requirements_requirement_id_idx` ON `requirements_agenttask_requirements` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_agenttaskreview` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`decision` text NOT NULL,
	`commit_sha` text NOT NULL,
	`done_when_results` text NOT NULL,
	`feedback` text NOT NULL,
	`blocking_issues` text NOT NULL,
	`suggestions` text NOT NULL,
	`created_at` text NOT NULL,
	`reviewer_id` integer,
	`task_id` integer NOT NULL,
	FOREIGN KEY (`reviewer_id`) REFERENCES `requirements_agent`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`task_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_agenttaskreview_reviewer_id_idx` ON `requirements_agenttaskreview` (`reviewer_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttaskreview_task_id_idx` ON `requirements_agenttaskreview` (`task_id`);--> statement-breakpoint
CREATE TABLE `requirements_agenttask` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`external_id` text NOT NULL,
	`title` text NOT NULL,
	`description` text NOT NULL,
	`status` text NOT NULL,
	`claimed_at` text,
	`lease_expires` text,
	`done_when` text NOT NULL,
	`scope_in` text NOT NULL,
	`scope_out` text NOT NULL,
	`spec_ref` text NOT NULL,
	`worktree_path` text NOT NULL,
	`branch_name` text NOT NULL,
	`commit_sha` text NOT NULL,
	`attempt_count` integer NOT NULL,
	`max_attempts` integer NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`claimed_by_id` integer,
	`sprint_id` integer,
	FOREIGN KEY (`claimed_by_id`) REFERENCES `requirements_agent`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`sprint_id`) REFERENCES `requirements_agentsprint`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_agenttask_external_id_unique` ON `requirements_agenttask` (`external_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_status_idx` ON `requirements_agenttask` (`status`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_claimed_by_id_idx` ON `requirements_agenttask` (`claimed_by_id`);--> statement-breakpoint
CREATE INDEX `requirements_agenttask_sprint_id_idx` ON `requirements_agenttask` (`sprint_id`);--> statement-breakpoint
CREATE TABLE `requirements_agent` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`agent_id` text NOT NULL,
	`role` text NOT NULL,
	`is_active` integer NOT NULL,
	`last_heartbeat` text,
	`config` text NOT NULL,
	`registered_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_agent_agent_id_unique` ON `requirements_agent` (`agent_id`);--> statement-breakpoint
CREATE INDEX `requirements_agent_role_idx` ON `requirements_agent` (`role`);--> statement-breakpoint
CREATE TABLE `requirements_conflictlog` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`pattern` text NOT NULL,
	`confidence` text NOT NULL,
	`details` text NOT NULL,
	`resolved` integer NOT NULL,
	`resolved_at` text,
	`resolution_notes` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`requirement_a_id` integer NOT NULL,
	`requirement_b_id` integer NOT NULL,
	FOREIGN KEY (`requirement_a_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`requirement_b_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_conflictlog_requirement_a_id_idx` ON `requirements_conflictlog` (`requirement_a_id`);--> statement-breakpoint
CREATE INDEX `requirements_conflictlog_requirement_b_id_idx` ON `requirements_conflictlog` (`requirement_b_id`);--> statement-breakpoint
CREATE TABLE `requirements_corpusentry` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`external_id` text NOT NULL,
	`kind` text NOT NULL,
	`title` text NOT NULL,
	`owner` text NOT NULL,
	`status` text NOT NULL,
	`source_file` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_corpusentry_external_id_unique` ON `requirements_corpusentry` (`external_id`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentry_kind_idx` ON `requirements_corpusentry` (`kind`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentry_owner_idx` ON `requirements_corpusentry` (`owner`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentry_status_idx` ON `requirements_corpusentry` (`status`);--> statement-breakpoint
CREATE TABLE `requirements_corpusentryversion` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`version` integer NOT NULL,
	`body` text NOT NULL,
	`content_hash` text NOT NULL,
	`applies_to` text NOT NULL,
	`checks` text NOT NULL,
	`effective_date` text,
	`source_file` text NOT NULL,
	`created_at` text NOT NULL,
	`entry_id` integer NOT NULL,
	`enforcement` text NOT NULL,
	`supersedes_id` integer,
	FOREIGN KEY (`entry_id`) REFERENCES `requirements_corpusentry`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`supersedes_id`) REFERENCES `requirements_corpusentryversion`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_version_idx` ON `requirements_corpusentryversion` (`version`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_content_hash_idx` ON `requirements_corpusentryversion` (`content_hash`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_effective_date_idx` ON `requirements_corpusentryversion` (`effective_date`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_entry_id_idx` ON `requirements_corpusentryversion` (`entry_id`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_enforcement_idx` ON `requirements_corpusentryversion` (`enforcement`);--> statement-breakpoint
CREATE INDEX `requirements_corpusentryversion_supersedes_id_idx` ON `requirements_corpusentryversion` (`supersedes_id`);--> statement-breakpoint
CREATE UNIQUE INDEX `unique_corpus_entry_version` ON `requirements_corpusentryversion` (`entry_id`,`version`);--> statement-breakpoint
CREATE TABLE `requirements_corpussnapshot_entry_versions` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`corpussnapshot_id` integer NOT NULL,
	`corpusentryversion_id` integer NOT NULL,
	FOREIGN KEY (`corpussnapshot_id`) REFERENCES `requirements_corpussnapshot`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`corpusentryversion_id`) REFERENCES `requirements_corpusentryversion`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_corpussnapshot_entry_versions_uniq` ON `requirements_corpussnapshot_entry_versions` (`corpussnapshot_id`,`corpusentryversion_id`);--> statement-breakpoint
CREATE INDEX `requirements_corpussnapshot_entry_versions_corpussnapshot_id_idx` ON `requirements_corpussnapshot_entry_versions` (`corpussnapshot_id`);--> statement-breakpoint
CREATE INDEX `requirements_corpussnapshot_entry_versions_corpusentryversion_id_idx` ON `requirements_corpussnapshot_entry_versions` (`corpusentryversion_id`);--> statement-breakpoint
CREATE TABLE `requirements_corpussnapshot` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`snapshot_hash` text NOT NULL,
	`entry_version_hashes` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_corpussnapshot_snapshot_hash_unique` ON `requirements_corpussnapshot` (`snapshot_hash`);--> statement-breakpoint
CREATE INDEX `requirements_corpussnapshot_created_at_idx` ON `requirements_corpussnapshot` (`created_at`);--> statement-breakpoint
CREATE TABLE `requirements_inappvalidationresult` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`status` text NOT NULL,
	`message` text NOT NULL,
	`checked_at` text NOT NULL,
	`validation_id` integer NOT NULL,
	`validation_run_id` integer NOT NULL,
	`context` text NOT NULL,
	`steps` text NOT NULL,
	FOREIGN KEY (`validation_id`) REFERENCES `requirements_inappvalidation`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`validation_run_id`) REFERENCES `requirements_inappvalidationrun`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_inappvalidationresult_validation_id_idx` ON `requirements_inappvalidationresult` (`validation_id`);--> statement-breakpoint
CREATE INDEX `requirements_inappvalidationresult_validation_run_id_idx` ON `requirements_inappvalidationresult` (`validation_run_id`);--> statement-breakpoint
CREATE TABLE `requirements_inappvalidationrun` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`imported_at` text NOT NULL,
	`source` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `requirements_inappvalidation` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`endpoint` text NOT NULL,
	`requirement_id` integer NOT NULL,
	`feature_flags` text NOT NULL,
	`vendor` text NOT NULL,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_inappvalidation_requirement_id_idx` ON `requirements_inappvalidation` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_intentvalidationresult` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`commit_sha` text NOT NULL,
	`strategic_score` integer NOT NULL,
	`opportunity_score` integer NOT NULL,
	`drift_score` integer NOT NULL,
	`passed` integer NOT NULL,
	`failure_reasons` text NOT NULL,
	`created_at` text NOT NULL,
	`task_id` integer NOT NULL,
	FOREIGN KEY (`task_id`) REFERENCES `requirements_agenttask`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_intentvalidationresult_task_id_idx` ON `requirements_intentvalidationresult` (`task_id`);--> statement-breakpoint
CREATE TABLE `requirements_requirement_depends_on` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`from_requirement_id` integer NOT NULL,
	`to_requirement_id` integer NOT NULL,
	FOREIGN KEY (`from_requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`to_requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_requirement_depends_on_uniq` ON `requirements_requirement_depends_on` (`from_requirement_id`,`to_requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_depends_on_from_requirement_id_idx` ON `requirements_requirement_depends_on` (`from_requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_depends_on_to_requirement_id_idx` ON `requirements_requirement_depends_on` (`to_requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_requirement` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`path` text NOT NULL,
	`depth` integer NOT NULL,
	`numchild` integer NOT NULL,
	`external_id` text NOT NULL,
	`title` text NOT NULL,
	`description` text NOT NULL,
	`tags` text NOT NULL,
	`priority` text NOT NULL,
	`status` text NOT NULL,
	`source_file` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`verification_status` text NOT NULL,
	`slo_status` text NOT NULL,
	`verification_method` text NOT NULL,
	`component` text NOT NULL,
	`condition` text NOT NULL,
	`response` text NOT NULL,
	`scope` text NOT NULL,
	`structure_completeness` real NOT NULL,
	`timing` text NOT NULL,
	`risk_level` text NOT NULL,
	`project` text NOT NULL,
	CONSTRAINT "requirement_project_is_named" CHECK(NOT ("requirements_requirement"."project" = ''))
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_requirement_path_unique` ON `requirements_requirement` (`path`);--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_requirement_external_id_unique` ON `requirements_requirement` (`external_id`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_verification_status_idx` ON `requirements_requirement` (`verification_status`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_slo_status_idx` ON `requirements_requirement` (`slo_status`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_verification_method_idx` ON `requirements_requirement` (`verification_method`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_component_idx` ON `requirements_requirement` (`component`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_risk_level_idx` ON `requirements_requirement` (`risk_level`);--> statement-breakpoint
CREATE INDEX `requirements_requirement_project_idx` ON `requirements_requirement` (`project`);--> statement-breakpoint
CREATE TABLE `requirements_reviewcoverage` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`matched_by` text NOT NULL,
	`cited` integer NOT NULL,
	`entry_version_id` integer NOT NULL,
	`review_id` integer NOT NULL,
	`enforcement` text NOT NULL,
	FOREIGN KEY (`entry_version_id`) REFERENCES `requirements_corpusentryversion`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`review_id`) REFERENCES `requirements_specreview`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_reviewcoverage_cited_idx` ON `requirements_reviewcoverage` (`cited`);--> statement-breakpoint
CREATE INDEX `requirements_reviewcoverage_entry_version_id_idx` ON `requirements_reviewcoverage` (`entry_version_id`);--> statement-breakpoint
CREATE INDEX `requirements_reviewcoverage_review_id_idx` ON `requirements_reviewcoverage` (`review_id`);--> statement-breakpoint
CREATE INDEX `requirements_reviewcoverage_enforcement_idx` ON `requirements_reviewcoverage` (`enforcement`);--> statement-breakpoint
CREATE UNIQUE INDEX `unique_review_coverage_row` ON `requirements_reviewcoverage` (`review_id`,`entry_version_id`);--> statement-breakpoint
CREATE TABLE `requirements_reviewfinding` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`finding_type` text NOT NULL,
	`check_id` text NOT NULL,
	`detail` text NOT NULL,
	`created_at` text NOT NULL,
	`entry_version_id` integer NOT NULL,
	`review_id` integer NOT NULL,
	`enforcement` text NOT NULL,
	FOREIGN KEY (`entry_version_id`) REFERENCES `requirements_corpusentryversion`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`review_id`) REFERENCES `requirements_specreview`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_reviewfinding_finding_type_idx` ON `requirements_reviewfinding` (`finding_type`);--> statement-breakpoint
CREATE INDEX `requirements_reviewfinding_check_id_idx` ON `requirements_reviewfinding` (`check_id`);--> statement-breakpoint
CREATE INDEX `requirements_reviewfinding_entry_version_id_idx` ON `requirements_reviewfinding` (`entry_version_id`);--> statement-breakpoint
CREATE INDEX `requirements_reviewfinding_review_id_idx` ON `requirements_reviewfinding` (`review_id`);--> statement-breakpoint
CREATE INDEX `requirements_reviewfinding_enforcement_idx` ON `requirements_reviewfinding` (`enforcement`);--> statement-breakpoint
CREATE TABLE `requirements_slo_requirements` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`slo_id` integer NOT NULL,
	`requirement_id` integer NOT NULL,
	FOREIGN KEY (`slo_id`) REFERENCES `requirements_slo`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_slo_requirements_uniq` ON `requirements_slo_requirements` (`slo_id`,`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_slo_requirements_slo_id_idx` ON `requirements_slo_requirements` (`slo_id`);--> statement-breakpoint
CREATE INDEX `requirements_slo_requirements_requirement_id_idx` ON `requirements_slo_requirements` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_slo` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`display_name` text NOT NULL,
	`description` text NOT NULL,
	`service` text NOT NULL,
	`target` real,
	`time_window` text NOT NULL,
	`budgeting_method` text NOT NULL,
	`status` text NOT NULL,
	`current_value` real,
	`error_budget_remaining` real,
	`last_updated` text,
	`source_file` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_slo_name_unique` ON `requirements_slo` (`name`);--> statement-breakpoint
CREATE INDEX `requirements_slo_status_idx` ON `requirements_slo` (`status`);--> statement-breakpoint
CREATE TABLE `requirements_specreview` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`spec_file` text NOT NULL,
	`reviewer` text NOT NULL,
	`outcome` text NOT NULL,
	`created_at` text NOT NULL,
	`requirement_id` integer NOT NULL,
	`snapshot_id` integer NOT NULL,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`snapshot_id`) REFERENCES `requirements_corpussnapshot`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_specreview_reviewer_idx` ON `requirements_specreview` (`reviewer`);--> statement-breakpoint
CREATE INDEX `requirements_specreview_outcome_idx` ON `requirements_specreview` (`outcome`);--> statement-breakpoint
CREATE INDEX `requirements_specreview_created_at_idx` ON `requirements_specreview` (`created_at`);--> statement-breakpoint
CREATE INDEX `requirements_specreview_requirement_id_idx` ON `requirements_specreview` (`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_specreview_snapshot_id_idx` ON `requirements_specreview` (`snapshot_id`);--> statement-breakpoint
CREATE TABLE `requirements_testrequirementlink` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`test_nodeid` text NOT NULL,
	`last_status` text NOT NULL,
	`last_run_at` text,
	`needs_review` integer NOT NULL,
	`review_reason` text NOT NULL,
	`created_at` text NOT NULL,
	`updated_at` text NOT NULL,
	`requirement_id` integer NOT NULL,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_testrequirementlink_uniq` ON `requirements_testrequirementlink` (`test_nodeid`,`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_testrequirementlink_test_nodeid_idx` ON `requirements_testrequirementlink` (`test_nodeid`);--> statement-breakpoint
CREATE INDEX `requirements_testrequirementlink_requirement_id_idx` ON `requirements_testrequirementlink` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_testresult_requirements` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`testresult_id` integer NOT NULL,
	`requirement_id` integer NOT NULL,
	FOREIGN KEY (`testresult_id`) REFERENCES `requirements_testresult`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_testresult_requirements_uniq` ON `requirements_testresult_requirements` (`testresult_id`,`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_testresult_requirements_testresult_id_idx` ON `requirements_testresult_requirements` (`testresult_id`);--> statement-breakpoint
CREATE INDEX `requirements_testresult_requirements_requirement_id_idx` ON `requirements_testresult_requirements` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_testresult` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`test_nodeid` text NOT NULL,
	`classname` text NOT NULL,
	`name` text NOT NULL,
	`time` real NOT NULL,
	`status` text NOT NULL,
	`message` text NOT NULL,
	`test_run_id` integer NOT NULL,
	FOREIGN KEY (`test_run_id`) REFERENCES `requirements_testrun`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_testresult_test_nodeid_idx` ON `requirements_testresult` (`test_nodeid`);--> statement-breakpoint
CREATE INDEX `requirements_testresult_test_run_id_idx` ON `requirements_testresult` (`test_run_id`);--> statement-breakpoint
CREATE TABLE `requirements_testrun` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`imported_at` text NOT NULL,
	`source_file` text NOT NULL,
	`ci_job_url` text NOT NULL,
	`finished_at` text,
	`git_branch` text NOT NULL,
	`git_sha` text NOT NULL,
	`started_at` text,
	`repository` text NOT NULL,
	`workflow_name` text NOT NULL,
	`workflow_run_id` integer
);
--> statement-breakpoint
CREATE INDEX `requirements_testrun_repository_idx` ON `requirements_testrun` (`repository`);--> statement-breakpoint
CREATE INDEX `requirements_testrun_workflow_run_id_idx` ON `requirements_testrun` (`workflow_run_id`);--> statement-breakpoint
CREATE TABLE `requirements_verificationflow_requirements` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`verificationflow_id` integer NOT NULL,
	`requirement_id` integer NOT NULL,
	FOREIGN KEY (`verificationflow_id`) REFERENCES `requirements_verificationflow`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`requirement_id`) REFERENCES `requirements_requirement`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_verificationflow_requirements_uniq` ON `requirements_verificationflow_requirements` (`verificationflow_id`,`requirement_id`);--> statement-breakpoint
CREATE INDEX `requirements_verificationflow_requirements_verificationflow_id_idx` ON `requirements_verificationflow_requirements` (`verificationflow_id`);--> statement-breakpoint
CREATE INDEX `requirements_verificationflow_requirements_requirement_id_idx` ON `requirements_verificationflow_requirements` (`requirement_id`);--> statement-breakpoint
CREATE TABLE `requirements_verificationflowrun` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`status` text NOT NULL,
	`context` text NOT NULL,
	`source` text NOT NULL,
	`started_at` text NOT NULL,
	`completed_at` text,
	`flow_id` integer NOT NULL,
	FOREIGN KEY (`flow_id`) REFERENCES `requirements_verificationflow`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE INDEX `requirements_verificationflowrun_status_idx` ON `requirements_verificationflowrun` (`status`);--> statement-breakpoint
CREATE INDEX `requirements_verificationflowrun_flow_id_idx` ON `requirements_verificationflowrun` (`flow_id`);--> statement-breakpoint
CREATE TABLE `requirements_verificationflowstep` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`step_order` integer NOT NULL,
	`name` text NOT NULL,
	`passed` integer NOT NULL,
	`details` text NOT NULL,
	`error_message` text NOT NULL,
	`response_status` integer,
	`response_body` text NOT NULL,
	`started_at` text NOT NULL,
	`completed_at` text NOT NULL,
	`flow_run_id` integer NOT NULL,
	FOREIGN KEY (`flow_run_id`) REFERENCES `requirements_verificationflowrun`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_verificationflowstep_uniq` ON `requirements_verificationflowstep` (`flow_run_id`,`step_order`);--> statement-breakpoint
CREATE INDEX `requirements_verificationflowstep_flow_run_id_idx` ON `requirements_verificationflowstep` (`flow_run_id`);--> statement-breakpoint
CREATE TABLE `requirements_verificationflow` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`name` text NOT NULL,
	`display_name` text NOT NULL,
	`description` text NOT NULL,
	`steps` text NOT NULL,
	`version` integer NOT NULL,
	`synced_at` text
);
--> statement-breakpoint
CREATE UNIQUE INDEX `requirements_verificationflow_name_unique` ON `requirements_verificationflow` (`name`);