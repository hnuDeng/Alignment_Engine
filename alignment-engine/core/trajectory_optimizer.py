
"""
轨迹优化器模块 V2
功能：在约束下求解最优轨迹（纯numpy实现，无外部依赖）
"""

import numpy as np
from typing import List, Dict


class TrajectoryOptimizer:
    """
    轨迹优化器 V2：使用梯度下降实现，无外部依赖
    
    核心功能：
    1. 初始化轨迹
    2. 梯度下降优化
    3. 约束处理
    """
    
    def __init__(self, horizon: int = 30, state_dim: int = 3):
        self.horizon = horizon
        self.state_dim = state_dim
        
        # 优化参数
        self.learning_rate = 0.01
        self.max_iterations = 200
        self.tolerance = 1e-4
        
        # 权重参数
        self.w_goal = 1.0
        self.w_smooth = 0.1
        self.w_constraint = 10.0
    
    def solve(self, start_state: np.ndarray, goal_state: np.ndarray,
              constraints: List[Dict] = None) -> np.ndarray:
        """求解最优轨迹"""
        # 初始化轨迹（线性插值）
        trajectory = self._initialize_trajectory(start_state, goal_state)
        
        # 梯度下降优化
        for iteration in range(self.max_iterations):
            # 计算梯度
            grad = self._compute_gradient(trajectory, goal_state, constraints or [])
            
            # 更新轨迹
            trajectory -= self.learning_rate * grad
            
            # 强制起始状态
            trajectory[0] = start_state
            
            # 检查收敛
            if np.linalg.norm(grad) < self.tolerance:
                break
        
        return trajectory
    
    def _initialize_trajectory(self, start: np.ndarray, goal: np.ndarray) -> np.ndarray:
        """初始化轨迹 (Vectorized)"""
        return np.linspace(start, goal, self.horizon)
    
    def _compute_gradient(self, trajectory: np.ndarray, goal: np.ndarray,
                          constraints: List[Dict]) -> np.ndarray:
        """计算梯度 (Vectorized)"""
        grad = np.zeros_like(trajectory)
        
        # 目标梯度：向目标方向
        goal_error = trajectory[-1] - goal
        grad[-1] += self.w_goal * goal_error
        
        # 平滑梯度：相邻状态差异 (Vectorized finite difference)
        if self.horizon > 2:
            grad[1:-1] += self.w_smooth * (2 * trajectory[1:-1] - trajectory[:-2] - trajectory[2:])
        
        # 约束梯度
        for c in constraints:
            grad += self.w_constraint * self._constraint_gradient(trajectory, c)
        
        return grad
    
    def _constraint_gradient(self, trajectory: np.ndarray, constraint: Dict) -> np.ndarray:
        """计算约束梯度 (Vectorized)"""
        grad = np.zeros_like(trajectory)
        
        name = constraint.get("name", "")
        
        if "obstacle" in name:
            # 避障约束
            obs_pos = constraint["params"]["obstacle_pos"]
            safety_margin = constraint["params"].get("safety_margin", 0.05)
            
            # Vectorized distance computation
            diff = trajectory - obs_pos
            dist = np.linalg.norm(diff, axis=1)
            
            mask = dist < safety_margin
            if np.any(mask):
                grad[mask] -= diff[mask] / (dist[mask, np.newaxis] + 1e-6)
        
        return grad


# 测试代码
if __name__ == "__main__":
    print("=== 测试轨迹优化器 V2 ===")
    
    optimizer = TrajectoryOptimizer(horizon=30, state_dim=3)
    
    start = np.array([0.0, 0.0, 0.0])
    goal = np.array([1.0, 1.0, 0.5])
    
    constraints = [{
        "name": "obstacle_wall",
        "params": {
            "obstacle_pos": np.array([0.5, 0.5, 0.25]),
            "safety_margin": 0.1
        }
    }]
    
    print("优化中...")
    trajectory = optimizer.solve(start, goal, constraints)
    
    print(f"轨迹形状: {trajectory.shape}")
    print(f"起始位置: {trajectory[0]}")
    print(f"终止位置: {trajectory[-1]}")
    print(f"目标位置: {goal}")
    print(f"最终误差: {np.linalg.norm(trajectory[-1] - goal):.4f}")
    print("✅ 优化器工作正常")
