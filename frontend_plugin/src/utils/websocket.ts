/**
 * @file utils/websocket.ts
 * @brief WebSocket 客户端封装 —— 支持自动重连、心跳、消息解析
 *
 * 设计原则：
 *  - 零外部依赖（原生 WebSocket API）
 *  - 指数退避重连策略（最大间隔 30s）
 *  - 心跳超时检测（默认 15s 无消息视为断线）
 *  - 类型安全的消息分发
 */

import {
  DriftMessageType,
  DriftReport,
  DriftWsMessage,
  WsConnectionStatus,
} from "../types";

/** WebSocket 事件回调接口 */
export interface DriftWsCallbacks {
  onStatusChange: (status: WsConnectionStatus) => void;
  onReport: (report: DriftReport) => void;
  onHeartbeat: () => void;
  onError?: (error: Event) => void;
}

/** 连接配置 */
interface DriftWsConfig {
  /** 重连基础间隔（ms） */
  reconnectBaseMs: number;
  /** 重连最大间隔（ms） */
  reconnectMaxMs: number;
  /** 心跳超时（ms） */
  heartbeatTimeoutMs: number;
}

const DEFAULT_CONFIG: DriftWsConfig = {
  reconnectBaseMs: 1000,
  reconnectMaxMs: 30000,
  heartbeatTimeoutMs: 15000,
};

/**
 * Drift WebSocket 客户端
 *
 * 管理与后端 Analyzer 智能体之间的 WebSocket 连接，
 * 负责接收漂移诊断流并分发给 UI 组件。
 */
export class DriftWsClient {
  private ws: WebSocket | null = null;
  private readonly endpoint: string;
  private readonly callbacks: DriftWsCallbacks;
  private readonly config: DriftWsConfig;

  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private disposed = false;
  private lastSeq = 0;

  constructor(
    endpoint: string,
    callbacks: DriftWsCallbacks,
    config: Partial<DriftWsConfig> = {}
  ) {
    this.endpoint = endpoint;
    this.callbacks = callbacks;
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /** 发起连接 */
  connect(): void {
    if (this.disposed) return;
    this.cleanup();
    this.setStatus("connecting");

    try {
      this.ws = new WebSocket(this.endpoint);
    } catch {
      this.setStatus("error");
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = this.handleOpen.bind(this);
    this.ws.onmessage = this.handleMessage.bind(this);
    this.ws.onclose = this.handleClose.bind(this);
    this.ws.onerror = this.handleError.bind(this);
  }

  /** 关闭连接并释放资源 */
  dispose(): void {
    this.disposed = true;
    this.cleanup();
    this.setStatus("disconnected");
  }

  /** 获取当前连接状态 */
  get connectionStatus(): WsConnectionStatus {
    if (!this.ws) return "disconnected";
    switch (this.ws.readyState) {
      case WebSocket.CONNECTING:   return "connecting";
      case WebSocket.OPEN:         return "connected";
      case WebSocket.CLOSING:
      case WebSocket.CLOSED:       return "disconnected";
      default:                     return "disconnected";
    }
  }

  /** 最后收到的消息序号（用于重连增量同步） */
  get lastSequence(): number {
    return this.lastSeq;
  }

  // ── 内部方法 ───────────────────────────────────────────────

  private handleOpen(): void {
    this.reconnectAttempt = 0;
    this.setStatus("connected");
    this.startHeartbeat();

    // 发送重连同步请求
    if (this.lastSeq > 0) {
      this.send({ reconnect_after_seq: this.lastSeq });
    }
  }

  private handleMessage(event: MessageEvent): void {
    this.resetHeartbeat();

    let msg: DriftWsMessage;
    try {
      msg = JSON.parse(event.data as string) as DriftWsMessage;
    } catch {
      console.warn("[DriftWsClient] Failed to parse message:", event.data);
      return;
    }

    this.lastSeq = Math.max(this.lastSeq, msg.seq);

    switch (msg.type) {
      case DriftMessageType.DRIFT_REPORT:
        this.callbacks.onReport(msg.payload as DriftReport);
        break;

      case DriftMessageType.DRIFT_EVENT:
        // 单事件包装为 mini-report
        if (Array.isArray(msg.payload)) {
          this.callbacks.onReport({
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
          });
        }
        break;

      case DriftMessageType.HEARTBEAT:
        this.callbacks.onHeartbeat();
        break;

      case DriftMessageType.STREAM_START:
      case DriftMessageType.STREAM_END:
        // informational — no-op
        break;
    }
  }

  private handleClose(): void {
    this.stopHeartbeat();
    this.setStatus("disconnected");
    this.scheduleReconnect();
  }

  private handleError(event: Event): void {
    console.error("[DriftWsClient] WebSocket error:", event);
    this.setStatus("error");
    this.callbacks.onError?.(event);
  }

  private send(data: Record<string, unknown>): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  // ── 心跳管理 ──────────────────────────────────────────────

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      // 超时未收到服务端心跳 → 视为断线
      this.ws?.close();
    }, this.config.heartbeatTimeoutMs);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private resetHeartbeat(): void {
    this.startHeartbeat();
  }

  // ── 重连策略 ──────────────────────────────────────────────

  private scheduleReconnect(): void {
    if (this.disposed) return;
    const delay = Math.min(
      this.config.reconnectBaseMs * Math.pow(2, this.reconnectAttempt),
      this.config.reconnectMaxMs
    );
    this.reconnectAttempt++;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  // ── 清理 ──────────────────────────────────────────────────

  private cleanup(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      if (
        this.ws.readyState === WebSocket.OPEN ||
        this.ws.readyState === WebSocket.CONNECTING
      ) {
        this.ws.close();
      }
      this.ws = null;
    }
  }

  private setStatus(status: WsConnectionStatus): void {
    this.callbacks.onStatusChange(status);
  }
}
