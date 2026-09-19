/**
 * @file hooks/useDriftStream.ts
 * @brief React Hook —— 管理漂移诊断 WebSocket 流的生命周期与状态
 *
 * 功能：
 *  1. 自动连接 / 断开 WebSocket
 *  2. 累积漂移报告（带去重和容量限制）
 *  3. UMAP 散点快照接收
 *  4. Reviewer 日志接收 + 用户决策状态管理
 *  5. 高亮样本 ID 集合管理
 */

import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";

import {
  AgentCopilotAction,
  AgentCopilotState,
  DriftMessageType,
  DriftReport,
  DriftWsMessage,
  ReviewLogEntry,
  UmapSnapshot,
} from "../types";

// ══════════════════════════════════════════════════════════════
// 初始状态
// ══════════════════════════════════════════════════════════════

const INITIAL_STATE: AgentCopilotState = {
  connectionStatus: "disconnected",
  reports: [],
  highlightedSampleIds: new Set<string>(),
  isStreaming: false,
  lastHeartbeat: null,
  umapSnapshot: null,
  reviewLogs: [],
};

// ══════════════════════════════════════════════════════════════
// Reducer
// ══════════════════════════════════════════════════════════════

function copilotReducer(
  state: AgentCopilotState,
  action: AgentCopilotAction
): AgentCopilotState {
  switch (action.type) {
    case "WS_STATUS_CHANGED":
      return {
        ...state,
        connectionStatus: action.status,
        isStreaming: action.status === "connected" ? state.isStreaming : false,
      };

    case "REPORT_RECEIVED": {
      if (state.reports.some((r) => r.reportId === action.report.reportId)) {
        return state;
      }
      return {
        ...state,
        reports: [action.report, ...state.reports].slice(0, 100),
        // 自动高亮新增的漂移样本
        highlightedSampleIds: new Set([
          ...state.highlightedSampleIds,
          ...action.report.samples.map((s) => s.sampleId),
        ]),
      };
    }

    case "HIGHLIGHT_SAMPLES": {
      const newSet = new Set(state.highlightedSampleIds);
      for (const id of action.sampleIds) {
        if (newSet.has(id)) {
          newSet.delete(id);
        } else {
          newSet.add(id);
        }
      }
      return { ...state, highlightedSampleIds: newSet };
    }

    case "CLEAR_HIGHLIGHTS":
      return { ...state, highlightedSampleIds: new Set() };

    case "SET_STREAMING":
      return { ...state, isStreaming: action.active };

    case "HEARTBEAT_RECEIVED":
      return { ...state, lastHeartbeat: Date.now() };

    case "UMAP_RECEIVED":
      return { ...state, umapSnapshot: action.snapshot };

    case "REVIEW_LOG_RECEIVED": {
      const exists = state.reviewLogs.some(
        (l) => l.logId === action.log.logId
      );
      if (exists) return state;
      return {
        ...state,
        reviewLogs: [action.log, ...state.reviewLogs].slice(0, 50),
      };
    }

    case "USER_DECISION": {
      return {
        ...state,
        reviewLogs: state.reviewLogs.map((log) =>
          log.logId === action.logId
            ? {
                ...log,
                userDecision: action.decision,
                rejectionReason: action.reason,
              }
            : log
        ),
      };
    }

    case "RESET":
      return INITIAL_STATE;

    default:
      return state;
  }
}

// ══════════════════════════════════════════════════════════════
// WebSocket 客户端（内联实现，零外部依赖）
// ══════════════════════════════════════════════════════════════

interface WsConfig {
  reconnectBaseMs: number;
  reconnectMaxMs: number;
  heartbeatTimeoutMs: number;
}

const DEFAULT_WS_CONFIG: WsConfig = {
  reconnectBaseMs: 1000,
  reconnectMaxMs: 30000,
  heartbeatTimeoutMs: 15000,
};

// ══════════════════════════════════════════════════════════════
// Hook: useDriftStream
// ══════════════════════════════════════════════════════════════

interface UseDriftStreamOptions {
  wsEndpoint: string;
  autoConnect?: boolean;
  wsConfig?: Partial<WsConfig>;
}

interface UseDriftStreamReturn {
  state: AgentCopilotState;
  connect: () => void;
  disconnect: () => void;
  toggleHighlight: (sampleIds: string[]) => void;
  clearHighlights: () => void;
  sendUserDecision: (logId: string, decision: "accepted" | "rejected", reason?: string) => void;
  reset: () => void;
}

export function useDriftStream(
  options: UseDriftStreamOptions
): UseDriftStreamReturn {
  const { wsEndpoint, autoConnect = true, wsConfig = {} } = options;
  const config = { ...DEFAULT_WS_CONFIG, ...wsConfig };

  const [state, dispatch] = useReducer(copilotReducer, INITIAL_STATE);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heartbeatTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectAttempt = useRef(0);
  const disposed = useRef(false);

  // ── 稳定回调引用 ──────────────────────────────────────────
  const dispatchRef = useRef(dispatch);
  dispatchRef.current = dispatch;

  // ── WebSocket 连接管理 ────────────────────────────────────

  const cleanup = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
    heartbeatTimer.current = setInterval(() => {
      // 超时未收到服务端心跳 → 断线
      wsRef.current?.close();
    }, config.heartbeatTimeoutMs);
  }, [config.heartbeatTimeoutMs]);

  const scheduleReconnect = useCallback(() => {
    if (disposed.current) return;
    const delay = Math.min(
      config.reconnectBaseMs * Math.pow(2, reconnectAttempt.current),
      config.reconnectMaxMs
    );
    reconnectAttempt.current++;
    reconnectTimer.current = setTimeout(() => {
      if (!disposed.current) connectFn();
    }, delay);
  }, [config.reconnectBaseMs, config.reconnectMaxMs]);

  const connectFn = useCallback(() => {
    if (disposed.current) return;
    cleanup();
    dispatchRef.current({ type: "WS_STATUS_CHANGED", status: "connecting" });

    let ws: WebSocket;
    try {
      ws = new WebSocket(wsEndpoint);
    } catch {
      dispatchRef.current({ type: "WS_STATUS_CHANGED", status: "error" });
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      reconnectAttempt.current = 0;
      dispatchRef.current({ type: "WS_STATUS_CHANGED", status: "connected" });
      startHeartbeat();
    };

    ws.onmessage = (event: MessageEvent) => {
      // 重置心跳
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      startHeartbeat();

      let msg: DriftWsMessage;
      try {
        msg = JSON.parse(event.data as string) as DriftWsMessage;
      } catch {
        return;
      }

      switch (msg.type) {
        case DriftMessageType.DRIFT_REPORT:
          dispatchRef.current({
            type: "REPORT_RECEIVED",
            payload: msg.payload as DriftReport,
          } as unknown as AgentCopilotAction);
          break;

        case DriftMessageType.DRIFT_EVENT:
          if (Array.isArray(msg.payload)) {
            dispatchRef.current({
              type: "REPORT_RECEIVED",
              report: {
                reportId: `event-${msg.seq}`,
                timestamp: new Date().toISOString(),
                analysisMode: "cpp_bfs",
                samples: msg.payload,
                stats: {
                  totalSamples: msg.payload.length,
                  meanDistance: 0,
                  threshold: 0,
                  driftCount: msg.payload.length,
                },
              },
            } as unknown as AgentCopilotAction);
          }
          break;

        case DriftMessageType.UMAP_UPDATE:
          dispatchRef.current({
            type: "UMAP_RECEIVED",
            snapshot: msg.payload as UmapSnapshot,
          } as unknown as AgentCopilotAction);
          break;

        case DriftMessageType.REVIEW_LOG:
          dispatchRef.current({
            type: "REVIEW_LOG_RECEIVED",
            log: msg.payload as ReviewLogEntry,
          } as unknown as AgentCopilotAction);
          break;

        case DriftMessageType.HEARTBEAT:
          dispatchRef.current({ type: "HEARTBEAT_RECEIVED" } as unknown as AgentCopilotAction);
          break;
      }
    };

    ws.onclose = () => {
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      dispatchRef.current({ type: "WS_STATUS_CHANGED", status: "disconnected" });
      scheduleReconnect();
    };

    ws.onerror = () => {
      dispatchRef.current({ type: "WS_STATUS_CHANGED", status: "error" });
    };

    wsRef.current = ws;
  }, [wsEndpoint, cleanup, startHeartbeat, scheduleReconnect]);

  // ── 生命周期 ──────────────────────────────────────────────

  useEffect(() => {
    disposed.current = false;
    if (autoConnect) connectFn();
    return () => {
      disposed.current = true;
      cleanup();
    };
  }, [wsEndpoint, autoConnect, connectFn, cleanup]);

  // ── 操作 ──────────────────────────────────────────────────

  const connect = useCallback(() => {
    disposed.current = false;
    connectFn();
  }, [connectFn]);

  const disconnect = useCallback(() => {
    disposed.current = true;
    cleanup();
    dispatch({ type: "WS_STATUS_CHANGED", status: "disconnected" });
  }, [cleanup]);

  const toggleHighlight = useCallback((sampleIds: string[]) => {
    dispatch({ type: "HIGHLIGHT_SAMPLES", sampleIds });
  }, []);

  const clearHighlights = useCallback(() => {
    dispatch({ type: "CLEAR_HIGHLIGHTS" });
  }, []);

  const sendUserDecision = useCallback(
    (logId: string, decision: "accepted" | "rejected", reason?: string) => {
      dispatch({ type: "USER_DECISION", logId, decision, reason });
      // 同步发送到后端
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(
          JSON.stringify({
            type: "user_decision",
            logId,
            decision,
            reason,
          })
        );
      }
    },
    []
  );

  const reset = useCallback(() => {
    dispatch({ type: "RESET" });
  }, []);

  return useMemo(
    () => ({
      state,
      connect,
      disconnect,
      toggleHighlight,
      clearHighlights,
      sendUserDecision,
      reset,
    }),
    [state, connect, disconnect, toggleHighlight, clearHighlights, sendUserDecision, reset]
  );
}
