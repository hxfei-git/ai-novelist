from ai_novelist.corpus.craft_schema import CraftEvidence, CraftNote, CraftProfile


def test_craft_profile_round_trip():
    profile = CraftProfile(
        profile_id="p1",
        scope="chapter",
        work_id="w1",
        notes=[
            CraftNote(
                note_id="n1",
                scope="chapter",
                facet="pacing",
                title="节奏",
                pattern="只释放一个问题。",
                why_it_works="降低解释负担。",
                use_when=["setup"],
                avoid_when=["climax"],
                pacing_functions=["setup"],
                evidence=[CraftEvidence(source_id="c1", work_id="w1", summary="分析摘要")],
            )
        ],
    )

    loaded = CraftProfile.from_dict(profile.to_dict())

    assert loaded == profile


def test_evidence_truncates_long_quote():
    evidence = CraftEvidence.from_dict({"source_id": "c1", "work_id": "w1", "short_quote": "长" * 80})

    assert len(evidence.short_quote) <= 30
