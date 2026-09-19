
"""
系统集成测试
功能：测试LLM理解层、约束生成器、轨迹优化器的集成
"""

import numpy as np
import json
import sys
import os

# 添加当前目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from llm_understanding import LLMUnderstandingLayer
from constraint_generator import ConstraintGenerator, SimpleSceneGraph
from trajectory_optimizer import TrajectoryOptimizer


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
            "goal": np.array([0.5, 0.5, 0.2])
        },
        {
            "name": "抓取杯子",
            "instruction": "pick up the cup",
            "scene_desc": "A red cup is on the table",
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.3, 0.2])
        }
    ]
    
    results = []
    
    for i, test in enumerate(test_cases):
        print(f"--- 测试 {i+1}: {test['name']} ---")
        
        # Step 1: LLM理解
        intent = llm_layer.understand(test["instruction"], test["scene_desc"])
        print(f"意图: {json.dumps(intent, ensure_ascii=False)}")
        
        # Step 2: 生成约束
        constraints = constraint_gen.generate(intent, test["current"], test["goal"])
        print(f"约束数量: {len(constraints)}")
        
        # Step 3: 优化轨迹
        trajectory = optimizer.solve(test["current"], test["goal"], constraints)
        
        # 计算指标
        final_error = np.linalg.norm(trajectory[-1] - test["goal"])
        smoothness = np.mean(np.diff(trajectory, axis=0)**2)
        
        print(f"轨迹形状: {trajectory.shape}")
        print(f"最终误差: {final_error:.4f}")
        print(f"平滑度: {smoothness:.4f}")
        
        results.append({
            "name": test["name"],
            "success": final_error < 0.1,
            "final_error": final_error,
            "smoothness": smoothness
        })
        
        print()
    
    # 4. 汇总结果
    print("=== 测试结果汇总 ===")
    for r in results:
        status = "[PASS] PASS" if r["success"] else "[FAIL] FAIL"
        print(f"{r['name']}: {status} (误差: {r['final_error']:.4f})")
    
    success_rate = sum(1 for r in results if r["success"]) / len(results)
    print(f"\n总体成功率: {success_rate*100:.1f}%")
    
    return results


if __name__ == "__main__":
    test_end_to_end()

