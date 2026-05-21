"""Codex CLI adapter."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ai_novelist.adapters.base import AgentAdapter, AgentAdapterError


class CodexCLIError(AgentAdapterError):
    """Raised when Codex CLI cannot produce a usable response."""


@dataclass
class CodexCLIAdapter(AgentAdapter):
    codex_bin: str = "codex"
    timeout_seconds: int = 180
    mock: bool = False

    def complete(self, prompt: str, workspace: Path) -> str:
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
        if "AGENT: director" in prompt:
            return self._mock_director(prompt)
        if "AGENT: world_builder" in prompt:
            return self._mock_worldbuilding()
        if "AGENT: outline_planner" in prompt:
            return self._mock_outline_plan()
        if "AGENT: chapter_planner" in prompt:
            return self._mock_chapter_plan()
        if "AGENT: chapter_writer" in prompt:
            return self._mock_chapter(revised="修订次数：0" not in prompt)
        if "AGENT: editor" in prompt:
            return self._mock_editor_review(revised="修订次数：0" not in prompt)
        return self._mock_outline(prompt)


    def _mock_director(self, prompt: str) -> str:
        request = self._extract_director_request(prompt).lower()
        chapter = self._extract_chapter(request)
        if any(word in request for word in ("退出", "结束", "quit", "exit")):
            return "ACTION: stop\nMESSAGE: 已结束本次创作对话。\nCHAPTER:"
        if any(word in request for word in ("保存", "落盘", "写入文件")):
            return "ACTION: persist_outputs\nMESSAGE: 我会保存当前已经生成的世界观、大纲、细纲、章节和审稿意见。\nCHAPTER:"
        if any(word in request for word in ("状态", "进度", "show", "哪里", "在哪", "路径", "位置")):
            return "ACTION: show_status\nMESSAGE: 我会展示当前项目状态和已有产物。\nCHAPTER:"
        if any(word in request for word in ("世界观", "设定", "背景")):
            return "ACTION: worldbuild\nMESSAGE: 我会先调度世界观 Agent，建立可持续写作的规则、冲突和素材。\nCHAPTER:"
        if any(word in request for word in ("大纲", "主线", "罪感", "人物弧光")):
            return "ACTION: plan_outline\nMESSAGE: 我会调度大纲 Agent，强化主线、人物弧光和伏笔回收。\nCHAPTER:"
        if any(word in request for word in ("细纲", "章节规划", "章节计划")):
            return "ACTION: plan_chapters\nMESSAGE: 我会调度章节细纲 Agent，把大纲拆成可执行章节。\nCHAPTER:"
        if any(word in request for word in ("审稿", "编辑", "检查")):
            return f"ACTION: review\nMESSAGE: 我会调度编辑 Agent 检查当前章节。\nCHAPTER: {chapter or ''}"
        if any(word in request for word in ("重写", "修改章节", "改写", "修订")):
            return f"ACTION: revise_chapter\nMESSAGE: 我会根据编辑意见调度章节写手重写当前章节。\nCHAPTER: {chapter or ''}"
        if "写" in request and "章" in request:
            return f"ACTION: write_chapter\nMESSAGE: 我会调度章节写手生成第 {chapter or 1} 章。\nCHAPTER: {chapter or 1}"
        if any(word in request for word in ("想写", "创意", "小说", "故事")):
            return "ACTION: worldbuild\nMESSAGE: 我先把这个创意沉淀成世界观，再继续推进大纲和章节。\nCHAPTER:"
        return "ACTION: ask_user\nMESSAGE: 你想让我下一步做什么？可以说：设计世界观、写大纲、写第 1 章、让编辑审稿或保存当前结果。\nCHAPTER:"

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
