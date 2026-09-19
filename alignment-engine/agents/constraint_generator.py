
"""
约束生成器模块
功能：将结构化意图转换为数学约束
"""

import numpy as np
from typing import Dict, List, Tuple


class ConstraintGenerator:
    """
    约束生成器：将结构化意图转换为优化问题的约束条件
    
    核心功能：
    1. 解析结构化意图
    2. 生成目标约束
    3. 生成避障约束
    4. 生成物理约束
    """
    
    def __init__(self, scene_graph=None):
        """
        初始化约束生成器
        
        Args:
            scene_graph: 场景图，包含物体位置和属性
        """
        self.scene = scene_graph
        self.safety_margin = 0.05  # 默认安全边距
        self.max_velocity = 1.0    # 默认最大速度
        self.max_acceleration = 2.0  # 默认最大加速度
    
    def generate(self, intent: Dict, current_state: np.ndarray, 
                 goal_state: np.ndarray) -> List[Dict]:
        """
        生成约束条件
        
        Args:
            intent: 结构化意图
            current_state: 当前状态 [x, y, z, ...]
            goal_state: 目标状态 [x, y, z, ...]
            
        Returns:
            约束条件列表
        """
        constraints = []
        
        # 1. 目标约束
        constraints.extend(self._generate_goal_constraints(intent, goal_state))
        
        # 2. 避障约束
        if "avoid_collision" in intent.get("constraints", []):
            constraints.extend(self._generate_obstacle_constraints())
        
        # 3. 姿态约束
        if "keep_upright" in intent.get("constraints", []):
            constraints.extend(self._generate_orientation_constraints())
        
        # 4. 速度约束
        constraints.extend(self._generate_velocity_constraints())
        
        # 5. 动作特定约束
        constraints.extend(self._generate_action_constraints(intent))
        
        return constraints
    
    def _generate_goal_constraints(self, intent: Dict, 
                                   goal_state: np.ndarray) -> List[Dict]:
        """生成目标约束"""
        constraints = []
        
        action = intent.get("action")
        
        if action == "place":
            # 放置动作：最终位置必须接近目标
            constraints.append({
                "type": "equality",
                "name": "goal_position",
                "expr": "position[-1] ≈ goal_state",
                "params": {
                    "goal": goal_state,
                    "tolerance": 0.02
                }
            })
        
        elif action == "pick":
            # 抓取动作：最终位置必须接近物体
            constraints.append({
                "type": "equality",
                "name": "object_approach",
                "expr": "position[-1] ≈ object_position",
                "params": {
                    "object_pos": self._get_object_position(intent.get("object")),
                    "tolerance": 0.01
                }
            })
        
        elif action == "move":
            # 移动动作：最终位置必须接近目标
            constraints.append({
                "type": "equality",
                "name": "goal_position",
                "expr": "position[-1] ≈ goal_state",
                "params": {
                    "goal": goal_state,
                    "tolerance": 0.05
                }
            })
        
        return constraints
    
    def _generate_obstacle_constraints(self) -> List[Dict]:
        """生成避障约束"""
        constraints = []
        
        if self.scene is None:
            return constraints
        
        obstacles = self.scene.get_obstacles()
        
        for obs in obstacles:
            constraints.append({
                "type": "inequality",
                "name": f"obstacle_{obs['name']}",
                "expr": "distance(trajectory, obstacle) > safety_margin",
                "params": {
                    "obstacle_pos": obs["position"],
                    "obstacle_radius": obs.get("radius", 0.1),
                    "safety_margin": self.safety_margin
                }
            })
        
        return constraints
    
    def _generate_orientation_constraints(self) -> List[Dict]:
        """生成姿态约束"""
        constraints.append({
            "type": "inequality",
            "name": "keep_upright",
            "expr": "abs(orientation) < max_tilt",
            "params": {
                "max_tilt": 0.1  # 弧度
            }
        })
        return constraints
    
    def _generate_velocity_constraints(self) -> List[Dict]:
        """生成速度约束"""
        constraints = []
        constraints.append({
            "type": "inequality",
            "name": "velocity_limit",
            "expr": "norm(velocity) < max_velocity",
            "params": {
                "max_velocity": self.max_velocity
            }
        })
        return constraints
    
    def _generate_action_constraints(self, intent: Dict) -> List[Dict]:
        """生成动作特定约束"""
        constraints = []
        
        action = intent.get("action")
        
        if action == "push":
            # 推动作：力的方向约束
            constraints.append({
                "type": "inequality",
                "name": "push_direction",
                "expr": "force_direction ≈ intended_direction",
                "params": {
                    "direction": self._infer_push_direction(intent)
                }
            })
        
        elif action == "pull":
            # 拉动作：力的方向约束
            constraints.append({
                "type": "inequality",
                "name": "pull_direction",
                "expr": "force_direction ≈ intended_direction",
                "params": {
                    "direction": self._infer_pull_direction(intent)
                }
            })
        
        return constraints
    
    def _get_object_position(self, object_name: str) -> np.ndarray:
        """获取物体位置"""
        if self.scene is None:
            return np.zeros(3)
        return self.scene.get_position(object_name)
    
    def _infer_push_direction(self, intent: Dict) -> np.ndarray:
        """推断推力方向"""
        # 简化：返回默认方向
        return np.array([1.0, 0.0, 0.0])
    
    def _infer_pull_direction(self, intent: Dict) -> np.ndarray:
        """推断拉力方向"""
        # 简化：返回默认方向
        return np.array([-1.0, 0.0, 0.0])


class SimpleSceneGraph:
    """简单场景图（用于测试）"""
    
    def __init__(self):
        self.objects = {}
        self.obstacles = []
    
    def add_object(self, name: str, position: np.ndarray, 
                   radius: float = 0.1):
        """添加物体"""
        self.objects[name] = {
            "position": position,
            "radius": radius
        }
    
    def add_obstacle(self, name: str, position: np.ndarray, 
                     radius: float = 0.1):
        """添加障碍物"""
        self.obstacles.append({
            "name": name,
            "position": position,
            "radius": radius
        })
    
    def get_position(self, name: str) -> np.ndarray:
        """获取物体位置"""
        return self.objects.get(name, {}).get("position", np.zeros(3))
    
    def get_obstacles(self) -> List[Dict]:
        """获取所有障碍物"""
        return self.obstacles


# 测试代码
if __name__ == "__main__":
    print("=== 测试约束生成器 ===")
    
    # 创建场景
    scene = SimpleSceneGraph()
    scene.add_object("cup", np.array([0.5, 0.3, 0.2]))
    scene.add_obstacle("wall", np.array([0.6, 0.3, 0.2]), 0.05)
    
    # 创建约束生成器
    generator = ConstraintGenerator(scene)
    
    # 测试用例
    test_cases = [
        {
            "intent": {
                "action": "place",
                "object": "cup",
                "target": "table",
                "constraints": ["avoid_collision", "keep_upright"]
            },
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.5, 0.2])
        },
        {
            "intent": {
                "action": "pick",
                "object": "cup",
                "constraints": ["avoid_collision"]
            },
            "current": np.array([0.3, 0.3, 0.5]),
            "goal": np.array([0.5, 0.3, 0.2])
        }
    ]
    
    for i, test in enumerate(test_cases):
        print(f"\n测试 {i+1}: {test['intent']['action']} {test['intent']['object']}")
        constraints = generator.generate(
            test["intent"], test["current"], test["goal"]
        )
        print(f"生成 {len(constraints)} 个约束:")
        for c in constraints:
            print(f"  - {c['name']}: {c['type']}")

