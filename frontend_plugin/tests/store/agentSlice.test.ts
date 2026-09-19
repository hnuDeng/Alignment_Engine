import { agentReducer, initialState } from "../../src/store/agentSlice";
import type { ActionType, AgentState } from "../../src/store/agentSlice";

describe("agentSlice Reducer", () => {
    it("should return the initial state", () => {
        expect(agentReducer(undefined, {} as ActionType)).toEqual(initialState);
    });

    it("should handle INIT_PIPELINE", () => {
        const state = agentReducer(initialState, { type: 'INIT_PIPELINE', payload: { taskId: "123" } });
        expect(state.status).toBe('idle');
        expect(state.currentTaskId).toBe("123");
        expect(state.logs.length).toBe(1);
    });

    it("should throw StateTransitionException if INIT_PIPELINE called when not idle or error", () => {
        const extractingState: AgentState = { ...initialState, status: 'extracting' };
        expect(() => {
            agentReducer(extractingState, { type: 'INIT_PIPELINE', payload: { taskId: "123" } });
        }).toThrow(/StateTransitionException/);
    });

    it("should handle EXTRACT_START", () => {
        const state = agentReducer(initialState, { type: 'EXTRACT_START' });
        expect(state.status).toBe('extracting');
        expect(state.logs[state.logs.length - 1]).toBe('Extraction started');
    });

    it("should handle ANALYZE_START", () => {
        const extractingState: AgentState = { ...initialState, status: 'extracting' };
        const state = agentReducer(extractingState, { type: 'ANALYZE_START' });
        expect(state.status).toBe('analyzing');
    });

    it("should handle ANALYZE_COMPLETE", () => {
        const analyzingState: AgentState = { ...initialState, status: 'analyzing' };
        const state = agentReducer(analyzingState, { type: 'ANALYZE_COMPLETE', payload: { driftScore: 0.5, anomalousIds: ['a1'] } });
        expect(state.status).toBe('idle');
        expect(state.driftScore).toBe(0.5);
        expect(state.anomalousIds).toEqual(['a1']);
    });

    it("should handle REVIEW_START", () => {
        const state = agentReducer(initialState, { type: 'REVIEW_START' });
        expect(state.status).toBe('reviewing');
    });

    it("should handle REVIEW_COMPLETE", () => {
        const state = agentReducer(initialState, { type: 'REVIEW_COMPLETE', payload: { script: "print(1)", executed: true } });
        expect(state.status).toBe('idle');
        expect(state.reviewDecision?.script).toBe("print(1)");
        expect(state.reviewDecision?.executed).toBe(true);
    });

    it("should handle ERROR", () => {
        const state = agentReducer(initialState, { type: 'ERROR', payload: { message: "Something went wrong" } });
        expect(state.status).toBe('error');
        expect(state.logs[state.logs.length - 1]).toContain("Something went wrong");
    });

    it("should handle RESET", () => {
        const errorState: AgentState = { ...initialState, status: 'error' };
        const state = agentReducer(errorState, { type: 'RESET' });
        expect(state).toEqual(initialState);
    });

    describe('Selection & Filter Actions', () => {
        it('should handle DATASET_FILTER_APPLY and CLEAR', () => {
            const stateWithFilter = agentReducer(initialState, { type: 'DATASET_FILTER_APPLY', payload: { filterString: 'test' } });
            expect(stateWithFilter.filterString).toBe('test');
            
            const stateCleared = agentReducer(stateWithFilter, { type: 'DATASET_FILTER_CLEAR' });
            expect(stateCleared.filterString).toBeNull();
        });

        it('should handle SELECTION_ADD, REMOVE and CLEAR', () => {
            let state = agentReducer(initialState, { type: 'SELECTION_ADD', payload: { sampleId: 's1' } });
            expect(state.selection).toEqual(['s1']);

            // Duplicate add shouldn't change array reference or content
            const stateDup = agentReducer(state, { type: 'SELECTION_ADD', payload: { sampleId: 's1' } });
            expect(stateDup).toBe(state);

            state = agentReducer(state, { type: 'SELECTION_ADD', payload: { sampleId: 's2' } });
            expect(state.selection).toEqual(['s1', 's2']);

            state = agentReducer(state, { type: 'SELECTION_REMOVE', payload: { sampleId: 's1' } });
            expect(state.selection).toEqual(['s2']);

            state = agentReducer(state, { type: 'SELECTION_CLEAR' });
            expect(state.selection).toEqual([]);
        });
    });
});
