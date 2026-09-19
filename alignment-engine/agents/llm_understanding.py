"""
LLM理解层模块
功能：将自然语言指令转换为结构化意图
"""

import json
from typing import Dict, List, Optional


class LLMUnderstandingLayer:
    """
    LLM理解层：将自然语言指令转换为结构化意图
    
    核心功能：
    1. 解析自然语言指令
    2. 提取动作、对象、目标、约束
    3. 输出结构化JSON
    """
    
    def __init__(self, llm_client=None):
        """
        初始化LLM理解层
        
        Args:
            llm_client: LLM API客户端，需要实现generate方法
        """
        self.llm = llm_client
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示"""
        return """You are a robot task understanding assistant.
        
Given a natural language instruction and scene description, extract the structured intent.

Output JSON format:
{
    "action": "pick|place|move|push|pull|rotate|open|close",
    "object": "object_name",
    "target": "target_location_or_object",
    "constraints": ["constraint1", "constraint2"],
    "priority": "high|medium|low",
    "confidence": 0.0-1.0
}

Rules:
1. action: The main action to perform
2. object: The object being acted upon
3. target: The destination or target object
4. constraints: List of constraints like "avoid_collision", "keep_upright", "slow_speed"
5. priority: Task priority level
6. confidence: Your confidence in the interpretation (0-1)

If the instruction is ambiguous, include multiple possible interpretations.
"""
    
    def understand(self, instruction: str, scene_description: str) -> Dict:
        """
        理解自然语言指令
        
        Args:
            instruction: 自然语言指令
            scene_description: 场景描述
            
        Returns:
            结构化意图字典
        """
        prompt = self._build_prompt(instruction, scene_description)
        
        if self.llm is None:
            # 如果没有LLM客户端，使用规则解析
            return self._rule_based_parse(instruction, scene_description)
        
        # 调用LLM
        response = self.llm.generate(
            system_prompt=self.system_prompt,
            user_prompt=prompt
        )
        
        # 解析JSON
        try:
            intent = json.loads(response)
            return self._validate_intent(intent)
        except json.JSONDecodeError:
            # 如果LLM输出不是有效JSON，尝试提取
            return self._extract_json_from_response(response)
    
    def _build_prompt(self, instruction: str, scene_description: str) -> str:
        """构建用户提示"""
        return f"""Instruction: {instruction}

Scene Description:
{scene_description}

Please extract the structured intent from this instruction."""
    
    def _rule_based_parse(self, instruction: str, scene_description: str) -> Dict:
        """
        基于规则的解析（备用方案）
        
        当没有LLM客户端时使用
        """
        intent = {
            "action": None,
            "object": None,
            "target": None,
            "constraints": [],
            "priority": "medium",
            "confidence": 0.5
        }
        
        # 动作识别
        action_keywords = {
            "pick": ["pick", "grab", "grasp", "take", "拿起", "抓取"],
            "place": ["place", "put", "drop", "放下", "放置"],
            "move": ["move", "go", "移动", "走到"],
            "push": ["push", "shove", "推"],
            "pull": ["pull", "drag", "拉"],
            "rotate": ["rotate", "turn", "旋转", "转动"],
            "open": ["open", "打开"],
            "close": ["close", "shut", "关闭"]
        }
        
        instruction_lower = instruction.lower()
        for action, keywords in action_keywords.items():
            if any(kw in instruction_lower for kw in keywords):
                intent["action"] = action
                break
        
        # 对象识别（简化版）
        # 实际应用中需要NER或更复杂的解析
        common_objects = ["cup", "ball", "box", "table", "chair", 
                         "杯子", "球", "盒子", "桌子", "椅子"]
        for obj in common_objects:
            if obj in instruction_lower:
                intent["object"] = obj
                break
        
        # 约束识别
        constraint_keywords = {
            "avoid_collision": ["avoid", "小心", "避开"],
            "keep_upright": ["upright", "正立", "不要倒"],
            "slow_speed": ["slow", "slowly", "慢慢", "轻"]
        }
        
        for constraint, keywords in constraint_keywords.items():
            if any(kw in instruction_lower for kw in keywords):
                intent["constraints"].append(constraint)
        
        return intent
    
    def _validate_intent(self, intent: Dict) -> Dict:
        """验证意图格式"""
        required_fields = ["action", "object", "target", "constraints", "priority", "confidence"]
        
        for field in required_fields:
            if field not in intent:
                if field == "constraints":
                    intent[field] = []
                elif field == "priority":
                    intent[field] = "medium"
                elif field == "confidence":
                    intent[field] = 0.5
                else:
                    intent[field] = None
        
        # 验证action类型
        valid_actions = ["pick", "place", "move", "push", "pull", "rotate", "open", "close"]
        if intent["action"] not in valid_actions:
            intent["confidence"] *= 0.5  # 降低置信度
        
        return intent
    
    def _extract_json_from_response(self, response: str) -> Dict:
        """从LLM响应中提取JSON"""
        import re
        
        # 尝试找到JSON块
        json_pattern = r'\{[^{}]+\}'
        matches = re.findall(json_pattern, response)
        
        for match in matches:
            try:
                return json.loads(match)
            except json.JSONDecodeError:
                continue
        
        # 如果找不到，返回默认值
        return {
            "action": None,
            "object": None,
            "target": None,
            "constraints": [],
            "priority": "medium",
            "confidence": 0.3
        }


class MockLLMClient:
    """模拟LLM客户端（用于测试）"""
    
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """模拟生成响应"""
        # 简单的规则匹配
        if "cup" in user_prompt.lower() or "杯子" in user_prompt:
            return json.dumps({
                "action": "pick",
                "object": "cup",
                "target": None,
                "constraints": [],
                "priority": "medium",
                "confidence": 0.8
            })
        elif "table" in user_prompt.lower() or "桌子" in user_prompt:
            return json.dumps({
                "action": "place",
                "object": "cup",
                "target": "table",
                "constraints": ["avoid_collision"],
                "priority": "medium",
                "confidence": 0.8
            })
        else:
            return json.dumps({
                "action": "move",
                "object": None,
                "target": None,
                "constraints": [],
                "priority": "low",
                "confidence": 0.5
            })


# 测试代码
if __name__ == "__main__":
    # 测试规则解析
    llm_layer = LLMUnderstandingLayer()
    
    test_cases = [
        ("把杯子放到桌子上", "桌面上有一个红色杯子"),
        ("pick up the ball", "A ball is on the floor"),
        ("慢慢移动到门口", "The robot is in the room"),
    ]
    
    print("=== 测试LLM理解层 ===")
    for instruction, scene in test_cases:
        result = llm_layer.understand(instruction, scene)
        print(f"\n指令: {instruction}")
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
