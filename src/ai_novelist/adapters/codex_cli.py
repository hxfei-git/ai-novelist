"""Codex CLI adapter."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError, AgentCallOptions


class CodexCLIError(AgentAdapterError):
    """Raised when Codex CLI cannot produce a usable response."""


@dataclass
class CodexCLIAdapter(AgentAdapter):
    codex_bin: str = "codex"
    timeout_seconds: int = 180
    mock: bool = False

    def complete(self, prompt: str, workspace: Path, options: AgentCallOptions | None = None) -> str:
        del options
        if self.mock:
            return self._mock_response(prompt)

        command = [
            self.codex_bin,
            "exec",
            "--json",
            "--skip-git-repo-check",
            "-C",
            str(workspace),
            prompt,
        ]
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                input="",
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise CodexCLIError(f"Codex CLI not found: {self.codex_bin}") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodexCLIError(f"Codex CLI timed out after {self.timeout_seconds}s") from exc

        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise CodexCLIError(f"Codex CLI failed with exit code {result.returncode}: {message}")

        text = self._extract_text(result.stdout)
        if not text.strip():
            raise CodexCLIError("Codex CLI returned empty output")
        return text

    def _extract_text(self, stdout: str) -> str:
        final_messages: list[str] = []
        raw_lines: list[str] = []

        for line in stdout.splitlines():
            if not line.strip():
                continue
            raw_lines.append(line)
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = self._text_from_event(event)
            if message:
                final_messages.append(message)

        if final_messages:
            return final_messages[-1].strip()
        return "\n".join(raw_lines).strip()

    def _text_from_event(self, event: dict) -> str:
        for key in ("message", "content", "text", "last_message"):
            value = event.get(key)
            if isinstance(value, str):
                return value

        item = event.get("item")
        if isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str):
                return text
            content = item.get("content")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        parts.append(part["text"])
                if parts:
                    return "\n".join(parts)

        return ""

    def _mock_response(self, prompt: str) -> str:
        if "AGENT: outline_stage_role" in prompt:
            return self._mock_outline_stage_role(prompt)
        if "AGENT: outline_stage_synthesizer" in prompt:
            return self._mock_outline_stage_synthesizer(prompt)
        if "AGENT: bible_update_extractor" in prompt:
            return self._mock_bible_update_extractor()
        if "AGENT: bible_conflict_checker" in prompt:
            return '{"conflicts": []}'
        if "AGENT: bible_update_synthesizer" in prompt:
            return "## 已写入\n- 小说圣经已吸收当前稳定设定。\n\n## 未写入\n- 暂无。\n\n## 待确认\n- open_questions 和冲突项仍需人工确认。"
        if "AGENT: research_intent" in prompt:
            return self._mock_research_intent(prompt)
        if "AGENT: director" in prompt:
            return self._mock_director(prompt)
        if "AGENT: retrieval_context_synthesizer" in prompt:
            return self._mock_retrieval_context()
        if "AGENT: direction_proposer" in prompt:
            return self._mock_directions()
        if "AGENT: outline_reviser" in prompt:
            return self._mock_outline_revised()
        if "AGENT: outline_editor" in prompt:
            return self._mock_outline_editor(revised="修订要求：暂无" not in prompt)
        if "AGENT: version_comparator" in prompt:
            return self._mock_version_comparison()
        if "AGENT: world_builder" in prompt:
            return self._mock_worldbuilding()
        if "AGENT: outline_planner" in prompt:
            return self._mock_outline_plan()
        if "AGENT: chapter_goal_agent" in prompt:
            return self._mock_chapter_goal_report()
        if "AGENT: chapter_conflict_agent" in prompt:
            return self._mock_chapter_conflict_report()
        if "AGENT: chapter_hook_agent" in prompt:
            return self._mock_chapter_hook_report()
        if "AGENT: chapter_card_synthesizer" in prompt:
            return self._mock_chapter_card()
        if "AGENT: scene_breakdown_agent" in prompt:
            return self._mock_scene_breakdown_report()
        if "AGENT: scene_conflict_check_agent" in prompt:
            return self._mock_scene_conflict_report()
        if "AGENT: scene_synthesizer" in prompt:
            return self._mock_scene_cards()
        if "AGENT: chapter_planner" in prompt:
            return self._mock_chapter_plan()
        if "AGENT: chapter_writer" in prompt:
            return self._mock_chapter(revised=self._is_revised_prompt(prompt))
        if "AGENT: dialogue_enhancer" in prompt:
            return self._mock_chapter(revised=self._is_revised_prompt(prompt))
        if "AGENT: atmosphere_enhancer" in prompt:
            return self._mock_chapter(revised=self._is_revised_prompt(prompt))
        if "AGENT: hook_enhancer" in prompt:
            return self._mock_chapter(revised=self._is_revised_prompt(prompt))
        if "AGENT: style_normalizer" in prompt:
            return self._mock_chapter(revised=self._is_revised_prompt(prompt))
        if "AGENT: continuity_editor" in prompt:
            return self._mock_review_role("连续性", revised=self._is_revised_prompt(prompt))
        if "AGENT: structure_editor" in prompt:
            return self._mock_review_role("结构", revised=self._is_revised_prompt(prompt))
        if "AGENT: character_arc_editor" in prompt:
            return self._mock_review_role("人物弧光", revised=self._is_revised_prompt(prompt))
        if "AGENT: style_editor" in prompt:
            return self._mock_review_role("风格", revised=self._is_revised_prompt(prompt))
        if "AGENT: simulated_reader" in prompt:
            return self._mock_review_role("模拟读者", revised=self._is_revised_prompt(prompt))
        if "AGENT: review_synthesizer" in prompt:
            return self._mock_review_synthesizer(revised=self._is_revised_prompt(prompt))
        if "AGENT: revision_planner" in prompt:
            return self._mock_revision_plan()
        if "AGENT: targeted_reviser" in prompt:
            return self._mock_chapter(revised=True)
        if "AGENT: revision_self_check" in prompt:
            return json.dumps(
                {
                    "tasks_status": [
                        {"task": "补强维修站异常记录。", "status": "done", "evidence": "醒来场景已出现审计编号异常。"},
                        {"task": "补明纸质文本禁忌。", "status": "done", "evidence": "手稿场景已说明纸质文本不可即时追踪。"},
                        {"task": "强化东七气闸倒计时。", "status": "done", "evidence": "结尾场景已强化倒计时压力。"},
                    ],
                    "new_risks": [],
                    "decision": "pass",
                },
                ensure_ascii=False,
            )
        if "AGENT: chapter_summarizer" in prompt:
            return self._mock_chapter_summary()
        if "AGENT: final_bible_update_extractor" in prompt:
            return self._mock_final_bible_updates()
        if "AGENT: editor" in prompt:
            return self._mock_editor_review(revised=self._is_revised_prompt(prompt))
        return self._mock_outline(prompt)


    def _mock_outline_stage_role(self, prompt: str) -> str:
        stage = self._extract_prompt_field(prompt, "STAGE") or "direction"
        role = self._extract_prompt_field(prompt, "ROLE") or "阶段 Agent"
        labels = {
            "direction": "方向定位",
            "concept": "故事概念",
            "worldbuilding": "世界观设定",
            "characters": "人物关系",
            "story_flow": "故事流程",
            "volume_outline": "分卷大纲",
            "chapter_outline": "章节大纲",
            "review_lock": "审稿锁定",
        }
        return (
            f"- 机会：{role}认为{labels.get(stage, stage)}可以围绕月球城市、记忆罪案和纸质手稿形成清晰卖点。\n"
            f"- 风险：需要避免在{labels.get(stage, stage)}阶段提前写成完整大纲。\n"
            "- 建议：保留一个待用户确认的核心选择，并给出可锁定的阶段结论。"
        )

    def _mock_outline_stage_synthesizer(self, prompt: str) -> str:
        stage = self._extract_prompt_field(prompt, "STAGE") or "direction"
        data = {
            "direction": (
                "## 方向定位稿\n"
                "1. 类型定位：黑暗悬疑科幻，以记忆罪案和身份追查提供长线吸引。\n"
                "2. 主角行动原则：低调求证、借势破局，每次推进都承担旧罪代价。\n"
                "3. 核心爽点：用被忽视的纸质线索反制记忆审计体系。\n"
                "4. 核心冲突：求生本能与公开旧罪之间持续对抗。\n"
                "5. 情绪基调：冷峻、压迫、疑云递进，胜利必须带苦涩代价。\n"
                "6. 主题边界：讨论秩序吞噬记忆，不滑向无关恋爱或轻喜剧。\n"
                "7. 反转原则：每次反转都改变主角责任认知，而非只抛新名词。\n"
                "8. 禁区：不提前展开具体规则、人物细则、章节桥段和名词清单。"
            ),
            "concept": (
                "## Director 汇总\n故事概念锁定为记忆审计时代的罪案追查：核心冲突是主角求生本能与旧罪公开之间的对抗；主题表达是安全秩序吞噬个人记忆后的代价；反转机制围绕手稿预言其实来自被删除记忆的残留索引。\n\n"
                "## 已采用设定\n采用纸质手稿作为不可被系统预测的异常媒介，并让每次预言都反咬主角旧身份。\n\n"
                "## 仍需确认的问题\n是否接受最终反转为主角曾主动授权关键记忆删除？"
            ),
            "worldbuilding": (
                "## Director 汇总\n世界观以银湾月球城、记忆审计编号、月背冷库和灰籍居民为核心。规则服务案件推进，而不是孤立解释。\n\n"
                "## 已采用设定\n锁定档案局、记忆公司和地下写作者三方冲突，让每条规则都带来现实代价。\n\n"
                "## 仍需确认的问题\n是否接受月背冷库保存被删除记忆这一核心规则？"
            ),
            "characters": (
                "## Director 汇总\n林澈的弧光从逃避旧罪到公开自证；许岚代表被删除者后代；沈博士代表秩序化垄断。\n\n"
                "## 已采用设定\n锁定主角旧罪与盟友受害史的关系冲突，地下写作者联盟既帮助也利用主角。\n\n"
                "## 仍需确认的问题\n是否接受林澈曾参与一次关键记忆删除？"
            ),
            "story_flow": (
                "## Director 汇总\n故事按异常手稿、事故验证、冷库追查、旧罪曝光、公开自证推进。每阶段都扩大代价。\n\n"
                "## 已采用设定\n用纸质手稿作为每次转折的触发器，前三章主打事故倒计时，中段转入冷库线索，终局进入听证会。\n\n"
                "## 仍需确认的问题\n是否接受终局以公开旧罪换取灰籍身份恢复？"
            ),
            "volume_outline": (
                "## Director 汇总\n分卷大纲采用三卷：手稿预言事故、月背冷库真相、听证会公开自证。每卷都有独立高潮，并用下一卷钩子承接。\n\n"
                "## 已采用设定\n第一卷以事故被验证收束，第二卷以主角旧授权曝光收束，第三卷以公开自证和系统崩塌收束。\n\n"
                "## 仍需确认的问题\n是否接受三卷结构作为全书推进基准？"
            ),
            "chapter_outline": (
                "## Director 汇总\n章节大纲采用 12 章结构：前 3 章建立手稿异常和第一起事故，中 4-8 章进入冷库与三方追逐，后 9-12 章完成旧罪公开和身份恢复。\n\n"
                "## 已采用设定\n每章保留一个可执行场景目标、一个线索钩子和一个情绪代价，优先保证第 1-3 章可直接进入章节细纲。\n\n"
                "## 仍需确认的问题\n是否以 12 章作为章节规划基准？"
            ),
            "review_lock": (
                "## Director 汇总\n终审认为八阶段产物连续：方向、概念、规则、人物、流程、分卷和章节基准一致，可以锁定为最终大纲。\n\n"
                "## 已采用设定\n未发现与检索上下文或已锁定阶段冲突的设定，下一步可进入章节细纲，优先拆解第 1-3 章。\n\n"
                "## 仍需确认的问题\n是否锁定最终大纲并写入 outline.md？"
            ),
        }
        return data.get(stage, data["direction"])


    def _mock_bible_update_extractor(self) -> str:
        return json.dumps(
            {
                "project": {
                    "title": "月城手稿",
                    "genre": "科幻悬疑",
                    "subgenre": "记忆罪案",
                    "core_experience": "在月球城市追查纸质手稿预言和被删除的旧罪。",
                    "tone_keywords": ["黑暗", "悬疑", "科幻", "罪感"],
                },
                "concept": {
                    "logline": "失忆工程师发现纸质手稿正在预言事故，并追查自己被删除的旧罪。",
                    "premise": "纸质手稿绕过预测系统，持续把主角推向月背冷库和公开自证。",
                    "core_conflict": "主角求生本能与公开旧罪之间的对抗。",
                    "theme": "安全秩序吞噬个人记忆后的代价。",
                    "central_question": "主角能否用公开罪证换回被删除者的身份？",
                    "ending_direction": "公开旧罪，恢复灰籍身份。",
                },
                "world_rules": [
                    {"name": "记忆审计", "description": "任何记忆备份都必须留下审计编号。", "limitation": "失效编号会暴露身份异常。", "cost": "公开未审计记忆会让相关人员失去合法身份。", "source_stage": "worldbuilding", "source_hint": "worldbuilding: 记忆审计规则"},
                    {"name": "纸质手稿", "description": "纸质文本无法被城市系统即时追踪。", "limitation": "传播慢且容易成为犯罪证据。", "cost": "持有者会被档案局追查。", "source_stage": "concept", "source_hint": "concept: 纸质手稿禁忌"},
                ],
                "characters": [
                    {"name": "林澈", "role": "主角", "identity": "失忆工程师", "external_goal": "追查手稿来源并阻止事故。", "internal_need": "承认并承担旧罪。", "secret": "曾参与关键记忆删除。", "arc": "从逃避旧罪到公开自证。", "source_hint": "characters: 主角设定"},
                    {"name": "许岚", "role": "盟友", "identity": "被删除者后代", "source_hint": "characters: 盟友设定"},
                    {"name": "沈博士", "role": "对手", "identity": "记忆秩序维护者", "source_hint": "characters: 对手设定"},
                ],
                "plot_threads": [
                    {"name": "手稿预言", "description": "纸质手稿持续预告事故并逼近主角旧身份。", "status": "active", "related_chapters": [1, 2, 3], "source_hint": "story_flow: 手稿预言线"}
                ],
                "foreshadowing": [
                    {"id": "F001", "setup_text": "失效审计编号", "payoff_text": "证明主角身份被删除。", "status": "planned", "source_hint": "chapter_outline: 审计编号伏笔"}
                ],
                "style_guide": {"pov": "第三人称贴近主角", "tone": "黑暗悬疑科幻"},
            },
            ensure_ascii=False,
        )

    def _extract_prompt_field(self, prompt: str, name: str) -> str:
        match = re.search(rf"^{name}:\s*(.*)$", prompt, re.MULTILINE)
        return match.group(1).strip() if match else ""


    def _is_revised_prompt(self, prompt: str) -> bool:
        if re.search(r"^REVISION_COUNT:\s*[1-9]", prompt, re.MULTILINE):
            return True
        if "draft_v2" in prompt or "修订版" in prompt or "revision_plan_v1" in prompt:
            return True
        return "修订次数：0" not in prompt and "REVISION_COUNT: 0" not in prompt

    def _mock_research_intent(self, prompt: str) -> str:
        request = self._extract_director_request(prompt)
        query = ""
        quote_match = re.search(r"[《\"]([^》\"]+)[》\"]", request)
        if quote_match:
            query = quote_match.group(1).strip()
        elif "苟在初圣" in request:
            query = "苟在初圣"
        else:
            query = request.strip()
        author = "初圣" if "作者是初圣" in request or "作者：初圣" in request else ""
        need = "yes" if any(word in request for word in ("同人", "原作", "查一下", "调研", "research", "/research", "苟在初圣")) else "no"
        intent = "fanfic" if "同人" in request else "web_research" if need == "yes" else "original"
        return (
            f"NEED_RESEARCH: {need}\n"
            f"QUERY: {query}\n"
            f"WORK_TITLE: {query if need == 'yes' else ''}\n"
            f"AUTHOR: {author}\n"
            f"INTENT: {intent}\n"
            "REASON: mock research intent"
        )


    def _mock_retrieval_context(self) -> str:
        return (
            "# 检索上下文\n\n"
            "## 查询意图\n- 整理目标作品或题材的可用公开信息。\n\n"
            "## 可用事实\n- 搜索结果显示该题材包含低调求生、资源积累、身份隐藏等关键词。\n\n"
            "## 创作相关线索\n- 可用于约束同人创作的基调、冲突来源和读者预期。\n\n"
            "## 不确定点\n- 角色名、完整世界观和关键剧情节点仍需用户确认。\n\n"
            "## 来源索引\n- 见 research_sources.json。\n\n"
            "## 使用边界\n- 不得把搜索摘要直接当作原作正史。"
        )


    def _mock_director(self, prompt: str) -> str:
        request = self._extract_director_request(prompt).lower()
        chapter = self._extract_chapter(request)

        def response(action: str, target: str, intent: str, message: str, instruction: str = "", locks: str = "", styles: str = "", chapter_value: str = "") -> str:
            return (
                f"ACTION: {action}\n"
                f"TARGET: {target}\n"
                f"INTENT: {intent}\n"
                f"MESSAGE: {message}\n"
                f"INSTRUCTION: {instruction}\n"
                f"LOCKED_CONSTRAINTS: {locks}\n"
                f"STYLE_PREFERENCES: {styles}\n"
                f"CHAPTER: {chapter_value}"
            )

        if any(word in request for word in ("退出", "结束", "quit", "exit", "stop")):
            return response("stop", "project", "stop", "已结束本次创作对话。")
        if any(word in request for word in ("查看小说圣经", "展示小说圣经", "show bible", "view bible")):
            return response("show_bible", "novel_bible", "status", "我会展示当前小说圣经。")
        if any(word in request for word in ("初始化小说圣经", "生成小说圣经", "更新小说圣经", "init bible", "generate bible", "update bible")):
            action = "init_bible" if any(word in request for word in ("初始化", "生成", "init", "generate")) else "update_bible"
            return response(action, "novel_bible", "update", "我会基于当前稳定产物更新小说圣经。")
        if "active_workflow：outline" in prompt and any(word in request for word in ("查看", "展示", "看一下", "看下", "显示")):
            task_args = {}
            if "方向" in request:
                task_args["stage"] = "direction"
            elif "世界观" in request:
                task_args["stage"] = "worldbuilding"
            elif "人物" in request or "角色" in request:
                task_args["stage"] = "characters"
            elif "故事流程" in request or "流程" in request:
                task_args["stage"] = "story_flow"
            elif "分卷" in request:
                task_args["stage"] = "volume_outline"
            elif "章节" in request:
                task_args["stage"] = "chapter_outline"
            return json.dumps({
                "action": "show_outline",
                "requires_confirmation": False,
                "confidence": 95,
                "target": "outline",
                "intent": "status",
                "user_message": "我会展示当前大纲阶段内容。",
                "task_args": task_args,
            }, ensure_ascii=False)
        if "active_workflow：outline" in prompt and any(word in request for word in ("这个设定别改", "别改", "不要改", "保留")):
            return response("revise_outline", "outline", "lock", "已记录锁定约束，我会按该约束重跑当前大纲阶段。", request, request)
        if "active_workflow：outline" in prompt and "outline_stage_status：options_ready" in prompt:
            if any(word in request for word in ("查看", "展示", "看一下", "看下", "显示")):
                task_args = {}
                if "方向" in request:
                    task_args["stage"] = "direction"
                elif "世界观" in request:
                    task_args["stage"] = "worldbuilding"
                elif "人物" in request or "角色" in request:
                    task_args["stage"] = "characters"
                elif "故事流程" in request or "流程" in request:
                    task_args["stage"] = "story_flow"
                elif "分卷" in request:
                    task_args["stage"] = "volume_outline"
                elif "章节" in request:
                    task_args["stage"] = "chapter_outline"
                return json.dumps({
                    "action": "show_outline",
                    "requires_confirmation": False,
                    "confidence": 95,
                    "target": "outline",
                    "intent": "status",
                    "user_message": "我会展示当前大纲阶段内容。",
                    "task_args": task_args,
                }, ensure_ascii=False)
            compact_request = request.replace(" ", "")
            if any(word in compact_request for word in ("接下来", "下一步", "怎么办", "现在怎么办")) and not any(word in request for word in ("进入下一阶段", "推进到下一阶段")):
                return json.dumps({
                    "action": "ask_user",
                    "requires_confirmation": False,
                    "confidence": 92,
                    "target": "outline",
                    "intent": "status",
                    "user_message": "当前阶段：审稿锁定 options_ready\n未决问题：2 项。是否需要补一个失败代价？；终局拒绝是否保留一次？\n可选下一步：\n1. 直接回答上述问题，系统会吸收回答并重跑当前阶段。\n2. 明确说确认进入下一阶段，系统会先请求你确认。\n3. 说查看当前阶段产物，我会展示当前阶段内容。",
                }, ensure_ascii=False)
            if __import__("re").search(r"(^|[\s，,；;])\d+(?:[.、)]|(?=\D))", request):
                return response("revise_outline", "outline", "answer_pending_questions", "我会吸收你的补充回答，并重跑当前大纲阶段。", request, request)
            negated = any(word in request for word in ("不要进入下一阶段", "不进入下一阶段", "先不进入下一阶段", "暂不进入下一阶段", "别进入下一阶段", "不要推进", "先不推进", "暂不推进"))
            transition = any(word in request for word in ("下一阶段", "进入下一阶段", "推进到下一阶段", "进入后续阶段", "推进后续阶段"))
            lock_and_continue = any(word in request for word in ("锁定当前阶段", "锁定本阶段", "通过当前阶段", "通过本阶段")) and any(word in request for word in ("继续", "进入", "推进", "下一阶段"))
            delegated = any(word in request for word in ("你决定", "由你决定", "交给你", "默认处理", "你来定")) and any(word in request for word in ("继续", "进入", "推进", "下一阶段"))
            if not negated and (transition or lock_and_continue or delegated):
                task_args = {}
                if "世界观" in request:
                    task_args["stage"] = "worldbuilding"
                elif "人物" in request or "角色" in request:
                    task_args["stage"] = "characters"
                elif "故事流程" in request or "流程" in request:
                    task_args["stage"] = "story_flow"
                elif "分卷" in request:
                    task_args["stage"] = "volume_outline"
                elif "章节" in request:
                    task_args["stage"] = "chapter_outline"
                return json.dumps({
                    "action": "advance_current_stage",
                    "requires_confirmation": True,
                    "confidence": 95,
                    "target": "outline",
                    "intent": "approve",
                    "user_message": "我会先让当前阶段自行闭环未决问题，再锁定并进入下一阶段。",
                    "task_args": task_args,
                }, ensure_ascii=False)
            if any(word in request for word in ("加入", "增加", "补充", "强化", "削弱", "修改", "调整", "改成", "改为", "设为", "设定", "选择", "采用", "接受", "接收", "同意", "保留", "不要", "别", "更", "太")):
                return response("revise_outline", "outline", "revise", "我会把你的新意见合入当前阶段，并重跑阶段产物。", request)
        if any(word in request for word in ("保存大纲", "确认大纲", "approve")):
            return response("persist_outline", "outline", "approve", "我会保存当前大纲。")
        if any(word in request for word in ("保存", "落盘", "写入文件")):
            return response("persist_outputs", "project", "save", "我会保存当前已经生成的产物。")
        if any(word in request for word in ("当前获取的信息", "获取的信息", "搜集到的信息", "搜索的信息", "检索信息", "调研信息", "参考简报", "参考信息", "来源列表", "当前信息", "信息或大纲")):
            return response("show_reference", "project", "status", "我会展示当前已获取的调研信息和大纲状态。")
        if any(word in request for word in ("查看大纲", "当前大纲", "看一下大纲", "展示大纲", "show outline")):
            return response("show_outline", "outline", "status", "我会展示当前大纲正文。")
        if any(word in request for word in ("查看状态", "项目状态", "状态", "进度", "status", "哪里", "在哪", "路径", "位置")):
            return response("show_status", "project", "status", "我会展示当前项目状态和已有产物。")
        if any(word in request for word in ("多个方向", "三个方向", "不同方向", "variant", "备选", "讨论大纲", "敲定大纲", "聊大纲")):
            return response("propose_directions", "outline", "variant", "我会给出三个不同的创作方向供你选择。")
        if any(word in request for word in ("同人", "原作", "参考网络", "查一下", "调研", "research", "/research", "小说名", "苟在初圣")):
            return response("research", "project", "web_research", "我会先调研原作资料，再进入同人创作。")
        if any(word in request for word in ("这个设定别改", "别改", "不要改", "保留")):
            return response("show_status", "outline", "lock", "我已记录锁定约束，后续修订会遵守。", request, request)
        if any(word in request for word in ("审查大纲", "审稿大纲", "review outline", "看看大纲问题")):
            return response("review_outline", "outline", "review", "我会调用大纲编辑审查当前大纲。")
        if any(word in request for word in ("大纲", "主线", "罪感", "人物弧光", "更黑暗", "偏悬疑", "少点设定解释", "太普通")):
            styles = []
            if "黑暗" in request:
                styles.append("更黑暗")
            if "悬疑" in request:
                styles.append("偏悬疑")
            if "少点设定" in request:
                styles.append("少设定解释")
            action = "revise_outline" if any(word in request for word in ("太", "强化", "增强", "更", "修改", "调整", "少点")) else "generate_outline"
            intent = "revise" if action == "revise_outline" else "create"
            instruction = request if intent == "revise" else ""
            return response(action, "outline", intent, "我会处理大纲，并把你的要求转成可执行修订。", instruction, styles="，".join(styles))
        if any(word in request for word in ("场景卡", "规划场景", "拆场景", "场景规划", "场景")) and "章" in request:
            return response("plan_scenes", "scene_cards", "create", f"我会为第 {chapter or 1} 章规划场景卡。", chapter_value=chapter or "1")
        if any(word in request for word in ("章节卡", "规划第", "章规划")) and "章" in request:
            return response("plan_chapter", "chapter_card", "create", f"我会为第 {chapter or 1} 章生成章节卡。", chapter_value=chapter or "1")
        if any(word in request for word in ("世界观", "设定", "背景")):
            return response("worldbuild", "worldbuilding", "create", "我会先调度世界观 Agent，建立可持续写作的规则、冲突和素材。")
        if any(word in request for word in ("细纲", "章节规划", "章节计划")):
            return response("plan_chapters", "outline", "create", "我会调度章节细纲 Agent，把大纲拆成可执行章节。")
        if any(word in request for word in ("导出小说", "导出全文", "导出手稿", "export")):
            return response("export_project", "export", "export", "我会导出当前已定稿章节。")
        if any(word in request for word in ("定稿", "最终稿", "finalize")) and ("章" in request or chapter):
            return response("finalize_chapter", "final_chapter", "approve", f"我会定稿第 {chapter or 1} 章并更新小说圣经。", chapter_value=chapter or "1")
        if any(word in request for word in ("审稿", "编辑", "检查")):
            return response("review_chapter", "chapter", "review", "我会调度编辑 Agent 检查当前章节。", chapter_value=chapter)
        if any(word in request for word in ("重写", "修改章节", "改写", "修订章节")) or ("修订" in request and ("章" in request or chapter)):
            return response("revise_chapter", "chapter", "revise", "我会根据编辑意见调度章节写手重写当前章节。", request, chapter_value=chapter)
        if "写" in request and "章" in request:
            return response("write_chapter", "chapter", "create", f"我会调度章节写手生成第 {chapter or 1} 章。", chapter_value=chapter or "1")
        if any(word in request for word in ("想写", "创意", "小说", "故事")):
            return response("propose_directions", "outline", "variant", "我先把这个创意拆成几个可选方向，再由你决定大纲路线。")
        if any(word in request for word in ("聊聊", "你觉得", "怎么样", "好不好", "有意思", "感觉")):
            return response("chat", "project", "answer", "可以，我们先聊这个方向；如果你要我改产物，请明确说修改哪里。")
        return response("ask_user", "unknown", "answer", "你想让我下一步做什么？可以说：生成大纲、给三个方向、修改大纲、审查大纲或保存。")

    def _extract_director_request(self, prompt: str) -> str:
        for line in reversed(prompt.splitlines()):
            if line.startswith("最新用户输入："):
                return line.split("：", 1)[1].strip()
        return prompt.strip().splitlines()[-1] if prompt.strip() else ""

    def _extract_chapter(self, text: str) -> str:
        import re

        match = re.search(r"第\s*(\d+)\s*章", text)
        if match:
            return match.group(1)
        match = re.search(r"chapter\s*(\d+)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _mock_directions(self) -> str:
        return (
            "# 创作方向提案\n\n"
            "## 方向 1：记忆罪案\n- 核心概念：主角追查手稿预言案件，逐步发现自己曾是记忆篡改执行者。\n- 主角压力：真相越清晰，罪感越强。\n- 主要冲突：自我救赎与城市稳定。\n- 风格气质：黑暗悬疑。\n- 优点：人物弧光强。\n- 风险：需要控制信息密度。\n\n"
            "## 方向 2：月背冷库\n- 核心概念：手稿来自保存删除记忆的月背冷库。\n- 主角压力：找回记忆会伤害盟友。\n- 主要冲突：私人真相与公共秩序。\n- 风格气质：科幻调查。\n- 优点：世界观纵深强。\n- 风险：设定解释可能过多。\n\n"
            "## 方向 3：纸上叛乱\n- 核心概念：地下写作者用纸质小说绕过预测系统发动叛乱。\n- 主角压力：必须决定是否公开自己的罪证。\n- 主要冲突：叙事自由与安全系统。\n- 风格气质：群像悬疑。\n- 优点：适合长篇扩展。\n- 风险：主线可能分散。\n\n"
            "## 建议选择\n建议选择方向 1，因为它最能强化主角罪感和悬疑推进。"
        )

    def _mock_outline_revised(self) -> str:
        return (
            "# 修订版总大纲\n\n"
            "## 修订摘要\n强化主角罪感，将第三幕改为更黑暗的公开自证：林澈必须承认自己曾参与删除灰籍居民记忆。\n\n"
            "## 核心卖点\n失忆工程师追查预言手稿，却发现每个案件都在逼他面对自己的旧罪。\n\n"
            "## 主线目标\n阻止穹顶事故，同时找回被删除的记忆审计链。\n\n"
            "## 人物弧光\n林澈从自我辩解，到承认罪责，再到用公开罪证换取灰籍居民的身份恢复。\n\n"
            "## 三幕结构\n1. 手稿预言事故，林澈发现自己的审计编号不存在。\n2. 他追查月背冷库，确认自己曾执行记忆删除。\n3. 他公开旧罪，摧毁记忆公司的合法性，但也失去城市身份。\n\n"
            "## 关键冲突升级\n每次接近真相，都会牵连一个被他伤害过的人。\n\n"
            "## 伏笔与回收\n失效审计编号、月尘、纸质手稿、许岚拒绝备份、沈博士旧签名都会在终局回收。\n\n"
            "## 锁定约束遵守情况\n保留月球城市、失忆工程师、手稿预言和记忆审计规则。\n\n"
            "## 待用户确认的问题\n是否接受林澈在结局失去合法身份的黑暗代价？"
        )

    def _mock_outline_editor(self, revised: bool) -> str:
        if revised:
            return (
                "STATUS: pass\nQUALITY_SCORE: 86\n\n"
                "## 总体判断\n修订版主角罪感更强，第三幕代价明确，可以进入保存或章节细纲。\n\n"
                "## 主要问题\n中段盟友许岚的主动性还可以继续增强。\n\n"
                "## 修改建议\n章节细纲阶段为许岚增加一次反向选择。\n\n"
                "## 锁定约束检查\n未破坏月球城市和记忆规则。\n\n"
                "## 风格匹配度\n悬疑和黑暗感匹配。\n\n"
                "## 下一步建议\n保存当前大纲，进入章节细纲。"
            )
        return (
            "STATUS: revise\nQUALITY_SCORE: 74\n\n"
            "## 总体判断\n大纲成立，但主角罪感不足，第三幕代价偏轻。\n\n"
            "## 主要问题\n林澈与旧罪的关系不够直接；反派压力强于内心压力。\n\n"
            "## 修改建议\n让林澈曾亲手执行一次记忆删除，并让终局必须公开自证。\n\n"
            "## 锁定约束检查\n当前未违反锁定设定。\n\n"
            "## 风格匹配度\n悬疑足够，黑暗感不足。\n\n"
            "## 下一步建议\n按编辑意见修订大纲。"
        )

    def _mock_version_comparison(self) -> str:
        return (
            "# 大纲版本比较\n\n"
            "## 核心变化\n- 新版把主角从被动追查者改为旧罪承担者。\n\n"
            "## 人物变化\n- 林澈的罪感和自我牺牲更强。\n\n"
            "## 冲突变化\n- 冲突从外部阴谋升级为自我审判。\n\n"
            "## 风格变化\n- 新版更黑暗、更悬疑。\n\n"
            "## 风险变化\n- 需更早保留林澈善意，避免读者反感。\n\n"
            "## 是否建议采用新版\n- 建议采用新版，但保留 locked_constraints。"
        )

    def _mock_worldbuilding(self) -> str:
        return (
            "# 世界观设定\n\n"
            "## 世界背景\n月球城市银湾建在第谷环形山边缘，穹顶灯带模拟地球昼夜，地下三层保存着城市居民的授权记忆备份。城市表面繁荣，底层却存在被删除身份的灰籍居民。\n\n"
            "## 世界规则\n"
            "1. 任何记忆备份都必须留下审计编号。\n"
            "2. 私人创作不允许被公共预测系统索引。\n"
            "3. 穹顶事故会触发全城记忆锁定，期间无人能修改备份。\n"
            "4. 纸质文本无法被城市系统即时追踪，因此成为地下写作者联盟的通信媒介。\n"
            "5. 被删除的记忆不会消失，只会转存到月背冷库。\n\n"
            "## 冲突来源\n档案局维护秩序，记忆公司出售安全感，地下写作者联盟追求自我叙事权。主角林澈夹在三方之间。\n\n"
            "## 禁忌与代价\n私自读取月背冷库属于重罪；公开未审计记忆会让相关人员失去合法身份。\n\n"
            "## 人物压力\n林澈既想找回自己的过去，又害怕发现自己是篡改事件的执行者。\n\n"
            "## 可持续写作素材\n穹顶维修站、月背冷库、纸质手稿、失效审计编号、灰籍集市、记忆公司听证会。\n\n"
            "## 自检\n规则能制造案件，禁忌能制造代价，地下素材能支撑连续追查。"
        )

    def _mock_outline_plan(self) -> str:
        return (
            "# 总大纲\n\n"
            "## 核心卖点\n失忆工程师发现自己的小说正在预告月球城市事故，而每一章都指向他被删除的过去。\n\n"
            "## 主线目标\n外在目标是找回手稿来源并阻止穹顶事故；内在需求是承认自己曾参与记忆篡改，并重新选择站在哪一边。\n\n"
            "## 人物弧光\n林澈从逃避责任到主动公开真相；盟友许岚从只求自保到帮助灰籍居民发声；对手沈博士从秩序维护者暴露为记忆垄断者。\n\n"
            "## 三幕结构\n1. 手稿出现：林澈发现事故预告，第一次追查失败。\n2. 真相逼近：他进入地下写作者联盟，确认手稿来自月背冷库。\n3. 公开选择：他用自己的审计编号证明系统造假，释放被锁定的记忆。\n\n"
            "## 章节钩子策略\n开篇用纸质手稿制造异常；中段用穹顶裂缝升级威胁；结尾让手稿最后一章署名为林澈本人。\n\n"
            "## 伏笔与回收\n"
            "1. 失效审计编号：第 1 章出现，第 8 章证明身份删除。\n"
            "2. 穹顶灯带闪烁：第 1 章异常，第 6 章回收为事故预兆。\n"
            "3. 纸质手稿边角月尘：第 2 章出现，第 7 章指向月背冷库。\n"
            "4. 许岚拒绝备份：第 3 章出现，第 9 章解释她是灰籍后代。\n"
            "5. 沈博士的旧签名：第 4 章出现，终章回收为篡改授权。\n\n"
            "## 风险自检\n需要控制设定解释密度，保持林澈主动行动，并让每次真相揭露带来现实代价。"
        )

    def _mock_chapter_goal_report(self) -> str:
        return (
            "## 章节目标报告\n"
            "- 外在目标：林澈确认纸质手稿预告是否真实，并查清自己审计编号失效的原因。\n"
            "- 内在目标：从自保和上报冲动，转向主动怀疑自己的过去。\n"
            "- 信息增量：手稿、失效审计编号、东七气闸事故倒计时同时出现。\n"
        )

    def _mock_chapter_conflict_report(self) -> str:
        return (
            "## 冲突报告\n"
            "- 主要冲突：公共上报规则与私自追查冲动对撞。\n"
            "- 外部阻碍：档案局扫描规则、维修站倒计时、身份待确认提示。\n"
            "- 连续性风险：不能提前说明林澈曾参与记忆删除，月背冷库只保留传闻。\n"
        )

    def _mock_chapter_hook_report(self) -> str:
        return (
            "## 钩子报告\n"
            "- 开场钩子：林澈在维修站醒来，工具箱里只有纸质手稿。\n"
            "- 中段转折：审计编号查询失败，待确认人员指向林澈。\n"
            "- 结尾钩子：手稿第二页写出十分钟后的事故坐标。\n"
        )

    def _mock_chapter_card(self) -> str:
        return (
            "# 第 1 章章节卡：空白手稿\n\n"
            "## 章节目标\n让林澈发现纸质手稿、失效审计编号和即将发生的东七气闸事故，完成从自保到主动追查的转向。\n\n"
            "## 场景列表\n"
            "1. 维修站醒来：林澈发现工具箱里的纸质手稿。\n"
            "2. 审计编号查询：终端提示编号不存在，相关人员身份待确认。\n"
            "3. 气闸倒计时：东七气闸压力曲线开始下坠，验证手稿预告。\n"
            "4. 冲出维修站：林澈带着手稿赶往事故坐标。\n\n"
            "## 关键冲突\n林澈必须在立刻上报未登记文本和私自追查身份异常之间选择；城市规则要求透明，而纸质手稿逼他隐藏。\n\n"
            "## 人物变化\n林澈从相信系统记录、优先自保，转向怀疑自己的身份和过去，并愿意承担违规追查的风险。\n\n"
            "## 结尾钩子\n手稿第二页写出十分钟后的东七气闸事故坐标，现实警报与纸面预言同步发生。\n\n"
            "## 连续性约束\n不能提前揭露林澈曾参与关键记忆删除；月背冷库只作为月尘和传闻出现；许岚暂不正式登场。\n\n"
            "## 本章写作输入\n按醒来、发现手稿、查询失败、事故倒计时四段推进；情绪从困惑到恐惧，再到主动行动；设定信息必须通过操作和警报呈现。\n\n"
            "## 自检\n章节完成异常发现、规则展示、身份疑问和行动钩子，能直接拆成场景卡。"
        )

    def _mock_scene_breakdown_report(self) -> str:
        return (
            "## 场景拆分报告\n"
            "- 场景 1：维修站醒来，建立异常物和纸质文本禁忌。\n"
            "- 场景 2：审计编号查询失败，把异常转为身份危机。\n"
            "- 场景 3：气闸警报验证预言，推动主角违规行动。\n"
        )

    def _mock_scene_conflict_report(self) -> str:
        return (
            "## 冲突检查报告\n"
            "- 三个场景分别承担物证异常、身份异常和公共事故，冲突不重复。\n"
            "- 不提前揭露月背冷库真相，只保留月尘线索。\n"
        )

    def _mock_scene_cards(self) -> str:
        return (
            "# 第 1 章场景卡\n\n"
            "## 场景 1：维修站醒来\n"
            "- 地点：银湾城第三维修站。\n"
            "- 出场人物：林澈。\n"
            "- 场景目的：建立主角失忆醒来和纸质手稿异常。\n"
            "- 人物目标：确认自己为什么躺在维修站地板上。\n"
            "- 冲突对象：空白记忆、值班系统和未登记纸质文本。\n"
            "- 关键信息：手稿第一页写着林澈的名字，纸质文本不能被系统即时追踪。\n"
            "- 情绪变化：茫然 -> 警觉。\n"
            "- 场景转折：工具箱里没有工具，只有纸质手稿。\n"
            "- 退出状态：林澈决定翻阅手稿并查询夹页编号。\n\n"
            "## 场景 2：审计编号查询\n"
            "- 地点：维修站终端台。\n"
            "- 出场人物：林澈，值班系统语音。\n"
            "- 场景目的：把物件异常升级成身份危机。\n"
            "- 人物目标：用审计编号证明手稿来源。\n"
            "- 冲突对象：档案局系统和失效编号。\n"
            "- 关键信息：终端返回编号不存在，相关人员身份待确认，待确认人员是林澈。\n"
            "- 情绪变化：警觉 -> 恐惧。\n"
            "- 场景转折：身份异常指向主角本人。\n"
            "- 退出状态：林澈暂时放弃上报，准备核对手稿预言。\n\n"
            "## 场景 3：气闸倒计时\n"
            "- 地点：第三维修站通道和东七气闸方向。\n"
            "- 出场人物：林澈，远处维修队。\n"
            "- 场景目的：验证预言有效并迫使主角行动。\n"
            "- 人物目标：赶到事故坐标阻止误操作。\n"
            "- 冲突对象：倒计时、城市上报规则和即将泄压的气闸。\n"
            "- 关键信息：手稿第二页的压力折线与现实警报一致。\n"
            "- 情绪变化：恐惧 -> 决断。\n"
            "- 场景转折：东七气闸压力曲线开始下坠。\n"
            "- 退出状态：林澈带着手稿冲向东七气闸，进入下一章事故验证。"
        )



    def _mock_chapter_summary(self) -> str:
        return "林澈在银湾城第三维修站醒来，发现纸质手稿预告东七气闸事故，并确认审计编号失效指向自己。修订稿补强了纸质文本禁忌、身份异常和事故倒计时，章末他带着手稿冲向东七气闸，决定违规追查。"

    def _mock_final_bible_updates(self) -> str:
        data = {
            "chapter_summaries": {
                "1": "林澈在银湾城第三维修站醒来，发现纸质手稿预告东七气闸事故，并确认审计编号失效指向自己。他带着手稿冲向东七气闸，决定违规追查。"
            },
            "timeline": [
                {"id": "chapter-001-final", "order": 1, "chapter": 1, "event": "林澈发现纸质手稿、失效审计编号和东七气闸事故预告。", "characters": ["林澈"], "location": "银湾城第三维修站", "source_hint": "final_chapter: 第1章定稿"}
            ],
            "foreshadowing": [
                {"id": "CH001-HOOK", "setup_chapter": 1, "setup_text": "手稿第二页预告东七气闸事故坐标。", "payoff_text": "后续验证手稿来源和月背冷库线索。", "status": "setup", "source_hint": "final_chapter: 手稿第二页预告"}
            ],
            "plot_threads": [
                {"name": "手稿预言", "description": "第一章确认手稿能预告真实事故。", "status": "active", "related_chapters": [1], "source_hint": "chapter_summary: 第1章摘要"}
            ],
            "open_questions": ["手稿为何能预告东七气闸事故仍待解释。"],
        }
        return json.dumps(data, ensure_ascii=False)

    def _mock_review_role(self, role: str, revised: bool) -> str:
        if revised:
            return f"## {role}审稿\n- 通过点：修订稿已经补足关键细节。\n- 风险：后续章节继续铺垫许岚即可。"
        return f"## {role}审稿\n- 问题：初稿需要补强维修站异常记录、纸质文本禁忌和事故倒计时。\n- 建议：进入定向修订。"

    def _mock_review_synthesizer(self, revised: bool) -> str:
        if revised:
            data = {
                "decision": "pass",
                "score": 88,
                "blocking_issues": [],
                "issues": ["后续章节继续补强许岚登场铺垫。"],
                "rewrite_tasks": [],
            }
        else:
            data = {
                "decision": "revise",
                "score": 72,
                "blocking_issues": ["场景压力和规则展示不足。"],
                "issues": ["主角醒来的环境压力不足。", "纸质手稿为什么危险还不够清楚。", "事故倒计时可以更强。"],
                "rewrite_tasks": ["增加审计编号查询失败。", "补明纸质文本禁忌。", "强化东七气闸倒计时。"],
            }
        return json.dumps(data, ensure_ascii=False)

    def _mock_revision_plan(self) -> str:
        data = {
            "revision_plan_v1": {
                "tasks": [
                    {"task": "补强维修站异常记录。", "target_scene": "醒来场景", "source": "review_v1.json.rewrite_tasks: 增加审计编号查询失败。"},
                    {"task": "补明纸质文本禁忌。", "target_scene": "手稿场景", "source": "review_v1.json.rewrite_tasks: 补明纸质文本禁忌。"},
                    {"task": "强化东七气闸倒计时。", "target_scene": "结尾场景", "source": "review_v1.json.rewrite_tasks: 强化东七气闸倒计时。"},
                ],
                "keep": ["不提前揭露月背冷库真相。"],
                "do_not_touch": ["不改变既有章节顺序。"],
                "open_questions": [],
            }
        }
        return json.dumps(data, ensure_ascii=False)

    def _mock_chapter_plan(self) -> str:
        return (
            "# 章节细纲\n\n"
            "## 章节总览\n前三章完成异常发现、现实验证和追查入口。\n\n"
            "## 第 1 章：空白手稿\n目标：让林澈发现纸质手稿和失效审计编号。\n场景列表：维修站醒来；穹顶灯带异常；手稿预告小型气闸事故；林澈试图查询审计编号失败。\n关键冲突：他必须在上报异常和私自追查之间选择。\n人物变化：从自保转向怀疑自己的过去。\n结尾钩子：手稿第二页写着十分钟后的事故坐标。\n\n"
            "## 第 2 章：穹顶裂缝\n目标：验证手稿预告真实有效。\n场景列表：赶往气闸；阻止维修队误操作；发现月尘痕迹；被档案局带走问询。\n关键冲突：公共安全与私人秘密冲突。\n结尾钩子：档案局系统显示林澈当天没有上班记录。\n\n"
            "## 第 3 章：备份人\n目标：引出地下写作者联盟。\n场景列表：许岚递交纸条；灰籍集市交易；冷库传闻；第一次追踪失败。\n结尾钩子：手稿第三章出现许岚死亡时间。\n\n"
            "## 连续性约束\n不能提前解释林澈参与篡改的全部真相；月背冷库只作为传闻出现。\n\n"
            "## 本章写作输入\n第 1 章按醒来、发现手稿、验证编号、事故倒计时四段推进，情绪从困惑到恐惧再到主动行动。\n\n"
            "## 自检\n每章都扩大风险范围：个人异常、公共事故、组织追杀。"
        )

    def _mock_chapter(self, revised: bool) -> str:
        revision_line = "修订版补强了维修站异常记录和月球城市规则。" if revised else "初稿保留部分信息空白，等待编辑审查。"
        return (
            "# 第 1 章：空白手稿\n\n"
            "月球城的清晨没有阳光。穹顶灯带从灰蓝一点点过渡到苍白，像有人把一块旧屏幕擦亮。林澈在第三维修站的地板上醒来，后颈贴着冰冷的金属格栅，耳边是循环播放的值班提示。\n\n"
            "提示说，昨夜没有事故。可他面前的工具箱被人打开，里面没有扳手，只有一本纸质手稿。纸在银湾城是奢侈品，也是系统最讨厌的东西，因为它不会自动留下审计编号。\n\n"
            "林澈翻开第一页，看见自己的名字。第二页写着：‘六点四十分，东七气闸会出现一次被记录为误操作的泄压。维修员林澈将在事故前十分钟醒来。’\n\n"
            "他抬头看向墙上的时间。六点三十。\n\n"
            "理智告诉他应该立刻上报。城市档案局规定，任何未登记文本都必须交由系统扫描。但手稿边角沾着一层极细的灰白月尘，像从没有人获准进入的月背冷库带出来。林澈试着查询手稿夹页上的审计编号，终端只返回一行红字：编号不存在，相关人员身份待确认。\n\n"
            "更糟的是，待确认的人是他。\n\n"
            "维修站外传来短促警报。东七气闸的压力曲线开始下坠，和手稿上画出的折线一模一样。林澈抓起手稿冲向通道，灯带在他头顶闪烁，像整座城市正在眨眼，假装没有看见他。\n\n"
            "他忽然明白，这不是一份小说草稿。至少，不只是。有人用他最熟悉也最危险的方式，把未来十分钟塞进了纸里。\n\n"
            f"## 本章推进\n{revision_line}主角发现手稿、失效审计编号和即将发生的气闸事故。\n\n"
            "## 连续性备注\n本章使用了纸质文本不可追踪、审计编号、穹顶维修站和月背冷库传闻四个世界规则。"
        )

    def _mock_editor_review(self, revised: bool) -> str:
        if revised:
            return (
                "STATUS: pass\nQUALITY_SCORE: 88\n\n"
                "# 编辑审稿意见\n\n"
                "## 总体判断\n修订稿已经把异常记录、城市规则和事故倒计时连接起来，可以进入人工审核。\n\n"
                "## 主要问题\n仍可在后续章节补强许岚的登场铺垫，但不影响本章保存。\n\n"
                "## 修改建议\n下一章继续放大公共事故代价，并让档案局第一次施压。\n\n"
                "## 连续性风险\n月背冷库仍保持传闻状态，没有提前泄露核心真相。\n\n"
                "## 通过条件\n本章满足目标、冲突、信息增量和结尾钩子要求。"
            )
        return (
            "STATUS: revise\nQUALITY_SCORE: 72\n\n"
            "# 编辑审稿意见\n\n"
            "## 总体判断\n章节钩子成立，但需要补强维修站异常记录和月球城市规则，否则世界观没有真正进入场景。\n\n"
            "## 主要问题\n主角醒来的环境压力不足；纸质手稿为什么危险还不够清楚；事故倒计时可以更强。\n\n"
            "## 修改建议\n增加审计编号查询失败、纸质文本禁忌、东七气闸倒计时三处细节。\n\n"
            "## 连续性风险\n不要提前解释月背冷库真相，只保留月尘线索。\n\n"
            "## 通过条件\n修订后需要让本章同时完成异常发现、规则展示和行动钩子。"
        )

    def _mock_outline(self, prompt: str) -> str:
        idea = prompt.strip().splitlines()[-1] if prompt.strip() else "未命名创意"
        return (
            "# 小说大纲\n\n"
            f"## 核心创意\n{idea}\n\n"
            "## 主角\n一位目标明确但内心矛盾的创作者型人物。\n\n"
            "## 三幕结构\n"
            "1. 开端：主角遇到打破日常秩序的事件。\n"
            "2. 对抗：主角追查真相，并付出关系和信念上的代价。\n"
            "3. 结局：主角完成选择，承担新秩序的后果。\n\n"
            "## 下一步\n将三幕结构扩展为章节细纲。"
        )
