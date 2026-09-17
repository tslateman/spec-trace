import type * as React from "react";
import { useEffect } from "react";
import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import { Shell } from "@/client/components/layout";
import { AboutPage } from "@/client/pages/about";
import { ConflictsPageView } from "@/client/pages/conflicts";
import { CorpusReviewDetailPage } from "@/client/pages/corpus-review-detail";
import { CorpusReviewsPage } from "@/client/pages/corpus-reviews";
import { CoveragePage } from "@/client/pages/coverage";
import { DriftPage } from "@/client/pages/drift";
import { FactoryPage } from "@/client/pages/factory";
import { FlowsPage } from "@/client/pages/flows";
import { GettingStartedPage } from "@/client/pages/getting-started";
import { HighRiskPage } from "@/client/pages/high-risk";
import { ImpactPage } from "@/client/pages/impact";
import { MatrixPage } from "@/client/pages/matrix";
import { MergeSafetyPage } from "@/client/pages/merge-safety";
import { RequirementPage } from "@/client/pages/requirement";
import { RunDetailPage } from "@/client/pages/run-detail";
import { RunsPage } from "@/client/pages/runs";
import { SloStatusPage } from "@/client/pages/slo-status";
import { SpecSyntaxPage } from "@/client/pages/spec-syntax";
import { TasksPage } from "@/client/pages/tasks";
import { TestRunsPage } from "@/client/pages/test-runs";
import { VendorCoveragePage } from "@/client/pages/vendor-coverage";

function Page({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  useEffect(() => {
    document.title = `${title} · SpecTrace`;
  }, [title]);

  return (
    <Shell title={title} subtitle={subtitle}>
      {children}
    </Shell>
  );
}

function NotFound() {
  const { pathname } = useLocation();

  return (
    <div role="alert" className="rounded-lg border border-border bg-card p-6">
      <p className="text-sm font-semibold">No page lives at {pathname}.</p>
      <p className="pt-1 text-sm text-muted-foreground">Check the address, or pick a page from the sidebar.</p>
      <Link to="/" className="mt-4 inline-block text-sm font-medium text-primary hover:underline">
        Back to Coverage
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/merge-safety"
          element={
            <Page title="Merge Safety" subtitle="Impact, drift, and unresolved conflicts at a glance">
              <MergeSafetyPage />
            </Page>
          }
        />
        <Route
          path="/"
          element={
            <Page title="Coverage" subtitle="Requirements and their verification status">
              <CoveragePage />
            </Page>
          }
        />
        <Route
          path="/specs"
          element={
            <Page title="Requirements" subtitle="The requirement tree and its verification status">
              <MatrixPage />
            </Page>
          }
        />
        <Route
          path="/specs/:externalId"
          element={
            <Page title="Requirement" subtitle="Context, linked tests, and dependencies">
              <RequirementPage />
            </Page>
          }
        />
        <Route
          path="/runs"
          element={
            <Page title="Validation Runs" subtitle="Enforcement runs pushed from CI">
              <RunsPage />
            </Page>
          }
        />
        <Route
          path="/runs/:runId"
          element={
            <Page title="Validation Run" subtitle="Results, steps, and the change since the previous run">
              <RunDetailPage />
            </Page>
          }
        />
        <Route
          path="/test-runs"
          element={
            <Page title="Test Runs" subtitle="The latest JUnit run pushed from CI">
              <TestRunsPage />
            </Page>
          }
        />
        <Route
          path="/conflicts"
          element={
            <Page title="Conflicts" subtitle="Requirement pairs the detector flagged">
              <ConflictsPageView />
            </Page>
          }
        />
        <Route
          path="/impact"
          element={
            <Page title="Impact" subtitle="The last impact report pushed from a diff">
              <ImpactPage />
            </Page>
          }
        />
        <Route
          path="/drift"
          element={
            <Page title="Drift" subtitle="Stale links and spec drift from the last report">
              <DriftPage />
            </Page>
          }
        />
        <Route
          path="/flows"
          element={
            <Page title="Flows" subtitle="Verification flows running right now">
              <FlowsPage />
            </Page>
          }
        />
        <Route
          path="/high-risk"
          element={
            <Page title="High Risk" subtitle="Critical and high-risk requirements, ranked by coverage">
              <HighRiskPage />
            </Page>
          }
        />
        <Route
          path="/getting-started"
          element={
            <Page title="Getting Started" subtitle="Write a spec, link a test, push the results">
              <GettingStartedPage />
            </Page>
          }
        />
        <Route
          path="/spec-syntax"
          element={
            <Page title="Spec Syntax" subtitle="The fields a spec file accepts">
              <SpecSyntaxPage />
            </Page>
          }
        />
        <Route
          path="/about"
          element={
            <Page title="About" subtitle="What SpecTrace does and why">
              <AboutPage />
            </Page>
          }
        />
        <Route
          path="/vendor-coverage"
          element={
            <Page title="Vendor Coverage" subtitle="Integration validation pass rates by vendor">
              <VendorCoveragePage />
            </Page>
          }
        />
        <Route
          path="/corpus/reviews"
          element={
            <Page title="Corpus Reviews" subtitle="Regulatory corpus coverage reviews for requirements">
              <CorpusReviewsPage />
            </Page>
          }
        />
        <Route
          path="/corpus/reviews/:id"
          element={
            <Page title="Corpus Review" subtitle="Coverage and findings for a single review">
              <CorpusReviewDetailPage />
            </Page>
          }
        />
        <Route
          path="/slo-status"
          element={
            <Page title="SLO Status" subtitle="Service level objectives linked to requirements">
              <SloStatusPage />
            </Page>
          }
        />
        <Route
          path="/factory"
          element={
            <Page title="Factory Report" subtitle="Throughput, refusals, state durations, and intent scores">
              <FactoryPage />
            </Page>
          }
        />
        <Route
          path="/tasks"
          element={
            <Page title="Agent Tasks" subtitle="Claims, leases, and outcomes from the TaskLedger">
              <TasksPage />
            </Page>
          }
        />
        <Route
          path="*"
          element={
            <Page title="Page not found" subtitle="The address does not match any page in this dashboard">
              <NotFound />
            </Page>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
