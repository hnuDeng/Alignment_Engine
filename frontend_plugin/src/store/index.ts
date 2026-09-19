/**
 * @file store/index.ts
 * @brief Store barrel -- re-exports all slices, middleware, normalizer,
 *        and types for convenient consumption.
 */

export { agentReducer, initialState as INITIAL_AGENT_STATE } from "./agentSlice";
export type { ActionType as AgentAction } from "./agentSlice";

export { datasetReducer, INITIAL_DATASET_STATE } from "./datasetSlice";
export type { DatasetAction } from "./datasetSlice";

export { socketMiddleware as SocketMiddleware } from "./socketMiddleware";

export { DataNormalizer } from "./DataNormalizer";

export type {
  AgentState,
  AnalyzerState,
  AnalyzerStatus,
  DatasetFilter,
  DatasetState,
  DatasetStats,
  ExecutionMode,
  ExtractorState,
  ExtractorStatus,
  NormalizedEntities,
  NormalizedReport,
  NormalizedReviewLog,
  NormalizedSample,
  PipelineStage,
  ReviewerState,
  ReviewerStatus,
  RootState,
  SeverityLevel,
  WsMiddlewareConfig,
  WsMiddlewareEvent,
} from "./types";

export {
  AnalyzerStatus as AnalyzerStatusEnum,
  ExecutionMode as ExecutionModeEnum,
  ExtractorStatus as ExtractorStatusEnum,
  PipelineStage as PipelineStageEnum,
  ReviewerStatus as ReviewerStatusEnum,
  SeverityLevel as SeverityLevelEnum,
} from "./types";
