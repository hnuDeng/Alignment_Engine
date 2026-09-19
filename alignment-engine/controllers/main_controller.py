
"""
主控制器模块 V2
功能：集成所有模块，提供完整的规划系统
"""

import numpy as np
import json
from typing import Dict, List

from llm_understanding import LLMUnderstandingLayer
from constraint_generator import ConstraintGenerator, SimpleSceneGraph
from trajectory_optimizer import TrajectoryOptimizer
from safety_checker import SafetyChecker
from action_generator import ActionGenerator


class LLMGuidedPlanner:
    """
    LLM引导的规划系统
    
    完整流程：
    用户指令 -> LLM理解 -> 约束生成 -> 轨迹优化 -> 安全检查 -> 动作生成
    """
    
    def __init__(self, scene_graph=None, max_retries=3):
        """
        初始化规划系统
        
        Args:
            scene_graph: 场景图
            max_retries: 最大重试次数
        """
        self.scene = scene_graph or SimpleSceneGraph()
        self.max_retries = max_retries
        
        # 初始化各模块
        self.llm = LLMUnderstandingLayer()
        self.constraint_gen = ConstraintGenerator(self.scene)
        self.optimizer = TrajectoryOptimizer(horizon=30, state_dim=3)
        self.safety_checker = SafetyChecker(self.scene)
        self.action_gen = ActionGenerator(control_type="position")
    
    def plan(self, instruction, scene_description, current_state, goal_state, retry_count=0):
        """
        执行规划
        
        Args:
            instruction: 自然语言指令
            scene_description: 场景描述
            current_state: 当前状态
            goal_state: 目标状态
            retry_count: 当前重试次数
            
        Returns:
            规划结果
        """
        print(f"[LLM理解] 指令: {instruction}")
        
        # Step 1: LLM理解
        intent = self.llm.understand(instruction, scene_description)
        print(f"[LLM理解] 意图: {json.dumps(intent, ensure_ascii=False)}")
        
        # Step 2: 生成约束
        constraints = self.constraint_gen.generate(intent, current_state, goal_state)
        print(f"[约束生成] 生成 {len(constraints)} 个约束")
        
        # Step 3: 优化轨迹
        trajectory = self.optimizer.solve(current_state, goal_state, constraints)
        print(f"[轨迹优化] 轨迹形状: {trajectory.shape}")
        
        # Step 4: 安全检查
        safety_result = self.safety_checker.check(trajectory)
        print(f"[安全检查] {'通过' if safety_result['safe'] else '失败'}")
        
        if not safety_result["safe"]:
            print(f"[安全检查] 违规: {safety_result['violations']}")
            
            # 检查是否达到最大重试次数
            if retry_count >= self.max_retries:
                print(f"[重新规划] 达到最大重试次数 {self.max_retries}，返回失败")
                return {
                    "success": False,
                    "error": "Max retries exceeded",
                    "violations": safety_result["violations"]
                }
            
            # 重新规划
            return self._replan_with_safety(
                instruction, scene_description,
                current_state, goal_state,
                safety_result["violations"],
                retry_count
            )
        
        # Step 5: 生成动作
        actions = self.action_gen.generate(trajectory)
        print(f"[动作生成] 生成 {len(actions)} 个动作")
        
        return {
            "success": True,
            "intent": intent,
            "trajectory": trajectory.tolist(),
            "actions": actions,
            "safety": safety_result
        }
    
    def _replan_with_safety(self, instruction, scene_description,
                            current_state, goal_state, violations, retry_count):
        """重新规划（增加安全边距）"""
        print(f"[重新规划] 第 {retry_count + 1} 次重试，增加安全边距...")
        
        # 增加安全边距
        self.constraint_gen.safety_margin *= 1.5
        
        # 重新规划
        result = self.plan(
            instruction, scene_description, 
            current_state, goal_state, 
            retry_count + 1
        )
        
        # 恢复安全边距
        self.constraint_gen.safety_margin /= 1.5
        
        return result


# 测试代码
if __name__ == "__main__":
    print("=== 测试主控制器 V2 ===\n")
    
    # 创建场景
    scene = SimpleSceneGraph()
    scene.add_object("cup", np.array([0.5, 0.3, 0.2]))
    scene.add_object("table", np.array([0.5, 0.5, 0.0]))
    scene.add_obstacle("wall", np.array([0.6, 0.3, 0.2]), 0.05)
    
    # 创建规划器
    planner = LLMGuidedPlanner(scene, max_retries=3)
    
    # 测试用例
    test_cases = [
        {
            "name": "放置杯子",
            "instruction": "把杯子放到桌子上",
            "scene": "桌面上有一个红色杯子",
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.5, 0.2])
        },
        {
            "name": "抓取杯子",
            "instruction": "pick up the cup",
            "scene": "A red cup is on the table",
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.3, 0.2])
        }
    ]
    
    results = []
    for test in test_cases:
        print(f"\n--- {test['name']} ---")
        result = planner.plan(
            test["instruction"],
            test["scene"],
            test["current"],
            test["goal"]
        )
        results.append(result)
        print(f"结果: {'成功' if result['success'] else '失败'}")
    
    # 汇总
    print("\n=== 测试汇总 ===")
    success_count = sum(1 for r in results if r["success"])
    print(f"成功率: {success_count}/{len(results)} ({success_count/len(results)*100:.0f}%)")
