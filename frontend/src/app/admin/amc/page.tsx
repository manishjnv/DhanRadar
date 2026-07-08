'use client';

/**
 * Admin AMC Coverage — /admin/amc
 *
 * Founder spec: ONE page reporting per-AMC × per-field DATA COVERAGE (row
 * counts / percentages only — no fund score, rating, or recommendation
 * anything). Summary strip (Total AMCs · Total Funds · NFOs · Accuracy ·
 * Overall completeness) + a compact sortable table, one row per AMC.
 *
 * Four-state contract (DataState, no-suppress): loading/error/empty/present.
 */

export const dynamic = 'force-dynamic';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardBody } from '@/components/ui/Card';
import { StatCard } from '@/components/admin/StatCard';
import { AmcCoverageTable } from '@/components/admin/AmcCoverageTable';
import { HelpTip } from '@/components/ui/HelpTip';
import { DataState } from '@/components/ui/DataState';
import { Skeleton } from '@/components/ui/Skeleton';
import { useAmcCoverage } from '@/features/admin/api';

function SummarySkeleton() {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {[...Array(5)].map((_, i) => (
        <Skeleton key={i} className="h-20 rounded-lg" />
      ))}
    </div>
  );
}

function StatCardWithTip({
  title,
  value,
  tip,
}: {
  title: string;
  value: React.ReactNode;
  tip?: string;
}) {
  return (
    <div className="relative">
      <StatCard title={title} value={value} />
      {tip && (
        <div className="absolute right-3 top-3">
          <HelpTip tip={tip} />
        </div>
      )}
    </div>
  );
}

export default function AdminAmcCoveragePage() {
  const { data, isLoading, isError, refetch } = useAmcCoverage();

  const status = isLoading ? 'loading' : isError ? 'error' : data ? 'present' : 'empty';

  return (
    <div className="flex flex-col gap-6 p-6">
      <div>
        <h1 className="text-h2 font-semibold text-ink">AMC Data Coverage</h1>
        <p className="mt-1 text-small text-ink-muted">
          Data-coverage counts only — no fund score, rating, or recommendation is shown here.
        </p>
      </div>

      <DataState status={status} onRetry={() => refetch()} skeleton={<SummarySkeleton />}>
        {data && (
          <>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              <StatCard title="Total AMCs" value={data.summary.total_amcs} />
              <StatCard
                title="Total Funds"
                value={data.summary.total_funds.toLocaleString('en-IN')}
              />
              <StatCardWithTip
                title="NFOs (6mo)"
                value={data.summary.nfo_count}
                tip={data.meta.nfo_definition}
              />
              <StatCardWithTip
                title="Accuracy"
                value={`${data.summary.accuracy_pct.toFixed(1)}%`}
                tip={data.meta.accuracy_definition}
              />
              <StatCardWithTip
                title="Overall Completeness"
                value={`${data.summary.overall_completeness_pct.toFixed(1)}%`}
                tip={data.meta.completeness_definition}
              />
            </div>

            <Card>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <CardTitle id="amc-coverage-table">Per-AMC Coverage</CardTitle>
                  <HelpTip
                    tip={`${data.meta.mode_definition} ${data.meta.freq_definition} ${data.meta.source_tag_definition}`}
                  />
                </div>
              </CardHeader>
              <CardBody>
                <AmcCoverageTable
                  rows={data.rows}
                  fieldOrder={data.meta.field_order}
                  fieldLabels={data.meta.field_labels}
                />
              </CardBody>
            </Card>
          </>
        )}
      </DataState>
    </div>
  );
}
