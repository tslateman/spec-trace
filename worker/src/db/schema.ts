import { relations, sql } from "drizzle-orm";
import {
  type AnySQLiteColumn,
  check,
  index,
  integer,
  real,
  sqliteTable,
  text,
  unique,
  uniqueIndex,
} from "drizzle-orm/sqlite-core";

const id = () => integer("id").primaryKey({ autoIncrement: true });
const json = (name: string) => text(name, { mode: "json" });
const bool = (name: string) => integer(name, { mode: "boolean" });

export const requirements = sqliteTable(
  "requirements_requirement",
  {
    id: id(),
    path: text("path").notNull().unique(),
    depth: integer("depth").notNull(),
    numchild: integer("numchild").notNull(),
    externalId: text("external_id").notNull().unique(),
    title: text("title").notNull(),
    description: text("description").notNull(),
    tags: json("tags").notNull(),
    priority: text("priority").notNull(),
    status: text("status").notNull(),
    sourceFile: text("source_file").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    verificationStatus: text("verification_status").notNull(),
    sloStatus: text("slo_status").notNull(),
    verificationMethod: text("verification_method").notNull(),
    component: text("component").notNull(),
    condition: text("condition").notNull(),
    response: text("response").notNull(),
    scope: text("scope").notNull(),
    structureCompleteness: real("structure_completeness").notNull(),
    timing: text("timing").notNull(),
    riskLevel: text("risk_level").notNull(),
    project: text("project").notNull(),
  },
  (table) => [
    index("requirements_requirement_verification_status_idx").on(table.verificationStatus),
    index("requirements_requirement_slo_status_idx").on(table.sloStatus),
    index("requirements_requirement_verification_method_idx").on(table.verificationMethod),
    index("requirements_requirement_component_idx").on(table.component),
    index("requirements_requirement_risk_level_idx").on(table.riskLevel),
    index("requirements_requirement_project_idx").on(table.project),
    check("requirement_project_is_named", sql`NOT (${table.project} = '')`),
  ],
);

export const requirementDependsOn = sqliteTable(
  "requirements_requirement_depends_on",
  {
    id: id(),
    fromRequirementId: integer("from_requirement_id")
      .notNull()
      .references(() => requirements.id),
    toRequirementId: integer("to_requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_requirement_depends_on_uniq").on(table.fromRequirementId, table.toRequirementId),
    index("requirements_requirement_depends_on_from_requirement_id_idx").on(table.fromRequirementId),
    index("requirements_requirement_depends_on_to_requirement_id_idx").on(table.toRequirementId),
  ],
);

export const testRuns = sqliteTable(
  "requirements_testrun",
  {
    id: id(),
    importedAt: text("imported_at").notNull(),
    sourceFile: text("source_file").notNull(),
    ciJobUrl: text("ci_job_url").notNull(),
    finishedAt: text("finished_at"),
    gitBranch: text("git_branch").notNull(),
    gitSha: text("git_sha").notNull(),
    startedAt: text("started_at"),
    repository: text("repository").notNull(),
    workflowName: text("workflow_name").notNull(),
    workflowRunId: integer("workflow_run_id"),
  },
  (table) => [
    index("requirements_testrun_repository_idx").on(table.repository),
    index("requirements_testrun_workflow_run_id_idx").on(table.workflowRunId),
    index("requirements_testrun_git_sha_idx").on(table.gitSha),
  ],
);

export const testResults = sqliteTable(
  "requirements_testresult",
  {
    id: id(),
    testNodeid: text("test_nodeid").notNull(),
    classname: text("classname").notNull(),
    name: text("name").notNull(),
    time: real("time").notNull(),
    status: text("status").notNull(),
    message: text("message").notNull(),
    testRunId: integer("test_run_id")
      .notNull()
      .references(() => testRuns.id),
  },
  (table) => [
    index("requirements_testresult_test_nodeid_idx").on(table.testNodeid),
    index("requirements_testresult_test_run_id_idx").on(table.testRunId),
  ],
);

export const testResultRequirements = sqliteTable(
  "requirements_testresult_requirements",
  {
    id: id(),
    testresultId: integer("testresult_id")
      .notNull()
      .references(() => testResults.id),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_testresult_requirements_uniq").on(table.testresultId, table.requirementId),
    index("requirements_testresult_requirements_testresult_id_idx").on(table.testresultId),
    index("requirements_testresult_requirements_requirement_id_idx").on(table.requirementId),
  ],
);

export const inAppValidations = sqliteTable(
  "requirements_inappvalidation",
  {
    id: id(),
    name: text("name").notNull(),
    endpoint: text("endpoint").notNull(),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
    featureFlags: json("feature_flags").notNull(),
    vendor: text("vendor").notNull(),
  },
  (table) => [index("requirements_inappvalidation_requirement_id_idx").on(table.requirementId)],
);

export const inAppValidationRuns = sqliteTable("requirements_inappvalidationrun", {
  id: id(),
  importedAt: text("imported_at").notNull(),
  source: text("source").notNull(),
});

export const inAppValidationResults = sqliteTable(
  "requirements_inappvalidationresult",
  {
    id: id(),
    status: text("status").notNull(),
    message: text("message").notNull(),
    checkedAt: text("checked_at").notNull(),
    validationId: integer("validation_id")
      .notNull()
      .references(() => inAppValidations.id),
    validationRunId: integer("validation_run_id")
      .notNull()
      .references(() => inAppValidationRuns.id),
    context: json("context").notNull(),
    steps: json("steps").notNull(),
  },
  (table) => [
    index("requirements_inappvalidationresult_validation_id_idx").on(table.validationId),
    index("requirements_inappvalidationresult_validation_run_id_idx").on(table.validationRunId),
  ],
);

export const verificationFlows = sqliteTable("requirements_verificationflow", {
  id: id(),
  name: text("name").notNull().unique(),
  displayName: text("display_name").notNull(),
  description: text("description").notNull(),
  steps: json("steps").notNull(),
  version: integer("version").notNull(),
  syncedAt: text("synced_at"),
});

export const verificationFlowRuns = sqliteTable(
  "requirements_verificationflowrun",
  {
    id: id(),
    status: text("status").notNull(),
    context: json("context").notNull(),
    source: text("source").notNull(),
    startedAt: text("started_at").notNull(),
    completedAt: text("completed_at"),
    flowId: integer("flow_id")
      .notNull()
      .references(() => verificationFlows.id),
  },
  (table) => [
    index("requirements_verificationflowrun_status_idx").on(table.status),
    index("requirements_verificationflowrun_flow_id_idx").on(table.flowId),
  ],
);

export const verificationFlowSteps = sqliteTable(
  "requirements_verificationflowstep",
  {
    id: id(),
    stepOrder: integer("step_order").notNull(),
    name: text("name").notNull(),
    passed: bool("passed").notNull(),
    details: text("details").notNull(),
    errorMessage: text("error_message").notNull(),
    responseStatus: integer("response_status"),
    responseBody: text("response_body").notNull(),
    startedAt: text("started_at").notNull(),
    completedAt: text("completed_at").notNull(),
    flowRunId: integer("flow_run_id")
      .notNull()
      .references(() => verificationFlowRuns.id),
  },
  (table) => [
    uniqueIndex("requirements_verificationflowstep_uniq").on(table.flowRunId, table.stepOrder),
    index("requirements_verificationflowstep_flow_run_id_idx").on(table.flowRunId),
  ],
);

export const verificationFlowRequirements = sqliteTable(
  "requirements_verificationflow_requirements",
  {
    id: id(),
    verificationflowId: integer("verificationflow_id")
      .notNull()
      .references(() => verificationFlows.id),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_verificationflow_requirements_uniq").on(table.verificationflowId, table.requirementId),
    index("requirements_verificationflow_requirements_verificationflow_id_idx").on(table.verificationflowId),
    index("requirements_verificationflow_requirements_requirement_id_idx").on(table.requirementId),
  ],
);

export const testRequirementLinks = sqliteTable(
  "requirements_testrequirementlink",
  {
    id: id(),
    testNodeid: text("test_nodeid").notNull(),
    lastStatus: text("last_status").notNull(),
    lastRunAt: text("last_run_at"),
    needsReview: bool("needs_review").notNull(),
    reviewReason: text("review_reason").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_testrequirementlink_uniq").on(table.testNodeid, table.requirementId),
    index("requirements_testrequirementlink_test_nodeid_idx").on(table.testNodeid),
    index("requirements_testrequirementlink_requirement_id_idx").on(table.requirementId),
  ],
);

export const conflictLogs = sqliteTable(
  "requirements_conflictlog",
  {
    id: id(),
    pattern: text("pattern").notNull(),
    confidence: text("confidence").notNull(),
    details: json("details").notNull(),
    resolved: bool("resolved").notNull(),
    resolvedAt: text("resolved_at"),
    resolutionNotes: text("resolution_notes").notNull(),
    resolutionReason: text("resolution_reason").notNull().default("unspecified"),
    lastSeenAt: text("last_seen_at"),
    timesDetected: integer("times_detected").notNull().default(1),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    requirementAId: integer("requirement_a_id")
      .notNull()
      .references(() => requirements.id),
    requirementBId: integer("requirement_b_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    index("requirements_conflictlog_requirement_a_id_idx").on(table.requirementAId),
    index("requirements_conflictlog_requirement_b_id_idx").on(table.requirementBId),
  ],
);

export const slos = sqliteTable(
  "requirements_slo",
  {
    id: id(),
    name: text("name").notNull().unique(),
    displayName: text("display_name").notNull(),
    description: text("description").notNull(),
    service: text("service").notNull(),
    target: real("target"),
    timeWindow: text("time_window").notNull(),
    budgetingMethod: text("budgeting_method").notNull(),
    status: text("status").notNull(),
    currentValue: real("current_value"),
    errorBudgetRemaining: real("error_budget_remaining"),
    lastUpdated: text("last_updated"),
    sourceFile: text("source_file").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [index("requirements_slo_status_idx").on(table.status)],
);

export const sloRequirements = sqliteTable(
  "requirements_slo_requirements",
  {
    id: id(),
    sloId: integer("slo_id")
      .notNull()
      .references(() => slos.id),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_slo_requirements_uniq").on(table.sloId, table.requirementId),
    index("requirements_slo_requirements_slo_id_idx").on(table.sloId),
    index("requirements_slo_requirements_requirement_id_idx").on(table.requirementId),
  ],
);

export const agentSprints = sqliteTable("requirements_agentsprint", {
  id: id(),
  name: text("name").notNull(),
  description: text("description").notNull(),
  goalDescription: text("goal_description").notNull(),
  isActive: bool("is_active").notNull(),
  completedAt: text("completed_at"),
  createdAt: text("created_at").notNull(),
});

export const agents = sqliteTable(
  "requirements_agent",
  {
    id: id(),
    agentId: text("agent_id").notNull().unique(),
    role: text("role").notNull(),
    isActive: bool("is_active").notNull(),
    lastHeartbeat: text("last_heartbeat"),
    config: json("config").notNull(),
    registeredAt: text("registered_at").notNull(),
  },
  (table) => [index("requirements_agent_role_idx").on(table.role)],
);

export const agentTasks = sqliteTable(
  "requirements_agenttask",
  {
    id: id(),
    externalId: text("external_id").notNull().unique(),
    title: text("title").notNull(),
    description: text("description").notNull(),
    status: text("status").notNull(),
    claimedAt: text("claimed_at"),
    leaseExpires: text("lease_expires"),
    doneWhen: json("done_when").notNull(),
    scopeIn: json("scope_in").notNull(),
    scopeOut: json("scope_out").notNull(),
    specRef: text("spec_ref").notNull(),
    worktreePath: text("worktree_path").notNull(),
    branchName: text("branch_name").notNull(),
    commitSha: text("commit_sha").notNull(),
    mergeSha: text("merge_sha").notNull().default(""),
    attemptCount: integer("attempt_count").notNull(),
    maxAttempts: integer("max_attempts").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
    claimedById: integer("claimed_by_id").references(() => agents.id),
    sprintId: integer("sprint_id").references(() => agentSprints.id),
  },
  (table) => [
    index("requirements_agenttask_status_idx").on(table.status),
    index("requirements_agenttask_claimed_by_id_idx").on(table.claimedById),
    index("requirements_agenttask_sprint_id_idx").on(table.sprintId),
  ],
);

export const agentTaskDependsOn = sqliteTable(
  "requirements_agenttask_depends_on",
  {
    id: id(),
    fromAgenttaskId: integer("from_agenttask_id")
      .notNull()
      .references(() => agentTasks.id),
    toAgenttaskId: integer("to_agenttask_id")
      .notNull()
      .references(() => agentTasks.id),
  },
  (table) => [
    uniqueIndex("requirements_agenttask_depends_on_uniq").on(table.fromAgenttaskId, table.toAgenttaskId),
    index("requirements_agenttask_depends_on_from_agenttask_id_idx").on(table.fromAgenttaskId),
    index("requirements_agenttask_depends_on_to_agenttask_id_idx").on(table.toAgenttaskId),
  ],
);

export const agentTaskRequirements = sqliteTable(
  "requirements_agenttask_requirements",
  {
    id: id(),
    agenttaskId: integer("agenttask_id")
      .notNull()
      .references(() => agentTasks.id),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
  },
  (table) => [
    uniqueIndex("requirements_agenttask_requirements_uniq").on(table.agenttaskId, table.requirementId),
    index("requirements_agenttask_requirements_agenttask_id_idx").on(table.agenttaskId),
    index("requirements_agenttask_requirements_requirement_id_idx").on(table.requirementId),
  ],
);

export const agentTaskHistory = sqliteTable(
  "requirements_agenttaskhistory",
  {
    id: id(),
    timestamp: text("timestamp").notNull(),
    action: text("action").notNull(),
    fromStatus: text("from_status").notNull(),
    toStatus: text("to_status").notNull(),
    details: json("details").notNull(),
    agentId: integer("agent_id").references(() => agents.id),
    taskId: integer("task_id")
      .notNull()
      .references(() => agentTasks.id),
  },
  (table) => [
    index("requirements_agenttaskhistory_timestamp_idx").on(table.timestamp),
    index("requirements_agenttaskhistory_agent_id_idx").on(table.agentId),
    index("requirements_agenttaskhistory_task_id_idx").on(table.taskId),
  ],
);

export const agentTaskReviews = sqliteTable(
  "requirements_agenttaskreview",
  {
    id: id(),
    decision: text("decision").notNull(),
    commitSha: text("commit_sha").notNull(),
    doneWhenResults: json("done_when_results").notNull(),
    feedback: text("feedback").notNull(),
    blockingIssues: json("blocking_issues").notNull(),
    suggestions: json("suggestions").notNull(),
    createdAt: text("created_at").notNull(),
    reviewerId: integer("reviewer_id").references(() => agents.id),
    taskId: integer("task_id")
      .notNull()
      .references(() => agentTasks.id),
  },
  (table) => [
    index("requirements_agenttaskreview_reviewer_id_idx").on(table.reviewerId),
    index("requirements_agenttaskreview_task_id_idx").on(table.taskId),
  ],
);

export const intentValidationResults = sqliteTable(
  "requirements_intentvalidationresult",
  {
    id: id(),
    commitSha: text("commit_sha").notNull(),
    strategicScore: integer("strategic_score").notNull(),
    opportunityScore: integer("opportunity_score").notNull(),
    driftScore: integer("drift_score").notNull(),
    passed: bool("passed").notNull(),
    failureReasons: json("failure_reasons").notNull(),
    createdAt: text("created_at").notNull(),
    taskId: integer("task_id")
      .notNull()
      .references(() => agentTasks.id),
  },
  (table) => [index("requirements_intentvalidationresult_task_id_idx").on(table.taskId)],
);

export const corpusEntries = sqliteTable(
  "requirements_corpusentry",
  {
    id: id(),
    externalId: text("external_id").notNull().unique(),
    kind: text("kind").notNull(),
    title: text("title").notNull(),
    owner: text("owner").notNull(),
    status: text("status").notNull(),
    sourceFile: text("source_file").notNull(),
    createdAt: text("created_at").notNull(),
    updatedAt: text("updated_at").notNull(),
  },
  (table) => [
    index("requirements_corpusentry_kind_idx").on(table.kind),
    index("requirements_corpusentry_owner_idx").on(table.owner),
    index("requirements_corpusentry_status_idx").on(table.status),
  ],
);

export const corpusEntryVersions = sqliteTable(
  "requirements_corpusentryversion",
  {
    id: id(),
    version: integer("version").notNull(),
    body: text("body").notNull(),
    contentHash: text("content_hash").notNull(),
    appliesTo: json("applies_to").notNull(),
    checks: json("checks").notNull(),
    effectiveDate: text("effective_date"),
    sourceFile: text("source_file").notNull(),
    createdAt: text("created_at").notNull(),
    entryId: integer("entry_id")
      .notNull()
      .references(() => corpusEntries.id),
    enforcement: text("enforcement").notNull(),
    supersedesId: integer("supersedes_id").references((): AnySQLiteColumn => corpusEntryVersions.id),
  },
  (table) => [
    unique("unique_corpus_entry_version").on(table.entryId, table.version),
    index("requirements_corpusentryversion_version_idx").on(table.version),
    index("requirements_corpusentryversion_content_hash_idx").on(table.contentHash),
    index("requirements_corpusentryversion_effective_date_idx").on(table.effectiveDate),
    index("requirements_corpusentryversion_entry_id_idx").on(table.entryId),
    index("requirements_corpusentryversion_enforcement_idx").on(table.enforcement),
    index("requirements_corpusentryversion_supersedes_id_idx").on(table.supersedesId),
  ],
);

export const corpusSnapshots = sqliteTable(
  "requirements_corpussnapshot",
  {
    id: id(),
    snapshotHash: text("snapshot_hash").notNull().unique(),
    entryVersionHashes: json("entry_version_hashes").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("requirements_corpussnapshot_created_at_idx").on(table.createdAt)],
);

export const corpusSnapshotEntryVersions = sqliteTable(
  "requirements_corpussnapshot_entry_versions",
  {
    id: id(),
    corpussnapshotId: integer("corpussnapshot_id")
      .notNull()
      .references(() => corpusSnapshots.id),
    corpusentryversionId: integer("corpusentryversion_id")
      .notNull()
      .references(() => corpusEntryVersions.id),
  },
  (table) => [
    uniqueIndex("requirements_corpussnapshot_entry_versions_uniq").on(
      table.corpussnapshotId,
      table.corpusentryversionId,
    ),
    index("requirements_corpussnapshot_entry_versions_corpussnapshot_id_idx").on(table.corpussnapshotId),
    index("requirements_corpussnapshot_entry_versions_corpusentryversion_id_idx").on(table.corpusentryversionId),
  ],
);

export const specReviews = sqliteTable(
  "requirements_specreview",
  {
    id: id(),
    specFile: text("spec_file").notNull(),
    reviewer: text("reviewer").notNull(),
    outcome: text("outcome").notNull(),
    createdAt: text("created_at").notNull(),
    requirementId: integer("requirement_id")
      .notNull()
      .references(() => requirements.id),
    snapshotId: integer("snapshot_id")
      .notNull()
      .references(() => corpusSnapshots.id),
  },
  (table) => [
    index("requirements_specreview_reviewer_idx").on(table.reviewer),
    index("requirements_specreview_outcome_idx").on(table.outcome),
    index("requirements_specreview_created_at_idx").on(table.createdAt),
    index("requirements_specreview_requirement_id_idx").on(table.requirementId),
    index("requirements_specreview_snapshot_id_idx").on(table.snapshotId),
  ],
);

export const reviewCoverage = sqliteTable(
  "requirements_reviewcoverage",
  {
    id: id(),
    matchedBy: json("matched_by").notNull(),
    cited: bool("cited").notNull(),
    entryVersionId: integer("entry_version_id")
      .notNull()
      .references(() => corpusEntryVersions.id),
    reviewId: integer("review_id")
      .notNull()
      .references(() => specReviews.id),
    enforcement: text("enforcement").notNull(),
  },
  (table) => [
    unique("unique_review_coverage_row").on(table.reviewId, table.entryVersionId),
    index("requirements_reviewcoverage_cited_idx").on(table.cited),
    index("requirements_reviewcoverage_entry_version_id_idx").on(table.entryVersionId),
    index("requirements_reviewcoverage_review_id_idx").on(table.reviewId),
    index("requirements_reviewcoverage_enforcement_idx").on(table.enforcement),
  ],
);

export const reviewFindings = sqliteTable(
  "requirements_reviewfinding",
  {
    id: id(),
    findingType: text("finding_type").notNull(),
    checkId: text("check_id").notNull(),
    detail: text("detail").notNull(),
    createdAt: text("created_at").notNull(),
    entryVersionId: integer("entry_version_id")
      .notNull()
      .references(() => corpusEntryVersions.id),
    reviewId: integer("review_id")
      .notNull()
      .references(() => specReviews.id),
    enforcement: text("enforcement").notNull(),
  },
  (table) => [
    index("requirements_reviewfinding_finding_type_idx").on(table.findingType),
    index("requirements_reviewfinding_check_id_idx").on(table.checkId),
    index("requirements_reviewfinding_entry_version_id_idx").on(table.entryVersionId),
    index("requirements_reviewfinding_review_id_idx").on(table.reviewId),
    index("requirements_reviewfinding_enforcement_idx").on(table.enforcement),
  ],
);

export const requirementsRelations = relations(requirements, ({ many }) => ({
  dependsOn: many(requirementDependsOn, { relationName: "from" }),
  dependedOnBy: many(requirementDependsOn, { relationName: "to" }),
  testResultLinks: many(testResultRequirements),
  inAppValidations: many(inAppValidations),
  verificationFlowLinks: many(verificationFlowRequirements),
  testRequirementLinks: many(testRequirementLinks),
  conflictsAsA: many(conflictLogs, { relationName: "a" }),
  conflictsAsB: many(conflictLogs, { relationName: "b" }),
  sloLinks: many(sloRequirements),
  agentTaskLinks: many(agentTaskRequirements),
  specReviews: many(specReviews),
}));

export const requirementDependsOnRelations = relations(requirementDependsOn, ({ one }) => ({
  from: one(requirements, {
    fields: [requirementDependsOn.fromRequirementId],
    references: [requirements.id],
    relationName: "from",
  }),
  to: one(requirements, {
    fields: [requirementDependsOn.toRequirementId],
    references: [requirements.id],
    relationName: "to",
  }),
}));

export const testRunsRelations = relations(testRuns, ({ many }) => ({
  results: many(testResults),
}));

export const testResultsRelations = relations(testResults, ({ one, many }) => ({
  testRun: one(testRuns, { fields: [testResults.testRunId], references: [testRuns.id] }),
  requirementLinks: many(testResultRequirements),
}));

export const testResultRequirementsRelations = relations(testResultRequirements, ({ one }) => ({
  testResult: one(testResults, {
    fields: [testResultRequirements.testresultId],
    references: [testResults.id],
  }),
  requirement: one(requirements, {
    fields: [testResultRequirements.requirementId],
    references: [requirements.id],
  }),
}));

export const inAppValidationsRelations = relations(inAppValidations, ({ one, many }) => ({
  requirement: one(requirements, {
    fields: [inAppValidations.requirementId],
    references: [requirements.id],
  }),
  results: many(inAppValidationResults),
}));

export const inAppValidationRunsRelations = relations(inAppValidationRuns, ({ many }) => ({
  results: many(inAppValidationResults),
}));

export const inAppValidationResultsRelations = relations(inAppValidationResults, ({ one }) => ({
  validation: one(inAppValidations, {
    fields: [inAppValidationResults.validationId],
    references: [inAppValidations.id],
  }),
  validationRun: one(inAppValidationRuns, {
    fields: [inAppValidationResults.validationRunId],
    references: [inAppValidationRuns.id],
  }),
}));

export const verificationFlowsRelations = relations(verificationFlows, ({ many }) => ({
  runs: many(verificationFlowRuns),
  requirementLinks: many(verificationFlowRequirements),
}));

export const verificationFlowRunsRelations = relations(verificationFlowRuns, ({ one, many }) => ({
  flow: one(verificationFlows, {
    fields: [verificationFlowRuns.flowId],
    references: [verificationFlows.id],
  }),
  steps: many(verificationFlowSteps),
}));

export const verificationFlowStepsRelations = relations(verificationFlowSteps, ({ one }) => ({
  flowRun: one(verificationFlowRuns, {
    fields: [verificationFlowSteps.flowRunId],
    references: [verificationFlowRuns.id],
  }),
}));

export const verificationFlowRequirementsRelations = relations(verificationFlowRequirements, ({ one }) => ({
  flow: one(verificationFlows, {
    fields: [verificationFlowRequirements.verificationflowId],
    references: [verificationFlows.id],
  }),
  requirement: one(requirements, {
    fields: [verificationFlowRequirements.requirementId],
    references: [requirements.id],
  }),
}));

export const testRequirementLinksRelations = relations(testRequirementLinks, ({ one }) => ({
  requirement: one(requirements, {
    fields: [testRequirementLinks.requirementId],
    references: [requirements.id],
  }),
}));

export const conflictLogsRelations = relations(conflictLogs, ({ one }) => ({
  requirementA: one(requirements, {
    fields: [conflictLogs.requirementAId],
    references: [requirements.id],
    relationName: "a",
  }),
  requirementB: one(requirements, {
    fields: [conflictLogs.requirementBId],
    references: [requirements.id],
    relationName: "b",
  }),
}));

export const slosRelations = relations(slos, ({ many }) => ({
  requirementLinks: many(sloRequirements),
}));

export const sloRequirementsRelations = relations(sloRequirements, ({ one }) => ({
  slo: one(slos, { fields: [sloRequirements.sloId], references: [slos.id] }),
  requirement: one(requirements, {
    fields: [sloRequirements.requirementId],
    references: [requirements.id],
  }),
}));

export const agentSprintsRelations = relations(agentSprints, ({ many }) => ({
  tasks: many(agentTasks),
}));

export const agentsRelations = relations(agents, ({ many }) => ({
  claimedTasks: many(agentTasks),
  history: many(agentTaskHistory),
  reviews: many(agentTaskReviews),
}));

export const agentTasksRelations = relations(agentTasks, ({ one, many }) => ({
  claimedBy: one(agents, { fields: [agentTasks.claimedById], references: [agents.id] }),
  sprint: one(agentSprints, { fields: [agentTasks.sprintId], references: [agentSprints.id] }),
  dependsOn: many(agentTaskDependsOn, { relationName: "from" }),
  dependedOnBy: many(agentTaskDependsOn, { relationName: "to" }),
  requirementLinks: many(agentTaskRequirements),
  history: many(agentTaskHistory),
  reviews: many(agentTaskReviews),
  intentValidations: many(intentValidationResults),
}));

export const agentTaskDependsOnRelations = relations(agentTaskDependsOn, ({ one }) => ({
  from: one(agentTasks, {
    fields: [agentTaskDependsOn.fromAgenttaskId],
    references: [agentTasks.id],
    relationName: "from",
  }),
  to: one(agentTasks, {
    fields: [agentTaskDependsOn.toAgenttaskId],
    references: [agentTasks.id],
    relationName: "to",
  }),
}));

export const agentTaskRequirementsRelations = relations(agentTaskRequirements, ({ one }) => ({
  task: one(agentTasks, { fields: [agentTaskRequirements.agenttaskId], references: [agentTasks.id] }),
  requirement: one(requirements, {
    fields: [agentTaskRequirements.requirementId],
    references: [requirements.id],
  }),
}));

export const agentTaskHistoryRelations = relations(agentTaskHistory, ({ one }) => ({
  agent: one(agents, { fields: [agentTaskHistory.agentId], references: [agents.id] }),
  task: one(agentTasks, { fields: [agentTaskHistory.taskId], references: [agentTasks.id] }),
}));

export const agentTaskReviewsRelations = relations(agentTaskReviews, ({ one }) => ({
  reviewer: one(agents, { fields: [agentTaskReviews.reviewerId], references: [agents.id] }),
  task: one(agentTasks, { fields: [agentTaskReviews.taskId], references: [agentTasks.id] }),
}));

export const intentValidationResultsRelations = relations(intentValidationResults, ({ one }) => ({
  task: one(agentTasks, { fields: [intentValidationResults.taskId], references: [agentTasks.id] }),
}));

export const corpusEntriesRelations = relations(corpusEntries, ({ many }) => ({
  versions: many(corpusEntryVersions),
}));

export const corpusEntryVersionsRelations = relations(corpusEntryVersions, ({ one, many }) => ({
  entry: one(corpusEntries, { fields: [corpusEntryVersions.entryId], references: [corpusEntries.id] }),
  supersedes: one(corpusEntryVersions, {
    fields: [corpusEntryVersions.supersedesId],
    references: [corpusEntryVersions.id],
    relationName: "supersedes",
  }),
  supersededBy: many(corpusEntryVersions, { relationName: "supersedes" }),
  snapshotLinks: many(corpusSnapshotEntryVersions),
  coverage: many(reviewCoverage),
  findings: many(reviewFindings),
}));

export const corpusSnapshotsRelations = relations(corpusSnapshots, ({ many }) => ({
  entryVersionLinks: many(corpusSnapshotEntryVersions),
  specReviews: many(specReviews),
}));

export const corpusSnapshotEntryVersionsRelations = relations(corpusSnapshotEntryVersions, ({ one }) => ({
  snapshot: one(corpusSnapshots, {
    fields: [corpusSnapshotEntryVersions.corpussnapshotId],
    references: [corpusSnapshots.id],
  }),
  entryVersion: one(corpusEntryVersions, {
    fields: [corpusSnapshotEntryVersions.corpusentryversionId],
    references: [corpusEntryVersions.id],
  }),
}));

export const specReviewsRelations = relations(specReviews, ({ one, many }) => ({
  requirement: one(requirements, {
    fields: [specReviews.requirementId],
    references: [requirements.id],
  }),
  snapshot: one(corpusSnapshots, {
    fields: [specReviews.snapshotId],
    references: [corpusSnapshots.id],
  }),
  coverage: many(reviewCoverage),
  findings: many(reviewFindings),
}));

export const reviewCoverageRelations = relations(reviewCoverage, ({ one }) => ({
  entryVersion: one(corpusEntryVersions, {
    fields: [reviewCoverage.entryVersionId],
    references: [corpusEntryVersions.id],
  }),
  review: one(specReviews, { fields: [reviewCoverage.reviewId], references: [specReviews.id] }),
}));

export const reviewFindingsRelations = relations(reviewFindings, ({ one }) => ({
  entryVersion: one(corpusEntryVersions, {
    fields: [reviewFindings.entryVersionId],
    references: [corpusEntryVersions.id],
  }),
  review: one(specReviews, { fields: [reviewFindings.reviewId], references: [specReviews.id] }),
}));

export const taskOutcomes = sqliteTable(
  "worker_task_outcomes",
  {
    id: id(),
    project: text("project").notNull(),
    taskExternalId: text("task_external_id").notNull(),
    status: text("status").notNull(),
    payload: json("payload").notNull(),
    drainedAt: text("drained_at"),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("worker_task_outcomes_project_id_idx").on(table.project, table.id)],
);

export const impactReports = sqliteTable(
  "worker_impact_reports",
  {
    id: id(),
    project: text("project").notNull(),
    baseRef: text("base_ref").notNull(),
    headRef: text("head_ref").notNull(),
    payload: json("payload").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("worker_impact_reports_project_created_idx").on(table.project, table.createdAt)],
);

export const driftReports = sqliteTable(
  "worker_drift_reports",
  {
    id: id(),
    project: text("project").notNull(),
    payload: json("payload").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("worker_drift_reports_project_created_idx").on(table.project, table.createdAt)],
);

export const coverageSnapshots = sqliteTable(
  "worker_coverage_snapshots",
  {
    id: id(),
    project: text("project").notNull(),
    commitSha: text("commit_sha").notNull(),
    gitBranch: text("git_branch").notNull(),
    specificationRate: real("specification_rate").notNull(),
    structureRate: real("structure_rate").notNull(),
    verificationRate: real("verification_rate").notNull(),
    total: integer("total").notNull(),
    nonDraft: integer("non_draft").notNull(),
    passing: integer("passing").notNull(),
    generatedAt: text("generated_at").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [index("worker_coverage_snapshots_project_generated_idx").on(table.project, table.generatedAt)],
);

export const taskGateRefusals = sqliteTable(
  "worker_task_gate_refusals",
  {
    id: id(),
    project: text("project").notNull(),
    taskExternalId: text("task_external_id").notNull(),
    operation: text("operation").notNull(),
    code: text("code").notNull(),
    message: text("message").notNull(),
    createdAt: text("created_at").notNull(),
  },
  (table) => [
    index("worker_task_gate_refusals_project_created_idx").on(table.project, table.createdAt),
    index("worker_task_gate_refusals_code_idx").on(table.code),
  ],
);
