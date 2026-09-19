
"""
动作生成器模块
功能：将轨迹转换为可执行的动作序列
"""

import numpy as np
from typing import List, Dict


class ActionGenerator:
    """
    动作生成器：将轨迹转换为可执行的动作序列
    
    支持的动作类型：
    1. 位置控制
    2. 速度控制
    3. 力矩控制
    """
    
    def __init__(self, control_type: str = "position"):
        """
        初始化动作生成器
        
        Args:
            control_type: 控制类型 (position/velocity/torque)
        """
        self.control_type = control_type
        self.dt = 0.1  # 时间步长
    
    def generate(self, trajectory: np.ndarray) -> List[Dict]:
        """
        生成动作序列
        
        Args:
            trajectory: 轨迹 [horizon, state_dim]
            
        Returns:
            动作序列
        """
        actions = []
        
        for t in range(len(trajectory) - 1):
            current = trajectory[t]
            target = trajectory[t + 1]
            
            if self.control_type == "position":
                action = self._position_control(current, target)
            elif self.control_type == "velocity":
                action = self._velocity_control(current, target)
            else:
                action = self._position_control(current, target)
            
            action["timestamp"] = t * self.dt
            actions.append(action)
        
        return actions
    
    def _position_control(self, current: np.ndarray, target: np.ndarray) -> Dict:
        """位置控制"""
        return {
            "type": "position",
            "target_position": target.tolist(),
            "current_position": current.tolist(),
            "displacement": (target - current).tolist()
        }
    
    def _velocity_control(self, current: np.ndarray, target: np.ndarray) -> Dict:
        """速度控制"""
        velocity = (target - current) / self.dt
        return {
            "type": "velocity",
            "velocity": velocity.tolist(),
            "duration": self.dt
        }


# 测试代码
if __name__ == "__main__":
    print("=== 测试动作生成器 ===")
    
    generator = ActionGenerator(control_type="position")
    
    trajectory = np.array([
        [0.0, 0.0, 0.0],
        [0.2, 0.2, 0.1],
        [0.5, 0.5, 0.25],
        [0.8, 0.8, 0.4],
        [1.0, 1.0, 0.5]
    ])
    
    actions = generator.generate(trajectory)
    
    print(f"生成 {len(actions)} 个动作")
    for i, action in enumerate(actions):
        print(f"动作 {i+1}: {action['type']} -> {action['target_position']}")
