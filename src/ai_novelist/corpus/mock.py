"""Deterministic mock craft extraction rules."""

from __future__ import annotations

from collections import defaultdict

from ai_novelist.corpus.craft_schema import CraftEvidence, CraftNote, CraftProfile
from ai_novelist.corpus.models import CorpusWork, RetrievalChunk


def build_mock_profiles(works: list[CorpusWork], chunks: list[RetrievalChunk]) -> tuple[list[CraftProfile], list[CraftProfile], list[CraftProfile], list[CraftProfile]]:
    work_profiles = [mock_work_profile(work, [chunk for chunk in chunks if chunk.work_id == work.work_id]) for work in works]
    chapter_profiles = [mock_chapter_profile(key, grouped) for key, grouped in group_chunks(chunks, "chapter_id").items()]
    scene_profiles = [mock_scene_profile(key, grouped) for key, grouped in group_chunks(chunks, "scene_id").items()]
    genre_profiles = mock_genre_profiles(works, work_profiles)
    return work_profiles, chapter_profiles, scene_profiles, genre_profiles


def mock_work_profile(work: CorpusWork, chunks: list[RetrievalChunk]) -> CraftProfile:
    tags = sorted({tag for chunk in chunks for tag in chunk.tags})
    notes = [
        CraftNote(
            note_id=f"{work.work_id}_work_premise",
            scope="work",
            facet="premise",
            title="用核心异常组织整本书",
            pattern="先确立一个持续追问的异常事实，再让每个章节只推进一部分答案。",
            why_it_works="读者追的是问题链，不是设定说明。",
            use_when=["新项目需要清晰卖点", "开篇需要避免说明书式设定"],
            avoid_when=["用户已锁定慢热日常", "Pacing Target 要求完全收束"],
            pacing_functions=["setup", "mystery", "unknown"],
            intensity_range=(1, 4),
            evidence=[evidence_from_chunk(chunks[0])] if chunks else [],
            tags=["premise", *tags[:4]],
        ),
        CraftNote(
            note_id=f"{work.work_id}_work_pacing",
            scope="work",
            facet="pacing",
            title="用信息差控制章节节奏",
            pattern="每章只释放一个可行动信息，把解释延后到角色必须付出代价时。",
            why_it_works="行动压力能抵消解释负担，让节奏更稳。",
            use_when=["悬疑、科幻、仙侠等规则较多的题材"],
            avoid_when=["当前章是纯余波且不需要新信息"],
            pacing_functions=["setup", "escalation", "twist", "unknown"],
            intensity_range=(2, 5),
            evidence=[evidence_from_chunk(chunks[min(1, len(chunks) - 1)])] if chunks else [],
            tags=["information_release", "pacing"],
        ),
    ]
    return CraftProfile(
        profile_id=f"{work.work_id}_work",
        scope="work",
        work_id=work.work_id,
        title=work.title,
        author=work.author,
        genre=work.genre,
        notes=notes,
        metadata={"source_path": work.source_path, "extractor": "mock"},
    )


def mock_chapter_profile(chapter_id: str, chunks: list[RetrievalChunk]) -> CraftProfile:
    first = chunks[0]
    is_opening = first.chapter_index == 1
    facet = "chapter_hook" if any("turn" in chunk.tags or "reveal" in chunk.tags for chunk in chunks) else "pacing"
    title = "开篇异常事实" if is_opening else "章节推进压力"
    notes = [
        CraftNote(
            note_id=f"{chapter_id}_{facet}",
            scope="chapter",
            facet=facet,  # type: ignore[arg-type]
            title=title,
            pattern="以角色当下必须处理的压力进入章节，再逐步暴露背后的规则或关系。",
            why_it_works="压力让读者先关心行动，再接受设定和信息释放。",
            use_when=["章节需要建立目标", "章节不能写成背景说明"],
            avoid_when=["当前章节奏强度低于 2 时避免硬钩子"],
            pacing_functions=["setup", "escalation", "twist", "unknown"],
            intensity_range=(1 if is_opening else 2, 4),
            evidence=[evidence_from_chunk(first)],
            tags=sorted({tag for chunk in chunks for tag in chunk.tags})[:8],
        )
    ]
    if any("restraint" in chunk.tags for chunk in chunks):
        notes.append(
            CraftNote(
                note_id=f"{chapter_id}_restraint",
                scope="chapter",
                facet="restraint",
                title="用沉默和余波保留张力",
                pattern="让角色先处理情绪或代价，不急着抬高外部冲突。",
                why_it_works="低强度章节也能维持读者关注，不会把长篇节奏推爆。",
                use_when=["aftermath", "breather", "setup"],
                avoid_when=["高潮章需要明确对抗时"],
                pacing_functions=["aftermath", "breather", "setup", "unknown"],
                intensity_range=(1, 2),
                evidence=[evidence_from_chunk(first)],
                tags=["restraint", "pacing"],
            )
        )
    return CraftProfile(
        profile_id=f"{chapter_id}_profile",
        scope="chapter",
        work_id=first.work_id,
        title=f"{first.chapter_title} craft",
        notes=notes,
        metadata={"chapter_id": chapter_id, "chapter_index": first.chapter_index, "extractor": "mock"},
    )


def mock_scene_profile(scene_id: str, chunks: list[RetrievalChunk]) -> CraftProfile:
    first = chunks[0]
    facet = scene_facet(first)
    note = CraftNote(
        note_id=f"{scene_id}_{facet}",
        scope="scene",
        facet=facet,  # type: ignore[arg-type]
        title=scene_title(facet, first.position),
        pattern=scene_pattern(facet),
        why_it_works="场景每次只改变一个状态，读者更容易感到推进。",
        use_when=["需要让场景承担明确功能", "需要避免对白或氛围空转"],
        avoid_when=["当前项目已锁定不同场景目标时"],
        pacing_functions=scene_pacing_functions(facet),
        intensity_range=scene_intensity_range(facet),
        evidence=[evidence_from_chunk(first)],
        tags=sorted({tag for chunk in chunks for tag in chunk.tags})[:8],
    )
    return CraftProfile(
        profile_id=f"{scene_id}_profile",
        scope="scene",
        work_id=first.work_id,
        title=f"{first.chapter_title} scene craft",
        notes=[note],
        metadata={"chapter_id": first.chapter_id, "scene_id": scene_id, "position": first.position, "extractor": "mock"},
    )


def mock_genre_profiles(works: list[CorpusWork], work_profiles: list[CraftProfile]) -> list[CraftProfile]:
    by_genre: dict[str, list[CraftNote]] = defaultdict(list)
    for work, profile in zip(works, work_profiles, strict=False):
        for genre in work.genre:
            by_genre[genre].extend(profile.notes[:1])
    profiles: list[CraftProfile] = []
    for genre, notes in sorted(by_genre.items()):
        profiles.append(
            CraftProfile(
                profile_id=f"genre_{genre}",
                scope="genre",
                title=f"{genre} 类型构思方法",
                genre=[genre],
                notes=[
                    CraftNote(
                        note_id=f"genre_{genre}_pacing",
                        scope="genre",
                        facet="pacing",
                        title=f"{genre}类型的信息释放节奏",
                        pattern="把类型核心吸引力拆成多次小问题，避免一次性解释。",
                        why_it_works="类型承诺更稳定，章节负担更轻。",
                        use_when=[f"当前项目接近{genre}"],
                        avoid_when=["用户要求完全反类型"],
                        pacing_functions=["setup", "escalation", "unknown"],
                        intensity_range=(1, 4),
                        evidence=[item.evidence[0] for item in notes if item.evidence][:3],
                        tags=["genre", "pacing"],
                    )
                ],
                metadata={"extractor": "mock"},
            )
        )
    return profiles


def evidence_from_chunk(chunk: RetrievalChunk) -> CraftEvidence:
    return CraftEvidence(
        source_id=chunk.chunk_id,
        work_id=chunk.work_id,
        chapter_id=chunk.chapter_id,
        scene_id=chunk.scene_id,
        chunk_id=chunk.chunk_id,
        location_label=f"第 {chunk.chapter_index} 章 / {chunk.position}",
        summary=f"结构标签：{', '.join(chunk.tags[:6]) or '未标注'}；用于抽象构思方法，不保存原文。",
    )


def group_chunks(chunks: list[RetrievalChunk], attr: str) -> dict[str, list[RetrievalChunk]]:
    grouped: dict[str, list[RetrievalChunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[str(getattr(chunk, attr))].append(chunk)
    return dict(sorted(grouped.items()))


def scene_facet(chunk: RetrievalChunk) -> str:
    if "dialogue" in chunk.tags:
        return "dialogue"
    if "atmosphere" in chunk.tags:
        return "atmosphere"
    if "turn" in chunk.tags or chunk.position == "scene_ending":
        return "scene_turn"
    if "information_release" in chunk.tags:
        return "information_release"
    return "conflict"


def scene_title(facet: str, position: str) -> str:
    if facet == "scene_turn":
        return "用退出状态制造场景转折"
    if facet == "dialogue":
        return "让对白承担关系变化"
    if facet == "atmosphere":
        return "用氛围服务信息释放"
    if facet == "information_release":
        return "把线索做成可行动信息"
    return f"{position} 的目标阻碍结构"


def scene_pattern(facet: str) -> str:
    if facet == "dialogue":
        return "对白先暴露目标差异，再用一句未说出口的信息改变关系。"
    if facet == "atmosphere":
        return "氛围描写只服务角色判断和隐藏信息，不单独堆砌质感。"
    if facet == "information_release":
        return "线索不直接解释真相，而是改变角色下一步选择。"
    if facet == "scene_turn":
        return "场景结尾改变进入状态，让角色带着新限制离开。"
    return "给角色一个局部目标，再设置阻碍和有限结果。"


def scene_pacing_functions(facet: str) -> list[str]:
    if facet in {"atmosphere", "dialogue"}:
        return ["setup", "breather", "aftermath", "unknown"]
    if facet == "scene_turn":
        return ["escalation", "twist", "climax", "unknown"]
    return ["setup", "escalation", "unknown"]


def scene_intensity_range(facet: str) -> tuple[int, int]:
    if facet in {"atmosphere", "dialogue"}:
        return (1, 3)
    if facet == "scene_turn":
        return (2, 5)
    return (1, 4)
