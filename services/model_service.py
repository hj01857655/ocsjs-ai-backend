# -*- coding: utf-8 -*-
"""
AI模型服务 - 适配新架构
"""
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from utils.logger import get_logger
from constants import SYSTEM_PROMPT

logger = get_logger(__name__)

@dataclass
class ModelResponse:
    """模型响应数据类"""
    content: str
    proxy_name: str
    model: str
    tokens: Dict[str, int]
    raw_response: Dict[str, Any]

class ModelService:
    """AI模型服务"""

    def __init__(self):
        self.timeout = 60.0  # 增加超时时间到60秒
        self.max_tokens = 1000
        self.temperature = 0.7

    def generate_response(self, prompt: str, model: Optional[str] = None,
                         parameters: Optional[Dict[str, Any]] = None) -> Optional[ModelResponse]:
        """生成AI响应"""
        try:
            # 从API代理池获取代理
            from services.api_proxy_pool import get_api_proxy_pool
            proxy_pool = get_api_proxy_pool()

            logger.info(f"获取代理池状态...")
            pool_status = proxy_pool.get_pool_status()
            logger.info(f"代理池状态: 总计 {pool_status['total_proxies']} 个，活跃 {pool_status['active_proxies']} 个")

            # 选择最佳代理
            proxy = proxy_pool.select_best_proxy(model)
            if not proxy:
                logger.error("没有可用的API代理")
                return None

            # 增强日志输出，显示使用的代理和模型
            actual_model = model or proxy.model
            logger.info(f"选择代理: {proxy.name} (模型: {actual_model})")
            print(f"🔌 使用第三方代理: {proxy.name} | 🤖 使用模型: {actual_model}")

            # 调用API
            result = proxy_pool.call_api(proxy, actual_model, [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ])

            # 直接处理API返回的结果（不再期望包装的success格式）
            if result and 'choices' in result and result['choices']:
                content = result['choices'][0]['message']['content']
                used_model = result.get('model', actual_model)

                logger.info(f"AI响应成功，内容长度: {len(content)}")
                print(f"✅ 代理 {proxy.name} 调用模型 {used_model} 成功")

                return ModelResponse(
                    content=content,
                    proxy_name=proxy.name,
                    model=used_model,
                    tokens=result.get('usage', {}),
                    raw_response=result
                )
            else:
                logger.error(f"API响应格式错误: {result}")
                print(f"❌ 代理 {proxy.name} 调用失败: 响应格式错误")
                return None

        except Exception as e:
            logger.error(f"生成响应异常: {str(e)}")
            print(f"💥 生成响应异常: {str(e)}")
            return None

    def _try_api_call_with_fallback(self, proxy, primary_model: str, prompt: str) -> Dict[str, Any]:
        """尝试调用API，如果失败则根据错误码决定是重试还是切换模型"""
        # 系统提示
        system_prompt = "你是一个专业的考试答题助手。请直接回答答案，不要解释。选择题只回答选项的内容(如：地球)；多选题用#号分隔答案,只回答选项的内容(如中国#世界#地球)；判断题只回答: 正确/对/true/√ 或 错误/错/false/×；填空题直接给出答案。"
        
        # 定义消息
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        # 首次尝试使用主要模型
        from services.api_proxy_pool import get_api_proxy_pool
        proxy_pool = get_api_proxy_pool()
        
        result = proxy_pool.call_api(proxy, primary_model, messages)
        
        # 检查结果
        if result.get('success'):
            result['model_used'] = primary_model
            return result
            
        # 分析错误
        error_text = result.get('error', '')
        status_code = None
        
        # 尝试从错误文本中提取状态码
        import re
        status_match = re.search(r'HTTP (\d+)', error_text)
        if status_match:
            status_code = int(status_match.group(1))
        
        # 根据错误类型决定策略
        if status_code:
            # 5xx 错误：服务器错误，尝试切换模型
            if status_code >= 500:
                print(f"🔄 服务器错误 {status_code}，尝试切换模型...")
                return self._try_alternative_models(proxy, primary_model, messages)
                
            # 402 错误：付款要求，直接切换模型
            elif status_code == 402:
                print(f"💰 付款要求错误 402，尝试切换模型...")
                return self._try_alternative_models(proxy, primary_model, messages)
                
            # 429 错误：请求过多，尝试切换模型
            elif status_code == 429:
                print(f"⏱️ 请求过多错误 429，尝试切换模型...")
                return self._try_alternative_models(proxy, primary_model, messages)
                
            # 其他 4xx 错误：客户端错误，可能需要重试
            elif status_code >= 400:
                print(f"⚠️ 客户端错误 {status_code}，尝试重试...")
                # 重试一次
                time.sleep(2)  # 等待2秒
                retry_result = proxy_pool.call_api(proxy, primary_model, messages)
                
                # 如果重试成功
                if retry_result.get('success'):
                    retry_result['model_used'] = primary_model
                    return retry_result
                    
                # 重试失败，尝试切换模型
                print(f"❌ 重试失败，尝试切换模型...")
                return self._try_alternative_models(proxy, primary_model, messages)
        
        # 其他错误：尝试切换模型
        if "timeout" in error_text.lower() or "ssl" in error_text.lower():
            print(f"🔌 连接错误，尝试切换模型...")
            return self._try_alternative_models(proxy, primary_model, messages)
            
        # 返回原始错误结果
        result['model_used'] = primary_model
        return result

    def _try_alternative_models(self, proxy, primary_model: str, messages: List[Dict]) -> Dict[str, Any]:
        """尝试使用代理支持的其他模型"""
        from services.api_proxy_pool import get_api_proxy_pool
        proxy_pool = get_api_proxy_pool()
        
        # 获取代理支持的其他模型
        alternative_models = [m for m in proxy.models if m != primary_model]
        
        if not alternative_models:
            print(f"⚠️ 代理 {proxy.name} 没有其他可用模型")
            return {"success": False, "error": "没有其他可用模型", "model_used": primary_model}
            
        print(f"🔍 尝试 {len(alternative_models)} 个备选模型...")
        
        # 尝试每个备选模型
        for alt_model in alternative_models:
            print(f"🔄 尝试备选模型: {alt_model}")
            result = proxy_pool.call_api(proxy, alt_model, messages)
            
            if result.get('success'):
                print(f"✅ 备选模型 {alt_model} 调用成功")
                result['model_used'] = alt_model
                return result
                
            print(f"❌ 备选模型 {alt_model} 调用失败: {result.get('error')}")
        
        # 所有备选模型都失败
        print(f"❌ 所有备选模型都失败")
        return {"success": False, "error": "所有模型都调用失败", "model_used": primary_model}

    def generate_answer(self, question: str, question_type: Optional[str] = None,
                       options: Optional[str] = None) -> Optional[str]:
        """生成题目答案"""
        try:
            # 构建提示词
            prompt = self._build_prompt(question, question_type, options)

            # 生成响应
            response = self.generate_response(prompt)

            if response:
                # 清理和规范化答案
                answer = self._clean_answer(response.content, question_type)
                return answer

            return None

        except Exception as e:
            logger.error(f"生成答案异常: {str(e)}")
            return None

    def _build_prompt(self, question: str, question_type: Optional[str] = None, options: Optional[str] = None) -> str:
        """构建AI提示词"""
        prompt = f"请回答以下题目：\n\n题目：{question}\n"

        if question_type:
            type_map = {
                'single': '单选题',
                'multiple': '多选题',
                'judge': '判断题',
                'judgement': '判断题',
                'completion': '填空题'
            }
            prompt += f"题型：{type_map.get(question_type, question_type)}\n"

        if options:
            prompt += f"选项：\n{options}\n"

        # 根据题型给出不同的答案要求
        if question_type == 'multiple':
            prompt += "\n注意：这是多选题，如果有多个正确答案，请直接给出每个正确选项的内容，多个答案之间用#分隔。例如：选项内容1#选项内容2#选项内容3。不要包含选项字母(A、B、C、D)，只返回选项的具体内容。"
        elif question_type == 'single':
            prompt += "\n注意：这是单选题，请直接给出正确选项的内容，不要包含选项字母(A、B、C、D)。"
        elif question_type == 'judge':
            prompt += "\n注意：这是判断题，请只回答'正确'或'错误'。"
        else:
            prompt += "\n请直接给出答案，不需要解释过程。"
            
        # 增强指令，确保模型只返回答案
        prompt += "\n\n你的整个回复应该只包含答案本身，不要包含任何额外的文字、解释或选项字母。不要使用句子格式，只需给出选项内容。"

        return prompt

    def _clean_answer(self, raw_answer: str, question_type: Optional[str] = None) -> str:
        """清理和规范化模型返回的答案"""
        if not raw_answer:
            return ""

        # 首先提取实际答案（去除思考过程）
        answer = self._extract_answer(raw_answer)

        # 去除前后空白
        answer = answer.strip()
        
        # 移除可能的多余前缀
        prefixes_to_remove = ["答案:", "答案是:", "答案：", "答案是：", "选项", "正确答案:", "正确答案：", "正确答案是:", "正确答案是："]
        for prefix in prefixes_to_remove:
            if answer.startswith(prefix):
                answer = answer[len(prefix):].strip()
                
        # 处理判断题答案
        if question_type == 'judge':
            # 标准化判断题答案
            answer = answer.lower()
            if any(x in answer for x in ["正确", "对", "true", "√", "yes", "y"]):
                return "正确"
            elif any(x in answer for x in ["错误", "错", "false", "×", "no", "n"]):
                return "错误"
                
        # 移除可能的选项字母前缀
        import re
        answer = re.sub(r'^[A-D][\.、:：\s]', '', answer)
        answer = re.sub(r'#\s*[A-D][\.、:：\s]', '#', answer)
                
        # 如果没有特殊处理，返回清理后的原始答案
        return answer

    def _extract_answer(self, content: str) -> str:
        """提取实际答案，去除思考过程"""
        if not content:
            return ""

        # 如果包含 <think> 标签，提取 </think> 后面的内容
        if '<think>' in content and '</think>' in content:
            # 找到最后一个 </think> 标签
            think_end = content.rfind('</think>')
            if think_end != -1:
                answer = content[think_end + 8:].strip()  # 8 是 '</think>' 的长度
                if answer:
                    return answer

        # 如果没有思考标签或提取失败，返回原内容
        return content.strip()

    def batch_generate(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量生成答案"""
        results = []

        for i, question_data in enumerate(questions):
            question = question_data.get('question', '')
            question_type = question_data.get('type')
            options = question_data.get('options')

            if not question:
                results.append({
                    'index': i,
                    'success': False,
                    'error': '题目内容为空'
                })
                continue

            try:
                answer = self.generate_answer(question, question_type, options)

                if answer:
                    results.append({
                        'index': i,
                        'question': question,
                        'answer': answer,
                        'success': True
                    })
                else:
                    results.append({
                        'index': i,
                        'question': question,
                        'success': False,
                        'error': '生成答案失败'
                    })

            except Exception as e:
                results.append({
                    'index': i,
                    'question': question,
                    'success': False,
                    'error': str(e)
                })

            # 添加延迟避免过于频繁的请求
            time.sleep(0.1)

        return results

# 全局模型服务实例
_model_service = None

def get_model_service() -> ModelService:
    """获取模型服务实例"""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
