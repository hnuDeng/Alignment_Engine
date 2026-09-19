/**
 * @file store/datasetSlice.ts
 * @brief Dataset state management -- normalized entity store, filters,
 *        selection, and stats computation.
 *
 * Operates on the NormalizedEntities produced by DataNormalizer.
 * No external dependencies -- pure useReducer compatible.
 */

import type { DriftReport, DriftSample, ReviewLogEntry, UmapSnapshot } from "../types";
import { DataNormalizer } from "./DataNormalizer";
import type {
  DatasetFilter,
  DatasetState,
  NormalizedReviewLog,
  SeverityLevel,
} from "./types";

// ══════════════════════════════════════════════════════════════
// Initial state
// ══════════════════════════════════════════════════════════════

export const INITIAL_DATASET_STATE: DatasetState = {
  datasetName: null,
  entities: {
    samples: {},
    reports: {},
    reviewLogs: {},
  },
  currentSnapshotId: null,
  highlightedSampleIds: [],
  filter: {
    labelIds: [],
    severityLevels: [],
    driftOnly: false,
    searchQuery: "",
  },
  stats: {
    totalSamples: 0,
    driftCount: 0,
    labelDistribution: {},
    meanIsolationScore: 0,
    maxIsolationScore: 0,
  },
  reportOrder: [],
  reviewLogOrder: [],
  boxSelectedSampleIds: [],
  errors: [],
};

// ══════════════════════════════════════════════════════════════
// Action types
// ══════════════════════════════════════════════════════════════

export type DatasetAction =
  | { type: "DATASET_SET_NAME"; name: string }
  | { type: "DATASET_MERGE_REPORT"; report: DriftReport }
  | { type: "DATASET_MERGE_SAMPLES"; samples: DriftSample[]; reportId: string }
  | { type: "DATASET_REMOVE_REPORT"; reportId: string }
  | { type: "DATASET_CLEAR_ALL" }
  | { type: "DATASET_SET_SNAPSHOT"; snapshot: UmapSnapshot }
  | { type: "DATASET_CLEAR_SNAPSHOT" }
  | { type: "DATASET_MERGE_REVIEW_LOG"; log: ReviewLogEntry }
  | { type: "DATASET_UPDATE_REVIEW_LOG"; logId: string; updates: Partial<ReviewLogEntry> }
  | { type: "DATASET_REMOVE_REVIEW_LOG"; logId: string }
  | { type: "DATASET_SET_HIGHLIGHT"; sampleIds: string[] }
  | { type: "DATASET_TOGGLE_HIGHLIGHT"; sampleIds: string[] }
  | { type: "DATASET_CLEAR_HIGHLIGHT" }
  | { type: "DATASET_SET_BOX_SELECT"; sampleIds: string[] }
  | { type: "DATASET_CLEAR_BOX_SELECT" }
  | { type: "DATASET_SET_FILTER"; filter: Partial<DatasetFilter> }
  | { type: "DATASET_RESET_FILTER" }
  | { type: "DATASET_RECOMPUTE_STATS" }
  | { type: "DATASET_PUSH_ERROR"; message: string; severity: SeverityLevel }
  | { type: "DATASET_CLEAR_ERRORS" }
  | { type: "DATASET_FULL_RESET" };

// ══════════════════════════════════════════════════════════════
// Reducer
// ══════════════════════════════════════════════════════════════

export function datasetReducer(state: DatasetState, action: DatasetAction): DatasetState {
  switch (action.type) {
    case "DATASET_SET_NAME":
      return { ...state, datasetName: action.name };

    case "DATASET_MERGE_REPORT": {
      const { entities, reportOrder } = DataNormalizer.mergeReport(
        state.entities,
        action.report,
      );
      return {
        ...state,
        entities,
        reportOrder,
        stats: DataNormalizer.computeStats(entities),
      };
    }

    case "DATASET_MERGE_SAMPLES": {
      const { entities } = DataNormalizer.mergeSamples(
        state.entities,
        action.samples,
        action.reportId,
      );
      return {
        ...state,
        entities,
        stats: DataNormalizer.computeStats(entities),
      };
    }

    case "DATASET_REMOVE_REPORT": {
      const { entities, reportOrder } = DataNormalizer.removeReport(
        state.entities,
        action.reportId,
        state.reportOrder,
      );
      return {
        ...state,
        entities,
        reportOrder,
        stats: DataNormalizer.computeStats(entities),
      };
    }

    case "DATASET_CLEAR_ALL":
      return {
        ...state,
        entities: { samples: {}, reports: {}, reviewLogs: {} },
        reportOrder: [],
        reviewLogOrder: [],
        stats: { ...INITIAL_DATASET_STATE.stats },
      };

    case "DATASET_SET_SNAPSHOT":
      return { ...state, currentSnapshotId: action.snapshot.snapshotId };

    case "DATASET_CLEAR_SNAPSHOT":
      return { ...state, currentSnapshotId: null };

    case "DATASET_MERGE_REVIEW_LOG": {
      const { entities, reviewLogOrder } = DataNormalizer.mergeReviewLog(
        state.entities,
        action.log,
        state.reviewLogOrder,
      );
      return { ...state, entities, reviewLogOrder };
    }

    case "DATASET_UPDATE_REVIEW_LOG": {
      const existing = state.entities.reviewLogs[action.logId];
      if (!existing) return state;
      const updated: NormalizedReviewLog = { ...existing, ...action.updates };
      return {
        ...state,
        entities: {
          ...state.entities,
          reviewLogs: { ...state.entities.reviewLogs, [action.logId]: updated },
        },
      };
    }

    case "DATASET_REMOVE_REVIEW_LOG": {
      const { [action.logId]: _, ...rest } = state.entities.reviewLogs;
      return {
        ...state,
        entities: { ...state.entities, reviewLogs: rest },
        reviewLogOrder: state.reviewLogOrder.filter((id) => id !== action.logId),
      };
    }

    case "DATASET_SET_HIGHLIGHT":
      return { ...state, highlightedSampleIds: [...action.sampleIds] };

    case "DATASET_TOGGLE_HIGHLIGHT": {
      const set = new Set(state.highlightedSampleIds);
      for (const id of action.sampleIds) {
        if (set.has(id)) set.delete(id);
        else set.add(id);
      }
      return { ...state, highlightedSampleIds: Array.from(set) };
    }

    case "DATASET_CLEAR_HIGHLIGHT":
      return { ...state, highlightedSampleIds: [] };

    case "DATASET_SET_BOX_SELECT":
      return { ...state, boxSelectedSampleIds: [...action.sampleIds] };

    case "DATASET_CLEAR_BOX_SELECT":
      return { ...state, boxSelectedSampleIds: [] };

    case "DATASET_SET_FILTER":
      return { ...state, filter: { ...state.filter, ...action.filter } };

    case "DATASET_RESET_FILTER":
      return { ...state, filter: { ...INITIAL_DATASET_STATE.filter } };

    case "DATASET_RECOMPUTE_STATS":
      return { ...state, stats: DataNormalizer.computeStats(state.entities) };

    case "DATASET_PUSH_ERROR":
      return {
        ...state,
        errors: [
          ...state.errors,
          { timestamp: Date.now(), message: action.message, severity: action.severity },
        ],
      };

    case "DATASET_CLEAR_ERRORS":
      return { ...state, errors: [] };

    case "DATASET_FULL_RESET":
      return { ...INITIAL_DATASET_STATE };

    default:
      return state;
  }
}
