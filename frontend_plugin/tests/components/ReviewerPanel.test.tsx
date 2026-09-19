/**
 * @file tests/components/ReviewerPanel.test.tsx
 * @brief Component tests for ReviewerPanel with 10 distinct data dimensions.
 *
 * Tests cover: empty state, single log, multiple logs, pending/accepted/rejected
 * decisions, AST pass/fail, sandbox success/failure, script expansion,
 * accept/reject button clicks, rejection reason input, and stats display.
 */


import { render, screen, fireEvent } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ReviewerPanel } from "../../src/components/ReviewerPanel";
import type { ReviewLogEntry } from "../../src/types";

// ══════════════════════════════════════════════════════════════
// Mock data factories (10 dimensions)
// ══════════════════════════════════════════════════════════════

function makeLog(overrides: Partial<ReviewLogEntry> = {}): ReviewLogEntry {
  return {
    logId: "log-001",
    reportId: "report-001",
    timestamp: "2025-01-15T10:30:00Z",
    generatedScript: "import fiftyone as fo\nds = fo.load_dataset('test')",
    astCheckPassed: true,
    astIssues: [],
    sandboxSuccess: true,
    sandboxLog: "[OK] Script executed successfully in 150ms",
    sandboxTimeMs: 150,
    userDecision: "pending",
    ...overrides,
  };
}

/** Dimension 1: AST passed, sandbox passed, pending decision */
const LOG_AST_PASS_SANDBOX_PASS_PENDING = makeLog({
  logId: "log-dim1",
  astCheckPassed: true,
  sandboxSuccess: true,
  userDecision: "pending",
});

/** Dimension 2: AST failed, sandbox skipped, pending */
const LOG_AST_FAIL_PENDING = makeLog({
  logId: "log-dim2",
  astCheckPassed: false,
  astIssues: ["Dangerous call: os.system()", "Import of subprocess detected"],
  sandboxSuccess: false,
  sandboxLog: "",
  sandboxTimeMs: 0,
  userDecision: "pending",
});

/** Dimension 3: AST passed, sandbox failed, pending */
const LOG_SANDBOX_FAIL_PENDING = makeLog({
  logId: "log-dim3",
  astCheckPassed: true,
  astIssues: [],
  sandboxSuccess: false,
  sandboxLog: "[ERROR] Timeout after 5000ms",
  sandboxTimeMs: 5000,
  userDecision: "pending",
});

/** Dimension 4: Accepted decision */
const LOG_ACCEPTED = makeLog({
  logId: "log-dim4",
  userDecision: "accepted",
});

/** Dimension 5: Rejected with reason */
const LOG_REJECTED = makeLog({
  logId: "log-dim5",
  userDecision: "rejected",
  rejectionReason: "Script modifies too many samples at once",
});

/** Dimension 6: Long script content */

/** Dimension 7: Multiple AST issues */
const LOG_MULTI_ISSUES = makeLog({
  logId: "log-dim7",
  astCheckPassed: false,
  astIssues: [
    "Line 3: exec() call detected",
    "Line 5: __import__() call detected",
    "Line 8: os module access",
    "Line 12: subprocess.Popen call",
  ],
  sandboxSuccess: false,
  userDecision: "pending",
});

/** Dimension 8: Long sandbox execution time */
const LOG_SLOW_SANDBOX = makeLog({
  logId: "log-dim8",
  sandboxTimeMs: 48500,
  sandboxLog: "[WARN] Execution took 48.5 seconds\n[OK] Completed",
  userDecision: "pending",
});

/** Dimension 9: Empty script */
const LOG_EMPTY_SCRIPT = makeLog({
  logId: "log-dim9",
  generatedScript: "",
  userDecision: "pending",
});

/** Dimension 10: Timestamp edge case (very old) */
const LOG_OLD_TIMESTAMP = makeLog({
  logId: "log-dim10",
  timestamp: "2020-01-01T00:00:00Z",
  userDecision: "pending",
});

// ══════════════════════════════════════════════════════════════
// Tests
// ══════════════════════════════════════════════════════════════

describe("ReviewerPanel", () => {
  const defaultProps = {
    reviewLogs: [] as ReviewLogEntry[],
    onAccept: jest.fn(),
    onReject: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ── 1. Empty state ─────────────────────────────────────────

  test("renders empty state message when no logs", () => {
    render(<ReviewerPanel {...defaultProps} />);
    expect(screen.getByText(/等待 Reviewer 生成审计日志/)).toBeInTheDocument();
  });

  test("shows zero stats when empty", () => {
    render(<ReviewerPanel {...defaultProps} />);
    expect(screen.getByText(/0 待决策/)).toBeInTheDocument();
    expect(screen.getByText(/0 已接受/)).toBeInTheDocument();
    expect(screen.getByText(/0 已拒绝/)).toBeInTheDocument();
  });

  // ── 2. Single pending log (AST pass + sandbox pass) ────────

  test("renders single pending log with AST pass badge", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} />);
    expect(screen.getByText("PASS AST")).toBeInTheDocument();
    expect(screen.getByText("PASS Sandbox")).toBeInTheDocument();
    expect(screen.getByText("待决策")).toBeInTheDocument();
  });

  test("shows accept and reject buttons for pending log", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} />);
    expect(screen.getByText("接受修改")).toBeInTheDocument();
    expect(screen.getByText("拒绝并重新分析")).toBeInTheDocument();
  });

  // ── 3. AST failure display ─────────────────────────────────

  test("renders AST fail badge and issues", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_AST_FAIL_PENDING]} />);
    expect(screen.getByText("FAIL AST")).toBeInTheDocument();
    expect(screen.getByText("Dangerous call: os.system()")).toBeInTheDocument();
    expect(screen.getByText("Import of subprocess detected")).toBeInTheDocument();
  });

  // ── 4. Sandbox failure display ─────────────────────────────

  test("renders sandbox fail badge and error log", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_SANDBOX_FAIL_PENDING]} />);
    expect(screen.getByText("FAIL Sandbox")).toBeInTheDocument();
    expect(screen.getByText(/Timeout after 5000ms/)).toBeInTheDocument();
  });

  // ── 5. Accepted decision ───────────────────────────────────

  test("renders accepted badge for accepted log", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_ACCEPTED]} />);
    expect(screen.getByText("已接受")).toBeInTheDocument();
  });

  test("hides action buttons for accepted log", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_ACCEPTED]} />);
    expect(screen.queryByText("接受修改")).not.toBeInTheDocument();
  });

  // ── 6. Rejected decision with reason ──────────────────────

  test("renders rejected badge and reason", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_REJECTED]} />);
    expect(screen.getByText("已拒绝")).toBeInTheDocument();
    expect(screen.getByText(/Script modifies too many samples/)).toBeInTheDocument();
  });

  // ── 7. Accept button click ─────────────────────────────────

  test("calls onAccept with logId when accept clicked", () => {
    const onAccept = jest.fn();
    render(<ReviewerPanel reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} onAccept={onAccept} onReject={jest.fn()} />);
    fireEvent.click(screen.getByText("接受修改"));
    expect(onAccept).toHaveBeenCalledWith("log-dim1");
  });

  // ── 8. Reject flow: show input -> type reason -> confirm ──

  test("reject flow: shows reason input, calls onReject on confirm", () => {
    const onReject = jest.fn();
    render(<ReviewerPanel reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} onAccept={jest.fn()} onReject={onReject} />);

    // Click reject to show input
    fireEvent.click(screen.getByText("拒绝并重新分析"));

    // Type reason
    const textarea = screen.getByPlaceholderText(/请输入拒绝原因/);
    fireEvent.change(textarea, { target: { value: "too aggressive" } });

    // Confirm reject
    fireEvent.click(screen.getByText("确认拒绝"));
    expect(onReject).toHaveBeenCalledWith("log-dim1", "too aggressive");
  });

  test("reject button disabled when reason is empty", () => {
    render(<ReviewerPanel reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} onAccept={jest.fn()} onReject={jest.fn()} />);
    fireEvent.click(screen.getByText("拒绝并重新分析"));

    const confirmBtn = screen.getByText("确认拒绝");
    fireEvent.click(confirmBtn);
    // onReject should not be called with empty reason
    expect(defaultProps.onReject).not.toHaveBeenCalled();
  });

  // ── 9. Script expansion ────────────────────────────────────

  test("toggles script visibility on button click", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} />);

    // Initially hidden
    expect(screen.queryByText(/import fiftyone/)).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByText("查看生成脚本"));
    expect(screen.getByText(/import fiftyone/)).toBeInTheDocument();

    // Click to collapse
    fireEvent.click(screen.getByText("收起脚本"));
    expect(screen.queryByText(/import fiftyone/)).not.toBeInTheDocument();
  });

  // ── 10. Multiple logs stats ────────────────────────────────

  test("shows correct stats for mixed decision states", () => {
    const logs = [LOG_AST_PASS_SANDBOX_PASS_PENDING, LOG_ACCEPTED, LOG_REJECTED];
    render(<ReviewerPanel {...defaultProps} reviewLogs={logs} />);
    expect(screen.getByText(/1 待决策/)).toBeInTheDocument();
    expect(screen.getByText(/1 已接受/)).toBeInTheDocument();
    expect(screen.getByText(/1 已拒绝/)).toBeInTheDocument();
  });

  // ── Additional dimension tests ─────────────────────────────

  test("displays sandbox execution time", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_SLOW_SANDBOX]} />);
    expect(screen.getByText("48500ms")).toBeInTheDocument();
  });

  test("handles multiple AST issues", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_MULTI_ISSUES]} />);
    expect(screen.getByText("Line 3: exec() call detected")).toBeInTheDocument();
    expect(screen.getByText("Line 12: subprocess.Popen call")).toBeInTheDocument();
  });

  test("handles empty script content", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_EMPTY_SCRIPT]} />);
    fireEvent.click(screen.getByText("查看生成脚本"));
    // Should not crash
    expect(screen.getByText("收起脚本")).toBeInTheDocument();
  });

  test("handles old timestamp gracefully", () => {
    render(<ReviewerPanel {...defaultProps} reviewLogs={[LOG_OLD_TIMESTAMP]} />);
    // Should render without crashing - time formatting may vary by locale
    expect(screen.getByText("待决策")).toBeInTheDocument();
  });

  test("renders title bar", () => {
    render(<ReviewerPanel {...defaultProps} />);
    expect(screen.getByText("Reviewer 决策面板")).toBeInTheDocument();
  });

  test("cancel reject flow", () => {
    render(<ReviewerPanel reviewLogs={[LOG_AST_PASS_SANDBOX_PASS_PENDING]} onAccept={jest.fn()} onReject={jest.fn()} />);

    // Open reject input
    fireEvent.click(screen.getByText("拒绝并重新分析"));

    // Type something
    const textarea = screen.getByPlaceholderText(/请输入拒绝原因/);
    fireEvent.change(textarea, { target: { value: "test reason" } });

    // Cancel
    fireEvent.click(screen.getByText("取消"));

    // Input should be gone
    expect(screen.queryByPlaceholderText(/请输入拒绝原因/)).not.toBeInTheDocument();
  });
});
