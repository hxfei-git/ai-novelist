"""Post-generation similarity checks against used Author Craft sources."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ai_novelist.artifacts import save_json_artifact
from ai_novelist.corpus.index import load_chunks
from ai_novelist.corpus.models import RetrievalChunk
from ai_novelist.state import NovelState
from ai_novelist.storage.local_store import LocalStore


@dataclass(frozen=True)
class MatchedSource:
    chunk_id: str
    work_id: str
    score: float
    reason: str


@dataclass(frozen=True)
class SimilarityReport:
    project_id: str
    chapter: int
    artifact: str
    risk: str
    max_common_substring: int
    max_ngram_overlap: float
    matched_sources: list[MatchedSource] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["matched_sources"] = [asdict(item) for item in self.matched_sources]
        return data


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def char_ngrams(text: str, n: int = 8) -> set[str]:
    normalized = normalize_text(text)
    if len(normalized) < n:
        return {normalized} if normalized else set()
    return {normalized[index : index + n] for index in range(0, len(normalized) - n + 1)}


def longest_common_substring(a: str, b: str, max_scan_chars: int = 20000) -> int:
    a = normalize_text(a)[:max_scan_chars]
    b = normalize_text(b)[:max_scan_chars]
    if not a or not b:
        return 0
    previous = [0] * (len(b) + 1)
    best = 0
    for char_a in a:
        current = [0] * (len(b) + 1)
        for index, char_b in enumerate(b, start=1):
            if char_a == char_b:
                current[index] = previous[index - 1] + 1
                best = max(best, current[index])
        previous = current
    return best


def overlap_score(generated: str, source_chunk: str) -> float:
    generated_grams = char_ngrams(generated, 8)
    source_grams = char_ngrams(source_chunk, 8)
    if not generated_grams or not source_grams:
        return 0.0
    return len(generated_grams & source_grams) / max(1, min(len(generated_grams), len(source_grams)))


def check_similarity(
    generated: str,
    candidate_chunks: list[RetrievalChunk],
    artifact: str = "draft",
    project_id: str = "",
    chapter: int = 1,
    max_common_threshold: int = 120,
    ngram_threshold: float = 0.22,
) -> SimilarityReport:
    max_common = 0
    max_overlap = 0.0
    matches: list[MatchedSource] = []
    for chunk in candidate_chunks:
        common = longest_common_substring(generated, chunk.text)
        overlap = overlap_score(generated, chunk.text)
        max_common = max(max_common, common)
        max_overlap = max(max_overlap, overlap)
        if common > max_common_threshold or overlap > ngram_threshold:
            matches.append(
                MatchedSource(
                    chunk_id=chunk.chunk_id,
                    work_id=chunk.work_id,
                    score=max(overlap, common / max_common_threshold),
                    reason=f"common={common}, overlap={overlap:.3f}",
                )
            )
    risk = "low"
    if max_common > max_common_threshold or max_overlap > ngram_threshold:
        risk = "high"
    elif max_common > max_common_threshold * 0.6 or max_overlap > ngram_threshold * 0.65:
        risk = "medium"
    recommendations = []
    if risk != "low":
        recommendations.append("重写相似段落，保留结构方法但替换人物行动、信息释放和表达。")
        recommendations.append("不要复用本地语料中的连续句式或桥段。")
    return SimilarityReport(project_id, chapter, artifact, risk, max_common, max_overlap, matches[:10], recommendations)


def save_similarity_report_for_state(state: NovelState, store: LocalStore, artifact: str, generated: str) -> NovelState:
    if state.craft_mode not in {"assist", "strict"}:
        return state
    index_dir = Path(str((state.craft_options or {}).get("corpus_index_dir") or "corpus_index")).expanduser()
    if not index_dir.exists():
        return state
    candidate_chunks = select_candidate_chunks(state, index_dir)
    if not candidate_chunks:
        return state
    report = check_similarity(
        generated,
        candidate_chunks,
        artifact=artifact,
        project_id=state.project_id,
        chapter=state.active_chapter or state.current_chapter,
    )
    relative_path = store.craft_similarity_report_relative_path(state.active_chapter or state.current_chapter, artifact)
    record = save_json_artifact(
        store.project_dir(state.project_id),
        relative_path,
        report.to_dict(),
        "craft_similarity_report",
        chapter=state.active_chapter or state.current_chapter,
        stage=artifact,
        source_agent="similarity_guard",
        graph=state.active_graph,
        summary=f"risk={report.risk}",
    )
    state.director_task_args["craft_similarity_report"] = report.to_dict()
    state.director_task_args["craft_similarity_report_path"] = record.path
    if state.craft_mode == "strict" and report.risk == "high":
        state.review_status = "revision_requested"
        state.next_action = "rewrite_chapter"
    return state


def select_candidate_chunks(state: NovelState, index_dir: Path) -> list[RetrievalChunk]:
    wanted = {str(item.get("chunk_id") or item.get("source_id")) for item in state.craft_sources if isinstance(item, dict)}
    sources_path = state.director_task_args.get("stage_craft_sources_path")
    if sources_path:
        path = Path(store_path_hint(state, sources_path))
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for item in data.get("source_evidence", []):
                    if isinstance(item, dict):
                        wanted.add(str(item.get("chunk_id") or item.get("source_id")))
            except json.JSONDecodeError:
                pass
    chunks = list(load_chunks(index_dir))
    if wanted:
        selected = [chunk for chunk in chunks if chunk.chunk_id in wanted]
        if selected:
            return selected[:30]
    return chunks[:30]


def store_path_hint(state: NovelState, relative_or_absolute: str) -> str:
    path = Path(relative_or_absolute)
    if path.is_absolute():
        return str(path)
    return str(Path("projects") / state.project_id / path)
