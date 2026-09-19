
"""
安全检查器模块
功能：验证轨迹的安全性
"""

import numpy as np
from typing import List, Dict


class SafetyChecker:
    """
    安全检查器：验证轨迹的安全性
    
    检查项目：
    1. 碰撞检测
    2. 运动学可行性
    3. 动力学稳定性
    4. 速度限制
    """
    
    def __init__(self, scene_graph=None):
        self.scene = scene_graph
        self.max_velocity = 1.0
        self.max_acceleration = 2.0
        self.min_clearance = 0.05  # 最小安全距离
    
    def check(self, trajectory: np.ndarray) -> Dict:
        """
        检查轨迹安全性
        
        Args:
            trajectory: 轨迹 [horizon, state_dim]
            
        Returns:
            安全检查结果
        """
        results = {
            "safe": True,
            "collision_free": True,
            "velocity_ok": True,
            "acceleration_ok": True,
            "violations": []
        }
        
        # 检查每个时间步
        for t in range(len(trajectory)):
            state = trajectory[t]
            
            # 碰撞检测
            if self.scene and self._check_collision(state, t):
                results["collision_free"] = False
                results["violations"].append(f"Collision at step {t}")
            
            # 速度检查
            if t > 0:
                velocity = trajectory[t] - trajectory[t-1]
                speed = np.linalg.norm(velocity)
                if speed > self.max_velocity:
                    results["velocity_ok"] = False
                    results["violations"].append(f"Velocity exceeded at step {t}: {speed:.2f}")
            
            # 加速度检查
            if t > 1:
                accel = trajectory[t] - 2*trajectory[t-1] + trajectory[t-2]
                accel_mag = np.linalg.norm(accel)
                if accel_mag > self.max_acceleration:
                    results["acceleration_ok"] = False
                    results["violations"].append(f"Acceleration exceeded at step {t}: {accel_mag:.2f}")
        
        # 综合判断
        results["safe"] = (
            results["collision_free"] and
            results["velocity_ok"] and
            results["acceleration_ok"]
        )
        
        return results
    
    def _check_collision(self, state: np.ndarray, step: int) -> bool:
        """检查碰撞"""
        if self.scene is None:
            return False
        
        obstacles = self.scene.get_obstacles()
        for obs in obstacles:
            dist = np.linalg.norm(state - obs["position"])
            if dist < obs.get("radius", 0.1) + self.min_clearance:
                return True
        
        return False


# 测试代码
if __name__ == "__main__":
    print("=== 测试安全检查器 ===")
    
    from constraint_generator import SimpleSceneGraph
    
    # 创建场景
    scene = SimpleSceneGraph()
    scene.add_obstacle("wall", np.array([0.5, 0.5, 0.25]), 0.1)
    
    checker = SafetyChecker(scene)
    
    # 测试安全轨迹
    safe_traj = np.array([
        [0.0, 0.0, 0.0],
        [0.2, 0.2, 0.1],
        [0.4, 0.2, 0.2],
        [0.8, 0.8, 0.4],
        [1.0, 1.0, 0.5]
    ])
    
    result = checker.check(safe_traj)
    print(f"安全轨迹检查: {'PASS' if result['safe'] else 'FAIL'}")
    print(f"违规: {result['violations']}")
    
    # 测试不安全轨迹（穿过障碍物）
    unsafe_traj = np.array([
        [0.0, 0.0, 0.0],
        [0.5, 0.5, 0.25],  # 直接穿过障碍物
        [1.0, 1.0, 0.5]
    ])
    
    result = checker.check(unsafe_traj)
    print(f"\n不安全轨迹检查: {'PASS' if result['safe'] else 'FAIL'}")
    print(f"违规: {result['violations']}")
