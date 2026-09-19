/**
 * @file store/DataNormalizer.ts
 * @brief Frontend memory database -- normalizes nested JSON from the backend
 *        into flat, ID-indexed entity maps to prevent full React re-renders.
 *
 * Design:
 *  - All entities stored in flat Record<string, T> maps keyed by their ID.
 *  - Reports reference samples by ID (not inline arrays).
 *  - O(1) lookup by ID; O(1) insert/delete; O(N) batch merge.
 *  - Immutable merge pattern: every operation returns new objects.
 *  - computeStats() is memoization-safe (callers can diff the result).
 *
 * No external dependencies.
 */

import type { DriftReport, DriftSample, ReviewLogEntry } from "../types";
import type {
  DatasetStats,
  ExecutionMode,
  NormalizedEntities,
  NormalizedReport,
  NormalizedReviewLog,
  NormalizedSample,
} from "./types";

// ══════════════════════════════════════════════════════════════
// DataNormalizer -- static utility class
// ══════════════════════════════════════════════════════════════

export class DataNormalizer {

  // ── Merge a full DriftReport (samples + report entity) ─────

  static mergeReport(
    entities: NormalizedEntities,
    report: DriftReport,
  ): { entities: NormalizedEntities; reportOrder: string[] } {
    // 1. Flatten samples
    const newSamples: Record<string, NormalizedSample> = { ...entities.samples };
    const sampleIds: string[] = [];

    for (let i = 0; i < report.samples.length; i++) {
      const s = report.samples[i];
      sampleIds.push(s.sampleId);
      newSamples[s.sampleId] = {
        sampleId: s.sampleId,
        label: "", // will be populated from UMAP data if available
        labelId: 0,
        embedding: null,
        isDrift: true,
        isolationScore: s.isolationScore,
        centroidDistance: s.centroidDistance,
        reason: s.reason,
        severity: s.severity,
        reportId: report.reportId,
        pointIndex: i,
      };
    }

    // 2. Create normalized report
    const normalizedReport: NormalizedReport = {
      reportId: report.reportId,
      timestamp: report.timestamp,
      analysisMode: report.analysisMode as ExecutionMode,
      stats: report.stats,
      sampleIds,
    };

    // 3. Merge report entity
    const newReports: Record<string, NormalizedReport> = {
      ...entities.reports,
      [report.reportId]: normalizedReport,
    };

    // 4. Prepend to report order (newest first)
    const reportOrder = [
      report.reportId,
      ...((entities as unknown as { _reportOrder?: string[] })._reportOrder ?? []),
    ];
    // Deduplicate
    const seen = new Set<string>();
    const dedupedOrder: string[] = [];
    for (const id of reportOrder) {
      if (!seen.has(id)) {
        seen.add(id);
        dedupedOrder.push(id);
      }
    }

    return {
      entities: {
        samples: newSamples,
        reports: newReports,
        reviewLogs: entities.reviewLogs,
      },
      reportOrder: dedupedOrder,
    };
  }

  // ── Merge samples without a full report ────────────────────

  static mergeSamples(
    entities: NormalizedEntities,
    samples: DriftSample[],
    reportId: string,
  ): { entities: NormalizedEntities } {
    const newSamples: Record<string, NormalizedSample> = { ...entities.samples };

    for (let i = 0; i < samples.length; i++) {
      const s = samples[i];
      newSamples[s.sampleId] = {
        sampleId: s.sampleId,
        label: "",
        labelId: 0,
        embedding: null,
        isDrift: true,
        isolationScore: s.isolationScore,
        centroidDistance: s.centroidDistance,
        reason: s.reason,
        severity: s.severity,
        reportId,
        pointIndex: i,
      };
    }

    return {
      entities: {
        ...entities,
        samples: newSamples,
      },
    };
  }

  // ── Remove a report and its associated samples ─────────────

  static removeReport(
    entities: NormalizedEntities,
    reportId: string,
    reportOrder: string[],
  ): { entities: NormalizedEntities; reportOrder: string[] } {
    // Remove report
    const { [reportId]: _, ...remainingReports } = entities.reports;

    // Remove associated samples
    const remainingSamples: Record<string, NormalizedSample> = {};
    for (const [id, sample] of Object.entries(entities.samples)) {
      if (sample.reportId !== reportId) {
        remainingSamples[id] = sample;
      }
    }

    return {
      entities: {
        samples: remainingSamples,
        reports: remainingReports,
        reviewLogs: entities.reviewLogs,
      },
      reportOrder: reportOrder.filter((id) => id !== reportId),
    };
  }

  // ── Merge a review log entry ───────────────────────────────

  static mergeReviewLog(
    entities: NormalizedEntities,
    log: ReviewLogEntry,
    reviewLogOrder: string[],
  ): { entities: NormalizedEntities; reviewLogOrder: string[] } {
    const normalized: NormalizedReviewLog = {
      logId: log.logId,
      reportId: log.reportId,
      timestamp: log.timestamp,
      generatedScript: log.generatedScript,
      astCheckPassed: log.astCheckPassed,
      astIssues: log.astIssues,
      sandboxSuccess: log.sandboxSuccess,
      sandboxLog: log.sandboxLog,
      sandboxTimeMs: log.sandboxTimeMs,
      userDecision: log.userDecision,
      rejectionReason: log.rejectionReason,
    };

    const newOrder = reviewLogOrder.includes(log.logId)
      ? reviewLogOrder
      : [log.logId, ...reviewLogOrder];

    return {
      entities: {
        ...entities,
        reviewLogs: {
          ...entities.reviewLogs,
          [log.logId]: normalized,
        },
      },
      reviewLogOrder: newOrder,
    };
  }

  // ── Enrich samples with UMAP point data ────────────────────

  static enrichSamplesWithUmap(
    entities: NormalizedEntities,
    points: Array<{
      sampleId: string;
      label: string;
      labelId: number;
      x: number;
      y: number;
    }>,
  ): NormalizedEntities {
    const newSamples: Record<string, NormalizedSample> = { ...entities.samples };

    for (const pt of points) {
      const existing = newSamples[pt.sampleId];
      if (existing) {
        newSamples[pt.sampleId] = {
          ...existing,
          label: pt.label,
          labelId: pt.labelId,
        };
      }
    }

    return { ...entities, samples: newSamples };
  }

  // ── Compute aggregate stats ────────────────────────────────

  static computeStats(entities: NormalizedEntities): DatasetStats {
    const samples = Object.values(entities.samples);
    const totalSamples = samples.length;
    const driftSamples = samples.filter((s) => s.isDrift);
    const driftCount = driftSamples.length;

    const labelDistribution: Record<number, number> = {};
    let scoreSum = 0;
    let maxScore = 0;

    for (const s of samples) {
      labelDistribution[s.labelId] = (labelDistribution[s.labelId] ?? 0) + 1;
      scoreSum += s.isolationScore;
      if (s.isolationScore > maxScore) maxScore = s.isolationScore;
    }

    return {
      totalSamples,
      driftCount,
      labelDistribution,
      meanIsolationScore: totalSamples > 0 ? scoreSum / totalSamples : 0,
      maxIsolationScore: maxScore,
    };
  }

  // ── Batch merge multiple reports ───────────────────────────

  static batchMergeReports(
    entities: NormalizedEntities,
    reports: DriftReport[],
    existingOrder: string[],
  ): { entities: NormalizedEntities; reportOrder: string[] } {
    let currentEntities = entities;
    let currentOrder = existingOrder;

    for (const report of reports) {
      const result = DataNormalizer.mergeReport(currentEntities, report);
      currentEntities = result.entities;
      currentOrder = result.reportOrder;
    }

    return { entities: currentEntities, reportOrder: currentOrder };
  }

  // ── Query helpers ──────────────────────────────────────────

  /** Get samples belonging to a specific report */
  static getReportSamples(
    entities: NormalizedEntities,
    reportId: string,
  ): NormalizedSample[] {
    const report = entities.reports[reportId];
    if (!report) return [];
    return report.sampleIds
      .map((id) => entities.samples[id])
      .filter(Boolean);
  }

  /** Get review logs for a specific report */
  static getReportReviewLogs(
    entities: NormalizedEntities,
    reportId: string,
  ): NormalizedReviewLog[] {
    return Object.values(entities.reviewLogs).filter(
      (log) => log.reportId === reportId,
    );
  }

  /** Filter samples by severity */
  static filterBySeverity(
    entities: NormalizedEntities,
    severities: string[],
  ): NormalizedSample[] {
    return Object.values(entities.samples).filter(
      (s) => severities.includes(s.severity),
    );
  }

  /** Get the top N most isolated samples */
  static getTopIsolated(
    entities: NormalizedEntities,
    n: number,
  ): NormalizedSample[] {
    return Object.values(entities.samples)
      .sort((a, b) => b.isolationScore - a.isolationScore)
      .slice(0, n);
  }

  /** Entity count summary */
  static getEntityCounts(entities: NormalizedEntities): {
    samples: number;
    reports: number;
    reviewLogs: number;
  } {
    return {
      samples: Object.keys(entities.samples).length,
      reports: Object.keys(entities.reports).length,
      reviewLogs: Object.keys(entities.reviewLogs).length,
    };
  }
}
