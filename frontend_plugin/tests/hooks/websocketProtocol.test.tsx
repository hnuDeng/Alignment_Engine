import { execFileSync } from "child_process";
import path from "path";
import { readFileSync } from "fs";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { useDriftStream } from "../../src/hooks/useDriftStream";
import { DriftAlert } from "../../src/components/DriftAlert";
import { AgentCopilotPanel } from "../../src/components/AgentCopilotPanel";

class LocalSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instance: LocalSocket;
  readyState = LocalSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];
  constructor(_url: string) { LocalSocket.instance = this; }
  send(value: string) { this.sent.push(value); }
  close() { this.readyState = LocalSocket.CLOSED; this.onclose?.(); }
  open() { this.readyState = LocalSocket.OPEN; this.onopen?.(); }
  receive(data: string) { this.onmessage?.({ data }); }
}

function Panel() {
  const { state } = useDriftStream({ wsEndpoint: "ws://local" });
  return <><div data-testid="status">{state.connectionStatus} {String(state.isStreaming)} {String(state.lastHeartbeat !== null)}</div>
    {state.reports.map(report => <DriftAlert key={report.reportId} report={report} expanded onHighlight={() => {}} onToggleExpand={() => {}} />)}
  </>;
}

function pythonWire(): string[] {
  const script = path.resolve(__dirname, "../../../alignment-engine/tests/websocket_fixture.py");
  return JSON.parse(process.env.ALIGNMENT_LIVE_PYTHON === "1"
    ? execFileSync("python", [script], { encoding: "utf8" })
    : readFileSync(path.join(__dirname, "websocketWire.json"), "utf8")) as string[];
}

beforeEach(() => {
  jest.useFakeTimers();
  global.WebSocket = LocalSocket as unknown as typeof WebSocket;
});
afterEach(() => jest.useRealTimers());

test("Python messages reach the panel with actual distances and unavailable values", () => {
  const wire = pythonWire();
  render(<Panel />);
  act(() => LocalSocket.instance.open());
  act(() => LocalSocket.instance.receive(wire[0]));
  expect(screen.getByTestId("status").textContent).toContain("connected true");
  act(() => LocalSocket.instance.receive(wire[1]));
  expect(screen.getByText("far")).toBeTruthy();
  expect(screen.getByText(/距离=33\.94/)).toBeTruthy();
  expect(screen.getAllByText(/不可用/).length).toBeGreaterThan(0);
  expect(screen.getByText(/总量: 3/)).toBeTruthy();
  act(() => { LocalSocket.instance.receive(wire[2]); LocalSocket.instance.receive(wire[3]); });
  expect(screen.getByTestId("status").textContent).toContain("connected false true");
  act(() => LocalSocket.instance.close());
  expect(screen.getByTestId("status").textContent).toContain("disconnected false");
});

test("invalid messages and server errors do not crash the panel", () => {
  render(<Panel />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive("not json"); LocalSocket.instance.receive('{"type":"drift_report","seq":1,"payload":{}}'); LocalSocket.instance.receive('{"type":"drift_event","seq":2,"payload":[null]}'); LocalSocket.instance.receive('{"type":"error","seq":3,"payload":{"message":"failed"}}'); });
  expect(screen.getByTestId("status").textContent).toContain("connected");
});

test("fallback samples are presented as candidates, including an empty selection", () => {
  const wire = pythonWire();
  const bridge = { setSelectedSamples: () => {}, getDatasetName: () => "fixture", flashSamples: () => {} };
  render(<AgentCopilotPanel wsEndpoint="ws://local" datasetBridge={bridge} />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive(wire[0]); LocalSocket.instance.receive(wire[1]); });
  expect(screen.getAllByText(/2 个待审样本/).length).toBeGreaterThan(0);
  expect(screen.queryByText(/异常样本/)).toBeNull();
  expect(screen.getByText(/阈值以下/)).toBeTruthy();
  expect(screen.getByTitle("高亮 2 个待审样本")).toBeTruthy();
  const empty = JSON.parse(wire[1]);
  empty.seq = 3; empty.payload.reportId = "empty"; empty.payload.samples = []; empty.payload.stats.driftCount = 0;
  act(() => LocalSocket.instance.receive(JSON.stringify(empty)));
  expect(screen.getByText("0 个待审样本")).toBeTruthy();
});

test("server error remains visible while the socket stays connected and receives a heartbeat", () => {
  const bridge = { setSelectedSamples: () => {}, getDatasetName: () => "fixture", flashSamples: () => {} };
  render(<AgentCopilotPanel wsEndpoint="ws://local" datasetBridge={bridge} />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive('{"type":"error","seq":1,"payload":{"message":"Pipeline failed"}}'); });
  expect(screen.getByRole("alert").textContent).toContain("Pipeline failed");
  expect(screen.getByText("已连接")).toBeTruthy();
  act(() => LocalSocket.instance.receive('{"type":"heartbeat","seq":2,"payload":null}'));
  expect(screen.getByText("已连接")).toBeTruthy();
  expect(screen.getByRole("alert").textContent).toContain("Pipeline failed");
});

test("the first highlight click selects the displayed candidates and the second clears them", () => {
  const wire = JSON.parse(readFileSync(path.join(__dirname, "websocketWire.json"), "utf8")) as string[];
  const setSelectedSamples = jest.fn();
  const bridge = { setSelectedSamples, getDatasetName: () => "fixture", flashSamples: () => {} };
  render(<AgentCopilotPanel wsEndpoint="ws://local" datasetBridge={bridge} />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive(wire[0]); LocalSocket.instance.receive(wire[1]); });
  fireEvent.click(screen.getByTitle("高亮 2 个待审样本"));
  expect(setSelectedSamples).toHaveBeenLastCalledWith(["far", "near-a"]);
  fireEvent.click(screen.getByTitle("取消高亮"));
  expect(setSelectedSamples).toHaveBeenLastCalledWith([]);
});

test("legacy events show unavailable analysis mode and identify their timestamp as receipt time", () => {
  const wire = JSON.parse(readFileSync(path.join(__dirname, "websocketWire.json"), "utf8")) as string[];
  const report = JSON.parse(wire[1]);
  const bridge = { setSelectedSamples: () => {}, getDatasetName: () => "fixture", flashSamples: () => {} };
  render(<AgentCopilotPanel wsEndpoint="ws://local" datasetBridge={bridge} />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive(JSON.stringify({ type: "drift_event", seq: 1, payload: report.payload.samples })); });
  expect(screen.getByText(/接收时间/)).toBeTruthy();
  expect(screen.getByText("模式不可用")).toBeTruthy();
  expect(screen.queryByText("cpp_bfs")).toBeNull();
});

test("heartbeats are sent and an unanswered heartbeat disconnects", () => {
  render(<Panel />);
  act(() => LocalSocket.instance.open());
  act(() => jest.advanceTimersByTime(7500));
  expect(JSON.parse(LocalSocket.instance.sent[0])).toEqual({ type: "heartbeat" });
  act(() => jest.advanceTimersByTime(7500));
  expect(screen.getByTestId("status").textContent).toContain("disconnected");
});

test("a malformed report source is ignored before rendering", () => {
  const wire = JSON.parse(readFileSync(path.join(__dirname, "websocketWire.json"), "utf8")) as string[];
  const bad = JSON.parse(wire[1]);
  bad.payload.source = {};
  render(<Panel />);
  act(() => { LocalSocket.instance.open(); LocalSocket.instance.receive(JSON.stringify(bad)); });
  expect(screen.queryByText("far")).toBeNull();
});
