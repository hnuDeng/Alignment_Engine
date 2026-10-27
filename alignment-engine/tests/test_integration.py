
"""
系统集成测试
功能：测试LLM理解层、约束生成器、轨迹优化器的集成
"""

import numpy as np
import json
import sys
import os

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.llm_understanding import LLMUnderstandingLayer
from agents.constraint_generator import ConstraintGenerator, SimpleSceneGraph
from core.trajectory_optimizer import TrajectoryOptimizer


def test_end_to_end():
    """端到端测试"""
    print("=== 端到端集成测试 ===\n")
    
    # 1. 初始化场景
    scene = SimpleSceneGraph()
    scene.add_object("cup", np.array([0.5, 0.3, 0.2]))
    scene.add_object("table", np.array([0.5, 0.5, 0.0]))
    scene.add_obstacle("wall", np.array([0.6, 0.3, 0.2]), 0.05)
    
    # 2. 初始化模块
    llm_layer = LLMUnderstandingLayer()
    constraint_gen = ConstraintGenerator(scene)
    optimizer = TrajectoryOptimizer(horizon=30, state_dim=3)
    
    # 3. 测试用例
    test_cases = [
        {
            "name": "放置杯子",
            "instruction": "把杯子放到桌子上",
            "scene_desc": "桌面上有一个红色杯子，机器人手臂在杯子上方",
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.5, 0.2]),
            "expected_object": "杯子",
            "expected_actions": (None, "place"),
        },
        {
            "name": "抓取杯子",
            "instruction": "pick up the cup",
            "scene_desc": "A red cup is on the table",
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.3, 0.2]),
            "expected_object": "cup",
            "expected_actions": ("pick",),
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases):
        print(f"--- 测试 {i+1}: {test['name']} ---")
        
        # Step 1: LLM理解
        intent = llm_layer.understand(test["instruction"], test["scene_desc"])
        print(f"意图: {json.dumps(intent, ensure_ascii=False)}")
        assert intent["object"] == test["expected_object"], test["name"]
        assert intent["action"] in test["expected_actions"], test["name"]
        
        # Step 2: 生成约束
        constraints = constraint_gen.generate(intent, test["current"], test["goal"])
        print(f"约束数量: {len(constraints)}")
        names = {constraint["name"] for constraint in constraints}
        assert "velocity_limit" in names, test["name"]
        if intent["action"] == "pick":
            assert "object_approach" in names, test["name"]
            approach = next(c for c in constraints if c["name"] == "object_approach")
            np.testing.assert_allclose(approach["params"]["object_pos"], [0.5, 0.3, 0.2])
        elif intent["action"] == "place":
            assert "goal_position" in names, test["name"]
        
        # Step 3: 优化轨迹
        trajectory = optimizer.solve(test["current"], test["goal"], constraints)
        assert trajectory.shape == (30, 3), test["name"]
        assert np.isfinite(trajectory).all(), test["name"]
        np.testing.assert_allclose(trajectory[0], test["current"])
        
        # 计算指标
        final_error = np.linalg.norm(trajectory[-1] - test["goal"])
        smoothness = np.mean(np.diff(trajectory, axis=0)**2)
        assert final_error < 0.1, f"{test['name']}: final error {final_error}"
        assert np.isfinite(smoothness), test["name"]
        
        print(f"轨迹形状: {trajectory.shape}")
        print(f"最终误差: {final_error:.4f}")
        print(f"平滑度: {smoothness:.4f}")
        
        results.append({
            "name": test["name"],
            "action": intent["action"],
            "final_error": final_error,
            "smoothness": smoothness
        })
        
        print()
    
    # 4. 汇总结果
    print("=== 测试结果汇总 ===")
    for r in results:
        status = "动作未识别" if r["action"] is None else f"动作: {r['action']}"
        print(f"{r['name']}: 给定目标轨迹误差 {r['final_error']:.4f}; {status}")
    
    print("\n轨迹目标使用预先给定的坐标；该结果不证明任务语义理解或约束全部满足。")


if __name__ == "__main__":
    test_end_to_end()

