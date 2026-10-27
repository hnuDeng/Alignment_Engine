import { datasetReducer, INITIAL_DATASET_STATE } from "../../src/store/datasetSlice";
import { readFileSync } from "fs";
import path from "path";

test("empty and reset dataset statistics leave isolation scores unavailable", () => {
  for (const state of [
    INITIAL_DATASET_STATE,
    datasetReducer(INITIAL_DATASET_STATE, { type: "DATASET_CLEAR_ALL" }),
    datasetReducer(INITIAL_DATASET_STATE, { type: "DATASET_FULL_RESET" }),
  ]) {
    expect(state.stats.meanIsolationScore).toBeNull();
    expect(state.stats.maxIsolationScore).toBeNull();
  }
});

test("selected fallback candidates do not become confirmed drift in normalized statistics", () => {
  const wire = JSON.parse(readFileSync(path.resolve(__dirname, "../hooks/websocketWire.json"), "utf8")) as string[];
  const report = JSON.parse(wire[1]).payload;
  const state = datasetReducer(INITIAL_DATASET_STATE, { type: "DATASET_MERGE_REPORT", report });
  expect(state.entities.samples["far"].isDrift).toBeNull();
  expect(state.entities.samples["near-a"].isDrift).toBeNull();
  expect(state.stats.driftCount).toBeNull();
});
