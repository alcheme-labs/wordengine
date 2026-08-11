from __future__ import annotations


VIEWER_LEGACY_STATIC_READOUT_SLOTS_SCHEMA = "viewer-legacy-static-readout-slots-v1"
VIEWER_LEGACY_STATIC_READOUT_SOURCE_PATH = "world_engine/viewer_legacy_static_readout_slots.py"


def viewer_legacy_static_readout_slots_before_route_reentry_html() -> str:
    return _BEFORE_ROUTE_REENTRY_STATIC_READOUT_SLOTS_HTML


def viewer_legacy_static_readout_slots_after_route_reentry_html() -> str:
    return _AFTER_ROUTE_REENTRY_STATIC_READOUT_SLOTS_HTML


_BEFORE_ROUTE_REENTRY_STATIC_READOUT_SLOTS_HTML = """<!-- viewer-legacy-static-readout-slots-v1:before-route-reentry -->
          <dt>Current-scope review</dt><dd id="current-scope-completion-review-readout">unavailable</dd>
          <dt>Next world-experience selection</dt><dd id="next-world-experience-selection-readout">unavailable</dd>
          <dt>Runtime/replay/browser</dt><dd id="runtime-replay-browser-consistency-readout">unavailable</dd>
          <dt>Post-consistency selection</dt><dd id="post-consistency-gap-audit-readout">unavailable</dd>
          <dt>Agent-feedback playability</dt><dd id="agent-feedback-playability-readout">unavailable</dd>
          <dt>Agent-feedback comprehension</dt><dd id="agent-feedback-comprehension-readout">unavailable</dd>
          <dt>Post-agent feedback selection</dt><dd id="post-agent-feedback-comprehension-gap-audit-readout">unavailable</dd>
          <dt>Agent-feedback guided loop</dt><dd id="agent-feedback-guided-action-loop-readout">unavailable</dd>
          <dt>Agent-feedback memory continuity</dt><dd id="agent-feedback-memory-continuity-readout">unavailable</dd>
          <dt>Agent-feedback memory-guided session</dt><dd id="agent-feedback-memory-guided-session-readout">unavailable</dd>
          <dt>Memory-guided next capability</dt><dd id="memory-guided-playable-session-gap-audit-readout">unavailable</dd>
          <dt>Memory-guided open world</dt><dd id="memory-guided-open-world-action-loop-readout">unavailable</dd>
          <dt>Post-memory-guided selection</dt><dd id="post-memory-guided-open-world-gap-audit-readout">unavailable</dd>
          <dt>Memory-guided comprehension</dt><dd id="memory-guided-open-world-comprehension-readout">unavailable</dd>
          <dt>Post-comprehension selection</dt><dd id="post-memory-guided-open-world-comprehension-gap-audit-readout">unavailable</dd>
          <dt>Multi-region continuity</dt><dd id="multi-region-memory-guided-open-world-continuity-readout">unavailable</dd>
          <dt>Longer session duration</dt><dd id="longer-memory-guided-open-world-session-duration-readout">unavailable</dd>
          <dt>Post-longer selection</dt><dd id="post-longer-session-duration-gap-audit-readout">unavailable</dd>
          <dt>Longer content/consequence</dt><dd id="longer-session-content-consequence-readout">unavailable</dd>
          <dt>Smooth observation transition</dt><dd id="smooth-observation-transition-readout">unavailable</dd>
          <dt>Richer observation content</dt><dd id="richer-observation-content-readout">unavailable</dd>
          <dt>Post-richer selection</dt><dd id="post-richer-observation-content-gap-audit-readout">unavailable</dd>
          <dt>Rich-guided action</dt><dd id="rich-observation-guided-action-session-readout">unavailable</dd>
          <dt>Post-rich guided selection</dt><dd id="post-rich-observation-guided-action-gap-audit-readout">unavailable</dd>
          <dt>Long rich-guided continuity</dt><dd id="long-rich-observation-guided-action-session-continuity-readout">unavailable</dd>
          <dt>Large-scale stress/budget</dt><dd id="large-scale-runtime-stress-budget-readout">unavailable</dd>
          <dt>Large-scale multi-region/session stress</dt><dd id="large-scale-multi-region-multi-session-stress-budget-readout">unavailable</dd>
          <dt>Post multi-region/session stress selection</dt><dd id="post-large-scale-multi-region-multi-session-stress-budget-gap-audit-readout">unavailable</dd>
          <dt>Stress-budget resilient playable meaning</dt><dd id="stress-budget-resilient-multi-region-multi-session-playable-meaning-readout">unavailable</dd>
          <dt>Post stress-budget meaning selection</dt><dd id="post-stress-budget-resilient-playable-meaning-gap-audit-readout">unavailable</dd>
          <dt>Stress-budget user-facing session</dt><dd id="stress-budget-user-facing-session-experience-readout">unavailable</dd>
          <dt>Post stress-budget user-facing selection</dt><dd id="post-stress-budget-user-facing-session-gap-audit-readout">unavailable</dd>
          <dt>Larger user-facing generalization</dt><dd id="larger-scale-user-facing-session-generalization-readout">unavailable</dd>
          <dt>Post larger-scale user-facing selection</dt><dd id="post-larger-scale-user-facing-session-generalization-gap-audit-readout">unavailable</dd>
          <dt>Larger user-facing continuity retention</dt><dd id="larger-scale-user-facing-session-continuity-retention-readout">unavailable</dd>
          <dt>Post continuity-retention selection</dt><dd id="post-larger-scale-user-facing-session-continuity-retention-gap-audit-readout">unavailable</dd>
          <dt>Retained action feedback diversity</dt><dd id="larger-scale-retained-action-feedback-diversity-readout">unavailable</dd>
          <dt>Post retained diversity selection</dt><dd id="post-larger-scale-retained-action-consequence-feedback-diversity-gap-audit-readout">unavailable</dd>
          <dt>Longer retained diversity continuity</dt><dd id="longer-larger-scale-retained-action-consequence-feedback-diversity-continuity-readout">unavailable</dd>
          <dt>Post longer retained continuity selection</dt><dd id="post-longer-larger-scale-retained-action-consequence-feedback-diversity-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region retained continuity generalization</dt><dd id="multi-region-larger-scale-retained-diversity-continuity-generalization-readout">unavailable</dd>
          <dt>Post multi-region retained generalization selection</dt><dd id="post-multi-region-larger-scale-retained-diversity-continuity-generalization-gap-audit-readout">unavailable</dd>
          <dt>Cross-session retained transfer</dt><dd id="cross-session-larger-scale-retained-diversity-transfer-readout">unavailable</dd>
          <dt>Post cross-session retained transfer selection</dt><dd id="post-cross-session-larger-scale-retained-diversity-transfer-gap-audit-readout">unavailable</dd>
          <dt>Multi-session retained transfer retention</dt><dd id="multi-session-larger-scale-retained-transfer-retention-readout">unavailable</dd>
          <dt>Post multi-session retained transfer-retention selection</dt><dd id="post-multi-session-larger-scale-retained-transfer-retention-gap-audit-readout">unavailable</dd>
          <dt>Longer multi-session retained transfer-retention continuity</dt><dd id="longer-multi-session-larger-scale-retained-transfer-retention-continuity-readout">unavailable</dd>
          <dt>Post longer retained transfer-retention continuity selection</dt><dd id="post-longer-multi-session-larger-scale-retained-transfer-retention-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region multi-session retained continuity</dt><dd id="multi-region-multi-session-larger-scale-retained-transfer-retention-continuity-readout">unavailable</dd>
          <dt>Post multi-region multi-session retained continuity selection</dt><dd id="post-multi-region-multi-session-larger-scale-retained-transfer-retention-continuity-gap-audit-readout">unavailable</dd>
          <dt>Large-scale retained stress/budget</dt><dd id="large-scale-multi-region-multi-session-larger-scale-retained-stress-budget-readout">unavailable</dd>
          <dt>Post large-scale retained stress/budget selection</dt><dd id="post-large-scale-multi-region-multi-session-larger-scale-retained-stress-budget-gap-audit-readout">unavailable</dd>
          <dt>Larger-scale retained playable meaning</dt><dd id="stress-budget-resilient-multi-region-multi-session-larger-scale-retained-playable-meaning-readout">unavailable</dd>
          <dt>Post retained playable meaning selection</dt><dd id="post-stress-budget-resilient-larger-scale-retained-playable-meaning-gap-audit-readout">unavailable</dd>
          <dt>Retained user-facing session</dt><dd id="stress-budget-resilient-larger-scale-retained-user-facing-session-experience-readout">unavailable</dd>
          <dt>Field action feedback capability</dt><dd id="field-driven-user-facing-action-consequence-feedback-capability-readout">unavailable</dd>
          <dt>Field cross-session transfer</dt><dd id="field-driven-cross-session-user-facing-action-consequence-feedback-transfer-readout">unavailable</dd>
          <dt>Field multi-session retention</dt><dd id="field-driven-multi-session-user-facing-action-consequence-feedback-retention-readout">unavailable</dd>
          <dt>Field longer retention continuity</dt><dd id="field-driven-longer-multi-session-user-facing-action-consequence-feedback-retention-continuity-readout">unavailable</dd>
          <dt>Field multi-region longer continuity</dt><dd id="field-driven-multi-region-longer-multi-session-user-facing-action-consequence-feedback-retention-continuity-generalization-readout">unavailable</dd>
          <dt>Field large-scale stress/budget</dt><dd id="field-driven-large-scale-multi-region-longer-multi-session-user-facing-action-consequence-feedback-retention-continuity-generalization-stress-budget-readout">unavailable</dd>
          <dt>Field stress-budget session</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-user-facing-world-session-experience-readout">unavailable</dd>
          <dt>Field stress-budget branching</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-session-branching-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field branch-choice continuity</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-continuity-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity generalization</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-generalization-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity generalization transfer</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-generalization-transfer-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity generalization transfer retention</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-generalization-transfer-retention-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity generalization transfer retention continuity</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-generalization-transfer-retention-continuity-action-consequence-feedback-readout">unavailable</dd>
          <dt>Field adaptive followup continuity generalization transfer retention continuity generalization</dt><dd id="field-driven-stress-budget-resilient-large-scale-retained-branch-choice-adaptive-followup-continuity-generalization-transfer-retention-continuity-generalization-action-consequence-feedback-readout">unavailable</dd>
"""

_AFTER_ROUTE_REENTRY_STATIC_READOUT_SLOTS_HTML = """<!-- viewer-legacy-static-readout-slots-v1:after-route-reentry -->
	          <dt>Post-stress selection</dt><dd id="post-large-scale-runtime-stress-gap-audit-readout">unavailable</dd>
          <dt>Stress-resilient Agent/Feedback</dt><dd id="stress-resilient-agent-feedback-readout">unavailable</dd>
          <dt>Stress-resilient gap selection</dt><dd id="stress-resilient-agent-feedback-gap-audit-readout">unavailable</dd>
          <dt>Stress-resilient generalization</dt><dd id="stress-resilient-agent-feedback-generalization-readout">unavailable</dd>
          <dt>Post-generalization selection</dt><dd id="post-generalization-gap-audit-readout">unavailable</dd>
          <dt>Generalized playable meaning</dt><dd id="generalized-agent-feedback-playable-meaning-readout">unavailable</dd>
          <dt>Post-generalized meaning selection</dt><dd id="post-generalized-playable-meaning-gap-audit-readout">unavailable</dd>
          <dt>Live playable meaning fluency</dt><dd id="live-playable-meaning-session-fluency-readout">unavailable</dd>
          <dt>Post-live fluency selection</dt><dd id="post-live-playable-meaning-session-fluency-gap-audit-readout">unavailable</dd>
          <dt>Long-live meaning continuity</dt><dd id="long-live-playable-meaning-session-continuity-readout">unavailable</dd>
          <dt>Post-long-live selection</dt><dd id="post-long-live-playable-meaning-session-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region long-live meaning</dt><dd id="multi-region-long-live-playable-meaning-generalization-readout">unavailable</dd>
          <dt>Post multi-region long-live selection</dt><dd id="post-multi-region-long-live-playable-meaning-generalization-gap-audit-readout">unavailable</dd>
          <dt>Comprehension repair</dt><dd id="multi-region-long-live-playable-meaning-comprehension-repair-readout">unavailable</dd>
          <dt>Post-comprehension repair selection</dt><dd id="post-comprehension-repair-gap-audit-readout">unavailable</dd>
          <dt>Cross-session transfer</dt><dd id="cross-session-long-live-playable-meaning-transfer-readout">unavailable</dd>
          <dt>Post-cross-session transfer selection</dt><dd id="post-cross-session-transfer-gap-audit-readout">unavailable</dd>
          <dt>Multi-session retention</dt><dd id="multi-session-long-live-playable-meaning-retention-readout">unavailable</dd>
          <dt>Post-retention selection</dt><dd id="post-multi-session-retention-gap-audit-readout">unavailable</dd>
          <dt>Retention-guided action diversity</dt><dd id="retention-guided-action-diversity-readout">unavailable</dd>
          <dt>Post-action-diversity selection</dt><dd id="post-retention-guided-action-diversity-gap-audit-readout">unavailable</dd>
          <dt>Longer action-diversity continuity</dt><dd id="longer-retention-guided-action-diversity-continuity-readout">unavailable</dd>
          <dt>Post-longer action-diversity selection</dt><dd id="post-longer-retention-guided-action-diversity-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region action-diversity generalization</dt><dd id="multi-region-retention-guided-action-diversity-generalization-readout">unavailable</dd>
          <dt>Post-multi-region action-diversity selection</dt><dd id="post-multi-region-retention-guided-action-diversity-generalization-gap-audit-readout">unavailable</dd>
          <dt>Multi-region consequence feedback meaning</dt><dd id="multi-region-retention-guided-action-consequence-feedback-meaning-readout">unavailable</dd>
          <dt>Post-consequence meaning selection</dt><dd id="post-multi-region-consequence-feedback-meaning-gap-audit-readout">unavailable</dd>
          <dt>Longer consequence meaning continuity</dt><dd id="longer-multi-region-consequence-feedback-meaning-continuity-readout">unavailable</dd>
          <dt>Post-longer consequence meaning selection</dt><dd id="post-longer-multi-region-consequence-feedback-meaning-continuity-gap-audit-readout">unavailable</dd>
          <dt>Cross-session consequence transfer</dt><dd id="cross-session-consequence-feedback-meaning-transfer-readout">unavailable</dd>
          <dt>Post-consequence transfer selection</dt><dd id="post-cross-session-consequence-feedback-transfer-gap-audit-readout">unavailable</dd>
          <dt>Multi-session consequence retention</dt><dd id="multi-session-consequence-feedback-meaning-retention-readout">unavailable</dd>
          <dt>Post-consequence retention selection</dt><dd id="post-multi-session-consequence-feedback-meaning-retention-gap-audit-readout">unavailable</dd>
          <dt>Consequence retention guided action diversity</dt><dd id="consequence-feedback-retention-guided-action-diversity-readout">unavailable</dd>
          <dt>Post-consequence action diversity selection</dt><dd id="post-consequence-feedback-retention-guided-action-diversity-gap-audit-readout">unavailable</dd>
          <dt>Longer consequence action-diversity continuity</dt><dd id="longer-consequence-feedback-action-diversity-continuity-readout">unavailable</dd>
          <dt>Post-longer consequence action-diversity selection</dt><dd id="post-longer-consequence-feedback-action-diversity-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region consequence action-diversity generalization</dt><dd id="multi-region-consequence-feedback-action-diversity-generalization-readout">unavailable</dd>
          <dt>Post-multi-region consequence action-diversity selection</dt><dd id="post-multi-region-consequence-feedback-action-diversity-generalization-gap-audit-readout">unavailable</dd>
          <dt>Longer multi-region consequence action-diversity continuity</dt><dd id="longer-multi-region-consequence-feedback-action-diversity-generalization-continuity-readout">unavailable</dd>
          <dt>Post-longer multi-region consequence action-diversity selection</dt><dd id="post-longer-multi-region-generalized-continuity-gap-audit-readout">unavailable</dd>
          <dt>Cross-session generalized transfer</dt><dd id="cross-session-generalized-transfer-readout">unavailable</dd>
          <dt>Post-cross-session generalized transfer selection</dt><dd id="post-cross-session-generalized-transfer-gap-audit-readout">unavailable</dd>
          <dt>Multi-session generalized transfer retention</dt><dd id="multi-session-generalized-transfer-retention-readout">unavailable</dd>
          <dt>Post multi-session generalized transfer retention selection</dt><dd id="post-multi-session-generalized-transfer-retention-gap-audit-readout">unavailable</dd>
          <dt>Longer multi-session generalized transfer retention continuity</dt><dd id="longer-multi-session-generalized-transfer-retention-continuity-readout">unavailable</dd>
          <dt>Post-longer multi-session generalized transfer retention selection</dt><dd id="post-longer-multi-session-generalized-transfer-retention-continuity-gap-audit-readout">unavailable</dd>
          <dt>Multi-region multi-session generalized transfer retention continuity</dt><dd id="multi-region-multi-session-generalized-transfer-retention-continuity-readout">unavailable</dd>
          <dt>Post multi-region multi-session generalized transfer retention selection</dt><dd id="post-multi-region-multi-session-generalized-transfer-retention-continuity-gap-audit-readout">unavailable</dd>
"""
