from __future__ import annotations


VIEWER_LEGACY_POST_ROUTE_REENTRY_SUMMARY_JS_SCHEMA = "viewer_legacy_post_route_reentry_summary_js_v1"
VIEWER_LEGACY_POST_ROUTE_REENTRY_SUMMARY_SOURCE_PATH = "world_engine/viewer_legacy_post_route_reentry_summary_js.py"

_VIEWER_LEGACY_POST_ROUTE_REENTRY_SUMMARY_JS = r"""
    // viewer-legacy-post-route-reentry-summary-js-v1
    function postStressBudgetResilientPlayableMeaningGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_stress_budget_resilient_playable_meaning_gap_audit;
      if (
        !payload ||
        payload.schema !== "post_stress_budget_resilient_playable_meaning_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::stress-budget-resilient-user-facing-world-session-experience-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 170 ||
        Number(payload.score_margin || 0) < 35 ||
        Number(payload.source_record_count || payload.source_count || 0) < 139 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_record_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7 ||
        Number(payload.previous_score || 0) < 0.88 ||
        Number(payload.previous_baseline_advantage || 0) < 0.25 ||
        Number(payload.previous_stress_window_count || 0) < 8 ||
        Number(payload.previous_region_session_cell_count || 0) < 24 ||
        Number(payload.previous_covered_stress_tick_span || 0) < 2048 ||
        Number(payload.agent_feedback_carryover_score || 0) < 0.90 ||
        Number(payload.runtime_budget_score || 0) < 0.88 ||
        Number(payload.artifact_budget_score || 0) < 0.88
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postStressBudgetResilientPlayableMeaningGapAuditSummary(frame) {
      const payload = postStressBudgetResilientPlayableMeaningGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousScore: Number(payload.previous_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        stressWindowCount: Number(payload.previous_stress_window_count || 0),
        stressedCellCount: Number(payload.previous_region_session_cell_count || 0),
        coveredStressTickSpan: Number(payload.previous_covered_stress_tick_span || 0),
        agentFeedbackCarryoverScore: Number(payload.agent_feedback_carryover_score || 0),
        runtimeBudgetScore: Number(payload.runtime_budget_score || 0),
        artifactBudgetScore: Number(payload.artifact_budget_score || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function stressBudgetUserFacingSessionExperience(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.stress_budget_resilient_user_facing_world_session_experience;
      if (
        !payload ||
        payload.schema !== "stress_budget_resilient_user_facing_world_session_experience_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_capability_id || "").toLowerCase();
      if (selected !== "world-experience-next::stress-budget-resilient-user-facing-world-session-experience-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "viewer polish", "real-rendering", "real rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.stress_budget_user_facing_session_experience_score || 0) < 0.88 ||
        Number(payload.same_source_control_score || 0) > 0.63 ||
        Number(payload.baseline_advantage || 0) < 0.25 ||
        Number(payload.session_count || 0) < 4 ||
        Number(payload.session_step_count || 0) < 16 ||
        Number(payload.region_session_experience_count || 0) < 24 ||
        Number(payload.action_consequence_feedback_readability_count || 0) < 12 ||
        Number(payload.agent_feedback_session_coverage || 0) < 1.0 ||
        Number(payload.min_session_score || 0) < 0.84 ||
        Number(payload.min_region_session_experience_score || 0) < 0.80 ||
        Number(payload.previous_score || 0) < 0.88 ||
        Number(payload.previous_baseline_advantage || 0) < 0.25 ||
        Number(payload.previous_stress_window_count || 0) < 8 ||
        Number(payload.previous_region_session_cell_count || 0) < 24 ||
        Number(payload.previous_covered_stress_tick_span || 0) < 2048 ||
        Number(payload.runtime_budget_score || 0) < 0.88 ||
        Number(payload.artifact_budget_score || 0) < 0.88
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function stressBudgetUserFacingSessionExperienceSummary(frame) {
      const payload = stressBudgetUserFacingSessionExperience(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedCapabilityId: payload.selected_capability_id || "unknown",
        score: Number(payload.stress_budget_user_facing_session_experience_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        sessionCount: Number(payload.session_count || 0),
        sessionStepCount: Number(payload.session_step_count || 0),
        regionSessionExperienceCount: Number(payload.region_session_experience_count || 0),
        readabilityCount: Number(payload.action_consequence_feedback_readability_count || 0),
        agentFeedbackSessionCoverage: Number(payload.agent_feedback_session_coverage || 0),
        minSessionScore: Number(payload.min_session_score || 0),
        minRegionSessionExperienceScore: Number(payload.min_region_session_experience_score || 0),
        previousScore: Number(payload.previous_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousStressWindowCount: Number(payload.previous_stress_window_count || 0),
        previousRegionSessionCellCount: Number(payload.previous_region_session_cell_count || 0),
        previousStressTickSpan: Number(payload.previous_covered_stress_tick_span || 0),
        runtimeBudgetScore: Number(payload.runtime_budget_score || 0),
        artifactBudgetScore: Number(payload.artifact_budget_score || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function largerScaleUserFacingSessionGeneralization(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.larger_scale_user_facing_world_session_generalization;
      if (
        !payload ||
        payload.schema !== "larger_scale_user_facing_world_session_generalization_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_capability_id || "").toLowerCase();
      if (selected !== "world-experience-next::larger-scale-user-facing-world-session-generalization-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "viewer polish", "real-rendering", "real rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.larger_scale_user_facing_generalization_score || 0) < 0.90 ||
        Number(payload.same_source_control_score || 0) > 0.62 ||
        Number(payload.baseline_advantage || 0) < 0.28 ||
        Number(payload.larger_session_count || 0) < 6 ||
        Number(payload.larger_region_count || 0) < 8 ||
        Number(payload.larger_session_step_count || 0) < 36 ||
        Number(payload.larger_region_session_generalization_count || 0) < 48 ||
        Number(payload.larger_action_consequence_feedback_readability_count || 0) < 24 ||
        Number(payload.larger_agent_feedback_coverage_count || 0) < 6 ||
        Number(payload.same_source_control_count || 0) < 4 ||
        Number(payload.agent_feedback_session_coverage || 0) < 1.0 ||
        Number(payload.min_larger_session_score || 0) < 0.86 ||
        Number(payload.min_region_session_generalization_score || 0) < 0.84 ||
        Number(payload.previous_user_facing_session_score || 0) < 0.90 ||
        Number(payload.previous_min_session_score || 0) < 0.88 ||
        Number(payload.previous_min_region_session_experience_score || 0) < 0.90 ||
        Number(payload.previous_baseline_advantage || 0) < 0.30 ||
        Number(payload.previous_stress_window_count || 0) < 8 ||
        Number(payload.previous_region_session_cell_count || 0) < 24 ||
        Number(payload.previous_covered_stress_tick_span || 0) < 2048
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function largerScaleUserFacingSessionGeneralizationSummary(frame) {
      const payload = largerScaleUserFacingSessionGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedCapabilityId: payload.selected_capability_id || "unknown",
        score: Number(payload.larger_scale_user_facing_generalization_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        sessionCount: Number(payload.larger_session_count || 0),
        regionCount: Number(payload.larger_region_count || 0),
        sessionStepCount: Number(payload.larger_session_step_count || 0),
        regionSessionGeneralizationCount: Number(payload.larger_region_session_generalization_count || 0),
        readabilityCount: Number(payload.larger_action_consequence_feedback_readability_count || 0),
        agentFeedbackCoverageCount: Number(payload.larger_agent_feedback_coverage_count || 0),
        sameSourceControlCount: Number(payload.same_source_control_count || 0),
        agentFeedbackSessionCoverage: Number(payload.agent_feedback_session_coverage || 0),
        minSessionScore: Number(payload.min_larger_session_score || 0),
        minRegionSessionGeneralizationScore: Number(payload.min_region_session_generalization_score || 0),
        previousScore: Number(payload.previous_user_facing_session_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousStressWindowCount: Number(payload.previous_stress_window_count || 0),
        previousRegionSessionCellCount: Number(payload.previous_region_session_cell_count || 0),
        previousStressTickSpan: Number(payload.previous_covered_stress_tick_span || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLargerScaleUserFacingSessionGeneralizationGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_larger_scale_user_facing_session_generalization_gap_audit;
      if (
        !payload ||
        payload.schema !== "post_larger_scale_user_facing_session_generalization_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::larger-scale-user-facing-world-session-continuity-retention-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "viewer polish", "real-rendering", "real rendering", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const preserved = payload.preserved_larger_scale_metrics || {};
      if (
        Number(payload.selected_score || 0) < 210 ||
        Number(payload.score_margin || 0) < 50 ||
        Number(payload.source_record_count || payload.source_count || 0) < 195 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_record_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7 ||
        Number(preserved.larger_scale_user_facing_generalization_score || 0) < 0.94 ||
        Number(preserved.larger_session_count || 0) < 6 ||
        Number(preserved.larger_region_count || 0) < 8 ||
        Number(preserved.larger_region_session_generalization_count || 0) < 48 ||
        Number(preserved.larger_agent_feedback_coverage_count || 0) < 6 ||
        Number(preserved.baseline_advantage || 0) < 0.34 ||
        Number(preserved.agent_feedback_session_coverage || 0) < 1.0 ||
        Number(preserved.stress_budget_preservation || 0) < 1.0
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLargerScaleUserFacingSessionGeneralizationGapAuditSummary(frame) {
      const payload = postLargerScaleUserFacingSessionGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      const preserved = payload.preserved_larger_scale_metrics || {};
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        largerScaleScore: Number(preserved.larger_scale_user_facing_generalization_score || 0),
        largerSessionCount: Number(preserved.larger_session_count || 0),
        largerRegionCount: Number(preserved.larger_region_count || 0),
        regionSessionGeneralizationCount: Number(preserved.larger_region_session_generalization_count || 0),
        agentFeedbackCoverageCount: Number(preserved.larger_agent_feedback_coverage_count || 0),
        baselineAdvantage: Number(preserved.baseline_advantage || 0),
        agentFeedbackSessionCoverage: Number(preserved.agent_feedback_session_coverage || 0),
        stressBudgetPreservation: Number(preserved.stress_budget_preservation || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function largerScaleUserFacingSessionContinuityRetention(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.larger_scale_user_facing_world_session_continuity_retention;
      if (
        !payload ||
        payload.schema !== "larger_scale_user_facing_world_session_continuity_retention_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_capability_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::larger-scale-user-facing-world-session-continuity-retention-hardening"
      ) return {};
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-larger-scale-user-facing-session-continuity-retention-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "viewer polish", "real-rendering", "real rendering", "rendering", "physics"]) {
        if (selected.includes(term) || next.includes(term)) return {};
      }
      if (
        Number(payload.larger_scale_user_facing_generalization_score || 0) < 0.94 ||
        Number(payload.larger_scale_user_facing_continuity_retention_score || 0) < 0.94 ||
        Number(payload.min_retained_session_score || 0) < 0.91 ||
        Number(payload.min_region_session_retention_score || 0) < 0.90 ||
        Number(payload.same_source_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage || 0) < 0.36 ||
        Number(payload.agent_feedback_retention_coverage || 0) < 1.0 ||
        Number(payload.replay_browser_budget_preservation || 0) < 1.0 ||
        Number(payload.retained_session_count || 0) !== 8 ||
        Number(payload.retained_session_chain_count || 0) !== 8 ||
        Number(payload.retained_region_count || 0) !== 8 ||
        Number(payload.region_session_retention_count || 0) !== 64 ||
        Number(payload.action_consequence_feedback_retention_count || 0) !== 32 ||
        Number(payload.readable_feedback_retention_count || 0) !== 32 ||
        Number(payload.agent_feedback_retention_count || 0) !== 8 ||
        Number(payload.same_source_control_count || 0) !== 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function largerScaleUserFacingSessionContinuityRetentionSummary(frame) {
      const payload = largerScaleUserFacingSessionContinuityRetention(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedCapabilityId: payload.selected_capability_id || "unknown",
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        score: Number(payload.larger_scale_user_facing_continuity_retention_score || 0),
        largerScaleScore: Number(payload.larger_scale_user_facing_generalization_score || 0),
        minSessionScore: Number(payload.min_retained_session_score || 0),
        minRegionSessionScore: Number(payload.min_region_session_retention_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        retainedSessionCount: Number(payload.retained_session_count || 0),
        retainedSessionChainCount: Number(payload.retained_session_chain_count || 0),
        retainedRegionCount: Number(payload.retained_region_count || 0),
        regionSessionRetentionCount: Number(payload.region_session_retention_count || 0),
        actionConsequenceFeedbackRetentionCount: Number(payload.action_consequence_feedback_retention_count || 0),
        readableFeedbackRetentionCount: Number(payload.readable_feedback_retention_count || 0),
        agentFeedbackRetentionCount: Number(payload.agent_feedback_retention_count || 0),
        agentFeedbackRetentionCoverage: Number(payload.agent_feedback_retention_coverage || 0),
        replayBrowserBudgetPreservation: Number(payload.replay_browser_budget_preservation || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLargerScaleUserFacingSessionContinuityRetentionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_larger_scale_user_facing_session_continuity_retention_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_larger_scale_user_facing_session_continuity_retention_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::larger-scale-retained-user-facing-action-consequence-feedback-diversity-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 225 ||
        Number(payload.score_margin || 0) < 55 ||
        Number(payload.source_record_count || 0) < 223 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 9 ||
        Number(payload.blocked_candidate_count || 0) !== 8 ||
        Number(payload.larger_scale_user_facing_continuity_retention_score || 0) < 0.94 ||
        Number(payload.min_retained_session_score || 0) < 0.91 ||
        Number(payload.min_region_session_retention_score || 0) < 0.90 ||
        Number(payload.same_source_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage || 0) < 0.36 ||
        Number(payload.agent_feedback_retention_coverage || 0) < 1.0 ||
        Number(payload.larger_scale_user_facing_generalization_score || 0) < 0.94 ||
        Number(payload.readable_feedback_retention_count || 0) !== 32 ||
        Number(payload.action_consequence_feedback_retention_count || 0) !== 32
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLargerScaleUserFacingSessionContinuityRetentionGapAuditSummary(frame) {
      const payload = postLargerScaleUserFacingSessionContinuityRetentionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        continuityRetentionScore: Number(payload.larger_scale_user_facing_continuity_retention_score || 0),
        largerScaleGeneralizationScore: Number(payload.larger_scale_user_facing_generalization_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        agentFeedbackRetentionCoverage: Number(payload.agent_feedback_retention_coverage || 0),
        readableFeedbackRetentionCount: Number(payload.readable_feedback_retention_count || 0),
        actionConsequenceFeedbackRetentionCount: Number(payload.action_consequence_feedback_retention_count || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function largerScaleRetainedActionFeedbackDiversity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.larger_scale_retained_user_facing_action_consequence_feedback_diversity;
      if (
        !payload ||
        payload.schema !==
          "larger_scale_retained_user_facing_action_consequence_feedback_diversity_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-larger-scale-retained-action-consequence-feedback-diversity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.retained_action_consequence_feedback_diversity_score || 0) < 0.9 ||
        Number(payload.retained_action_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_consequence_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_feedback_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_action_category_count || 0) !== 6 ||
        Number(payload.retained_consequence_class_count || 0) !== 6 ||
        Number(payload.retained_feedback_mode_count || 0) !== 6 ||
        Number(payload.same_source_repeated_pattern_control_score || 1) > 0.55 ||
        Number(payload.baseline_advantage || 0) < 0.32
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function largerScaleRetainedActionFeedbackDiversitySummary(frame) {
      const payload = largerScaleRetainedActionFeedbackDiversity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        score: Number(payload.retained_action_consequence_feedback_diversity_score || 0),
        actionCount: Number(payload.retained_action_diversity_record_count || 0),
        consequenceCount: Number(payload.retained_consequence_diversity_record_count || 0),
        feedbackCount: Number(payload.retained_feedback_diversity_record_count || 0),
        categoryCount: Number(payload.retained_action_category_count || 0),
        classCount: Number(payload.retained_consequence_class_count || 0),
        modeCount: Number(payload.retained_feedback_mode_count || 0),
        controlScore: Number(payload.same_source_repeated_pattern_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLargerScaleRetainedActionConsequenceFeedbackDiversityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_larger_scale_retained_action_consequence_feedback_diversity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_larger_scale_retained_action_consequence_feedback_diversity_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::longer-larger-scale-retained-action-consequence-feedback-diversity-continuity-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 275 ||
        Number(payload.score_margin || 0) < 80 ||
        Number(payload.source_record_count || 0) < 37 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 9 ||
        Number(payload.blocked_candidate_count || 0) !== 8 ||
        Number(payload.retained_action_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_consequence_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_feedback_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_agent_feedback_diversity_carryover_count || 0) !== 8 ||
        Number(payload.retained_action_consequence_feedback_diversity_score || 0) < 0.9 ||
        Number(payload.same_source_repeated_pattern_control_score || 1) > 0.55 ||
        Number(payload.baseline_advantage || 0) < 0.32 ||
        Number(payload.larger_scale_user_facing_continuity_retention_score || 0) < 0.94 ||
        Number(payload.larger_scale_user_facing_generalization_score || 0) < 0.94 ||
        Number(payload.agent_feedback_retention_coverage || 0) < 1.0 ||
        Number(payload.action_consequence_feedback_retention_count || 0) !== 32 ||
        Number(payload.readable_feedback_retention_count || 0) !== 32 ||
        Number(payload.region_session_retention_count || 0) !== 64
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLargerScaleRetainedActionConsequenceFeedbackDiversityGapAuditSummary(frame) {
      const payload = postLargerScaleRetainedActionConsequenceFeedbackDiversityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        retainedDiversityScore: Number(payload.retained_action_consequence_feedback_diversity_score || 0),
        actionCount: Number(payload.retained_action_diversity_record_count || 0),
        consequenceCount: Number(payload.retained_consequence_diversity_record_count || 0),
        feedbackCount: Number(payload.retained_feedback_diversity_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.retained_agent_feedback_diversity_carryover_count || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_repeated_pattern_control_score || 0),
        continuityRetentionScore: Number(payload.larger_scale_user_facing_continuity_retention_score || 0),
        largerScaleGeneralizationScore: Number(payload.larger_scale_user_facing_generalization_score || 0),
        agentFeedbackRetentionCoverage: Number(payload.agent_feedback_retention_coverage || 0),
        actionConsequenceFeedbackRetentionCount: Number(payload.action_consequence_feedback_retention_count || 0),
        readableFeedbackRetentionCount: Number(payload.readable_feedback_retention_count || 0),
        regionSessionRetentionCount: Number(payload.region_session_retention_count || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_larger_scale_retained_action_consequence_feedback_diversity_continuity;
      if (
        !payload ||
        payload.schema !==
          "longer_larger_scale_retained_action_consequence_feedback_diversity_continuity_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-longer-larger-scale-retained-action-consequence-feedback-diversity-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.longer_diversity_continuity_score || 0) < 0.92 ||
        Number(payload.same_source_longer_static_control_score || 1) > 0.56 ||
        Number(payload.baseline_advantage || 0) < 0.34 ||
        Number(payload.retained_session_count || 0) !== 8 ||
        Number(payload.longer_window_count || 0) !== 6 ||
        Number(payload.longer_session_window_count || 0) !== 48 ||
        Number(payload.action_continuity_record_count || 0) !== 48 ||
        Number(payload.consequence_continuity_record_count || 0) !== 48 ||
        Number(payload.feedback_continuity_record_count || 0) !== 48 ||
        Number(payload.retained_agent_feedback_carryover_count || 0) !== 8 ||
        Number(payload.action_category_count || 0) < 6 ||
        Number(payload.consequence_class_count || 0) < 6 ||
        Number(payload.feedback_mode_count || 0) < 6 ||
        Number(payload.continuity_retention_score || 0) < 0.94 ||
        Number(payload.larger_scale_generalization_score || 0) < 0.94 ||
        Number(payload.source_record_count || 0) < 28
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuitySummary(frame) {
      const payload = longerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedCapabilityId: payload.selected_capability_id || "unknown",
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        score: Number(payload.longer_diversity_continuity_score || 0),
        controlScore: Number(payload.same_source_longer_static_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        retainedSessionCount: Number(payload.retained_session_count || 0),
        longerWindowCount: Number(payload.longer_window_count || 0),
        longerSessionWindowCount: Number(payload.longer_session_window_count || 0),
        actionContinuityCount: Number(payload.action_continuity_record_count || 0),
        consequenceContinuityCount: Number(payload.consequence_continuity_record_count || 0),
        feedbackContinuityCount: Number(payload.feedback_continuity_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.retained_agent_feedback_carryover_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        consequenceClassCount: Number(payload.consequence_class_count || 0),
        feedbackModeCount: Number(payload.feedback_mode_count || 0),
        continuityRetentionScore: Number(payload.continuity_retention_score || 0),
        largerScaleGeneralizationScore: Number(payload.larger_scale_generalization_score || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_larger_scale_retained_action_consequence_feedback_diversity_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_longer_larger_scale_retained_action_consequence_feedback_diversity_continuity_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-region-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 300 ||
        Number(payload.score_margin || 0) < 80 ||
        Number(payload.source_record_count || 0) < 31 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 9 ||
        Number(payload.blocked_candidate_count || 0) !== 8 ||
        Number(payload.longer_diversity_continuity_score || 0) < 0.9 ||
        Number(payload.longer_window_count || 0) !== 6 ||
        Number(payload.longer_session_window_count || 0) !== 48 ||
        Number(payload.action_continuity_record_count || 0) !== 48 ||
        Number(payload.consequence_continuity_record_count || 0) !== 48 ||
        Number(payload.feedback_continuity_record_count || 0) !== 48 ||
        Number(payload.retained_agent_feedback_carryover_count || 0) !== 8 ||
        Number(payload.same_source_longer_static_control_score || 1) > 0.55 ||
        Number(payload.retained_action_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_consequence_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_feedback_diversity_record_count || 0) !== 48 ||
        Number(payload.retained_agent_feedback_diversity_carryover_count || 0) !== 8 ||
        Number(payload.retained_action_consequence_feedback_diversity_score || 0) < 0.9 ||
        Number(payload.larger_scale_user_facing_continuity_retention_score || 0) < 0.94 ||
        Number(payload.larger_scale_user_facing_generalization_score || 0) < 0.94 ||
        Number(payload.agent_feedback_retention_coverage || 0) < 1.0
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuityGapAuditSummary(frame) {
      const payload = postLongerLargerScaleRetainedActionConsequenceFeedbackDiversityContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        longerDiversityContinuityScore: Number(payload.longer_diversity_continuity_score || 0),
        longerWindowCount: Number(payload.longer_window_count || 0),
        longerSessionWindowCount: Number(payload.longer_session_window_count || 0),
        actionContinuityCount: Number(payload.action_continuity_record_count || 0),
        consequenceContinuityCount: Number(payload.consequence_continuity_record_count || 0),
        feedbackContinuityCount: Number(payload.feedback_continuity_record_count || 0),
        longerAgentFeedbackCarryoverCount: Number(payload.retained_agent_feedback_carryover_count || 0),
        longerStaticControlScore: Number(payload.same_source_longer_static_control_score || 0),
        retainedDiversityScore: Number(payload.retained_action_consequence_feedback_diversity_score || 0),
        actionCount: Number(payload.retained_action_diversity_record_count || 0),
        consequenceCount: Number(payload.retained_consequence_diversity_record_count || 0),
        feedbackCount: Number(payload.retained_feedback_diversity_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.retained_agent_feedback_diversity_carryover_count || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sameSourceControlScore: Number(payload.same_source_repeated_pattern_control_score || 0),
        continuityRetentionScore: Number(payload.larger_scale_user_facing_continuity_retention_score || 0),
        largerScaleGeneralizationScore: Number(payload.larger_scale_user_facing_generalization_score || 0),
        agentFeedbackRetentionCoverage: Number(payload.agent_feedback_retention_coverage || 0),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function multiRegionLargerScaleRetainedDiversityContinuityGeneralization(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization;
      if (
        !payload ||
        payload.schema !==
          "multi_region_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-region-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.region_count || 0) < 4 ||
        Number(payload.longer_window_count || 0) !== 6 ||
        Number(payload.region_window_count || 0) < 24 ||
        Number(payload.action_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.consequence_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.feedback_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.agent_feedback_carryover_count || 0) < 4 ||
        Number(payload.same_source_control_count || 0) !== 4 ||
        Number(payload.same_source_best_control_score || 1) > 0.56 ||
        Number(payload.multi_region_generalization_score || 0) < 0.9 ||
        Number(payload.baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_longer_diversity_continuity_score || 0) < 0.9 ||
        Number(payload.previous_retained_diversity_score || 0) < 0.9 ||
        Number(payload.previous_continuity_retention_score || 0) < 0.9 ||
        Number(payload.previous_larger_scale_generalization_score || 0) < 0.9 ||
        Number(payload.source_record_count || 0) < 15
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiRegionLargerScaleRetainedDiversityContinuityGeneralizationSummary(frame) {
      const payload = multiRegionLargerScaleRetainedDiversityContinuityGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        score: Number(payload.multi_region_generalization_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        controlScore: Number(payload.same_source_best_control_score || 0),
        regionCount: Number(payload.region_count || 0),
        longerWindowCount: Number(payload.longer_window_count || 0),
        regionWindowCount: Number(payload.region_window_count || 0),
        actionContinuityCount: Number(payload.action_diversity_continuity_record_count || 0),
        consequenceContinuityCount: Number(payload.consequence_diversity_continuity_record_count || 0),
        feedbackContinuityCount: Number(payload.feedback_diversity_continuity_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        previousLongerContinuityScore: Number(payload.previous_longer_diversity_continuity_score || 0),
        previousRetainedDiversityScore: Number(payload.previous_retained_diversity_score || 0),
        previousContinuityRetentionScore: Number(payload.previous_continuity_retention_score || 0),
        previousLargerScaleGeneralizationScore: Number(payload.previous_larger_scale_generalization_score || 0),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postMultiRegionLargerScaleRetainedDiversityContinuityGeneralizationGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_region_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::cross-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 400 ||
        Number(payload.score_margin || 0) < 100 ||
        Number(payload.source_record_count || 0) < 40 ||
        Number(payload.gap_count || 0) !== 9 ||
        Number(payload.candidate_count || 0) !== 10 ||
        Number(payload.blocked_candidate_count || 0) !== 9 ||
        Number(payload.multi_region_generalization_score || 0) < 0.95 ||
        Number(payload.region_count || 0) < 4 ||
        Number(payload.longer_window_count || 0) !== 6 ||
        Number(payload.region_window_count || 0) < 24 ||
        Number(payload.action_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.consequence_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.feedback_diversity_continuity_record_count || 0) < 24 ||
        Number(payload.agent_feedback_carryover_count || 0) < 4 ||
        Number(payload.same_source_control_count || 0) !== 4 ||
        Number(payload.same_source_best_control_score || 1) > 0.55 ||
        Number(payload.baseline_advantage || 0) < 0.4 ||
        Number(payload.previous_longer_diversity_continuity_score || 0) < 0.9 ||
        Number(payload.previous_retained_diversity_score || 0) < 0.9 ||
        Number(payload.previous_continuity_retention_score || 0) < 0.94 ||
        Number(payload.previous_larger_scale_generalization_score || 0) < 0.94
      ) return {};
      for (const key of ["projection_payload_digest", "report_digest", "replay_digest", "browser_evidence_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionLargerScaleRetainedDiversityContinuityGeneralizationGapAuditSummary(frame) {
      const payload = postMultiRegionLargerScaleRetainedDiversityContinuityGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        multiRegionScore: Number(payload.multi_region_generalization_score || 0),
        regionCount: Number(payload.region_count || 0),
        longerWindowCount: Number(payload.longer_window_count || 0),
        regionWindowCount: Number(payload.region_window_count || 0),
        actionContinuityCount: Number(payload.action_diversity_continuity_record_count || 0),
        consequenceContinuityCount: Number(payload.consequence_diversity_continuity_record_count || 0),
        feedbackContinuityCount: Number(payload.feedback_diversity_continuity_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        sameSourceControlCount: Number(payload.same_source_control_count || 0),
        sameSourceControlScore: Number(payload.same_source_best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        previousLongerContinuityScore: Number(payload.previous_longer_diversity_continuity_score || 0),
        previousRetainedDiversityScore: Number(payload.previous_retained_diversity_score || 0),
        previousContinuityRetentionScore: Number(payload.previous_continuity_retention_score || 0),
        previousLargerScaleGeneralizationScore: Number(payload.previous_larger_scale_generalization_score || 0),
        postLongerSelectedNextActionId: payload.post_longer_selected_next_action_id || "unknown",
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function crossSessionLargerScaleRetainedDiversityTransfer(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.cross_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer;
      if (
        !payload ||
        payload.schema !==
          "cross_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-cross-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.cross_session_transfer_score || 0) < 0.9 ||
        Number(payload.same_source_no_transfer_control_score || 1) > 0.57 ||
        Number(payload.baseline_advantage || 0) < 0.32 ||
        Number(payload.source_record_count || 0) < 25 ||
        Number(payload.session_boundary_count || 0) < 3 ||
        Number(payload.transfer_record_count || 0) < 6 ||
        Number(payload.action_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.consequence_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.feedback_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.continuity_transfer_record_count || 0) < 6 ||
        Number(payload.generalization_transfer_record_count || 0) < 4 ||
        Number(payload.agent_feedback_carryover_transfer_record_count || 0) < 4 ||
        Number(payload.same_source_control_count || 0) !== 4 ||
        Number(payload.previous_multi_region_generalization_score || 0) < 0.9 ||
        Number(payload.previous_longer_diversity_continuity_score || 0) < 0.9 ||
        Number(payload.previous_retained_diversity_score || 0) < 0.9 ||
        Number(payload.previous_continuity_retention_score || 0) < 0.9 ||
        Number(payload.previous_larger_scale_generalization_score || 0) < 0.9
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "browser_evidence_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function crossSessionLargerScaleRetainedDiversityTransferSummary(frame) {
      const payload = crossSessionLargerScaleRetainedDiversityTransfer(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        transferScore: Number(payload.cross_session_transfer_score || 0),
        controlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        sessionBoundaryCount: Number(payload.session_boundary_count || 0),
        transferRecordCount: Number(payload.transfer_record_count || 0),
        actionTransferCount: Number(payload.action_diversity_transfer_record_count || 0),
        consequenceTransferCount: Number(payload.consequence_diversity_transfer_record_count || 0),
        feedbackTransferCount: Number(payload.feedback_diversity_transfer_record_count || 0),
        continuityTransferCount: Number(payload.continuity_transfer_record_count || 0),
        generalizationTransferCount: Number(payload.generalization_transfer_record_count || 0),
        agentFeedbackTransferCount: Number(payload.agent_feedback_carryover_transfer_record_count || 0),
        sameSourceControlCount: Number(payload.same_source_control_count || 0),
        previousMultiRegionGeneralizationScore: Number(payload.previous_multi_region_generalization_score || 0),
        previousLongerContinuityScore: Number(payload.previous_longer_diversity_continuity_score || 0),
        previousRetainedDiversityScore: Number(payload.previous_retained_diversity_score || 0),
        previousContinuityRetentionScore: Number(payload.previous_continuity_retention_score || 0),
        previousLargerScaleGeneralizationScore: Number(payload.previous_larger_scale_generalization_score || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        browserEvidenceDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postCrossSessionLargerScaleRetainedDiversityTransferGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_cross_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_cross_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 140 ||
        Number(payload.second_best_score || 999) > 125 ||
        Number(payload.score_margin || 0) < 25 ||
        Number(payload.source_record_count || 0) < 40 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_record_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7 ||
        Number(payload.previous_cross_session_transfer_score || 0) < 0.9 ||
        Number(payload.previous_same_source_no_transfer_control_score || 1) > 0.57 ||
        Number(payload.previous_baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_session_boundary_count || 0) < 3 ||
        Number(payload.previous_transfer_record_count || 0) < 6 ||
        Number(payload.previous_action_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.previous_consequence_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.previous_feedback_diversity_transfer_record_count || 0) < 6 ||
        Number(payload.previous_continuity_transfer_record_count || 0) < 6 ||
        Number(payload.previous_generalization_transfer_record_count || 0) < 4 ||
        Number(payload.previous_agent_feedback_carryover_transfer_record_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postCrossSessionLargerScaleRetainedDiversityTransferGapAuditSummary(frame) {
      const payload = postCrossSessionLargerScaleRetainedDiversityTransferGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousTransferScore: Number(payload.previous_cross_session_transfer_score || 0),
        previousControlScore: Number(payload.previous_same_source_no_transfer_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousSessionBoundaryCount: Number(payload.previous_session_boundary_count || 0),
        previousTransferRecordCount: Number(payload.previous_transfer_record_count || 0),
        previousActionTransferCount: Number(payload.previous_action_diversity_transfer_record_count || 0),
        previousConsequenceTransferCount: Number(payload.previous_consequence_diversity_transfer_record_count || 0),
        previousFeedbackTransferCount: Number(payload.previous_feedback_diversity_transfer_record_count || 0),
        previousContinuityTransferCount: Number(payload.previous_continuity_transfer_record_count || 0),
        previousGeneralizationTransferCount: Number(payload.previous_generalization_transfer_record_count || 0),
        previousAgentFeedbackTransferCount: Number(payload.previous_agent_feedback_carryover_transfer_record_count || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function multiSessionLargerScaleRetainedTransferRetention(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention;
      if (
        !payload ||
        payload.schema !==
          "multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.retention_score || 0) < 0.90 ||
        Number(payload.same_source_transfer_only_retention_control_score || 1) > 0.57 ||
        Number(payload.baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_cross_session_transfer_score || 0) < 0.90
      ) return {};
      if (
        Number(payload.source_record_count || 0) < 40 ||
        Number(payload.followup_session_count || 0) < 3 ||
        Number(payload.retained_transfer_record_count || 0) < 6 ||
        Number(payload.action_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.consequence_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.feedback_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.continuity_transfer_retention_count || 0) < 6 ||
        Number(payload.generalization_transfer_retention_count || 0) < 4 ||
        Number(payload.agent_feedback_transfer_retention_count || 0) < 4 ||
        Number(payload.same_source_control_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiSessionLargerScaleRetainedTransferRetentionSummary(frame) {
      const payload = multiSessionLargerScaleRetainedTransferRetention(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        retentionScore: Number(payload.retention_score || 0),
        controlScore: Number(payload.same_source_transfer_only_retention_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        previousTransferScore: Number(payload.previous_cross_session_transfer_score || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        followupSessionCount: Number(payload.followup_session_count || 0),
        retainedTransferCount: Number(payload.retained_transfer_record_count || 0),
        actionTransferRetentionCount: Number(payload.action_diversity_transfer_retention_count || 0),
        consequenceTransferRetentionCount: Number(payload.consequence_diversity_transfer_retention_count || 0),
        feedbackTransferRetentionCount: Number(payload.feedback_diversity_transfer_retention_count || 0),
        continuityTransferRetentionCount: Number(payload.continuity_transfer_retention_count || 0),
        generalizationTransferRetentionCount: Number(payload.generalization_transfer_retention_count || 0),
        agentFeedbackTransferRetentionCount: Number(payload.agent_feedback_transfer_retention_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postMultiSessionLargerScaleRetainedTransferRetentionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::longer-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "single-session",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 150 ||
        Number(payload.second_best_score || 999) > 130 ||
        Number(payload.score_margin || 0) < 30 ||
        Number(payload.source_record_count || 0) < 60 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 9 ||
        Number(payload.score_record_count || 0) !== 9 ||
        Number(payload.blocked_candidate_count || 0) !== 8 ||
        Number(payload.previous_retention_score || 0) < 0.9 ||
        Number(payload.previous_same_source_transfer_only_retention_control_score || 1) > 0.57 ||
        Number(payload.previous_baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_followup_session_count || 0) < 3 ||
        Number(payload.previous_retained_transfer_record_count || 0) < 6 ||
        Number(payload.previous_action_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.previous_consequence_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.previous_feedback_diversity_transfer_retention_count || 0) < 6 ||
        Number(payload.previous_continuity_transfer_retention_count || 0) < 6 ||
        Number(payload.previous_generalization_transfer_retention_count || 0) < 4 ||
        Number(payload.previous_agent_feedback_transfer_retention_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiSessionLargerScaleRetainedTransferRetentionGapAuditSummary(frame) {
      const payload = postMultiSessionLargerScaleRetainedTransferRetentionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        previousControlScore: Number(payload.previous_same_source_transfer_only_retention_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousFollowupSessionCount: Number(payload.previous_followup_session_count || 0),
        previousRetainedTransferCount: Number(payload.previous_retained_transfer_record_count || 0),
        previousActionTransferRetentionCount: Number(payload.previous_action_diversity_transfer_retention_count || 0),
        previousConsequenceTransferRetentionCount: Number(payload.previous_consequence_diversity_transfer_retention_count || 0),
        previousFeedbackTransferRetentionCount: Number(payload.previous_feedback_diversity_transfer_retention_count || 0),
        previousContinuityTransferRetentionCount: Number(payload.previous_continuity_transfer_retention_count || 0),
        previousGeneralizationTransferRetentionCount: Number(payload.previous_generalization_transfer_retention_count || 0),
        previousAgentFeedbackTransferRetentionCount: Number(payload.previous_agent_feedback_transfer_retention_count || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function longerMultiSessionLargerScaleRetainedTransferRetentionContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity;
      if (
        !payload ||
        payload.schema !==
          "longer_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.viewer_polish_blocked !== true ||
        payload.real_rendering_physics_chemistry_blocked !== true ||
        payload.repeated_selection_blocked !== true ||
        payload.repeated_transfer_blocked !== true ||
        payload.repeated_retention_blocked !== true ||
        payload.single_session_only_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-longer-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "single-session",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.continuity_score || 0) < 0.92 ||
        Number(payload.enabled_score || 0) < 0.90 ||
        Number(payload.best_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage || 0) < 0.34 ||
        Number(payload.previous_retention_score || 0) < 0.90 ||
        Number(payload.previous_same_source_transfer_only_retention_control_score || 1) > 0.57 ||
        Number(payload.previous_baseline_advantage || 0) < 0.32 ||
        Number(payload.source_record_count || 0) < 60 ||
        Number(payload.window_count || 0) !== 6 ||
        Number(payload.covered_tick_span || 0) !== 1536 ||
        Number(payload.retained_transfer_continuity_count || 0) < 6 ||
        Number(payload.action_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.consequence_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.feedback_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.continuity_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.generalization_transfer_retention_continuity_count || 0) < 4 ||
        Number(payload.agent_feedback_transfer_retention_continuity_count || 0) < 4 ||
        Number(payload.same_source_control_count || 0) < 2
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerMultiSessionLargerScaleRetainedTransferRetentionContinuitySummary(frame) {
      const payload = longerMultiSessionLargerScaleRetainedTransferRetentionContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        continuityScore: Number(payload.continuity_score || 0),
        enabledScore: Number(payload.enabled_score || 0),
        controlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        retainedTransferContinuityCount: Number(payload.retained_transfer_continuity_count || 0),
        actionTransferRetentionContinuityCount: Number(payload.action_transfer_retention_continuity_count || 0),
        consequenceTransferRetentionContinuityCount: Number(payload.consequence_transfer_retention_continuity_count || 0),
        feedbackTransferRetentionContinuityCount: Number(payload.feedback_transfer_retention_continuity_count || 0),
        continuityTransferRetentionContinuityCount: Number(payload.continuity_transfer_retention_continuity_count || 0),
        generalizationTransferRetentionContinuityCount: Number(payload.generalization_transfer_retention_continuity_count || 0),
        agentFeedbackTransferRetentionContinuityCount: Number(payload.agent_feedback_transfer_retention_continuity_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postLongerMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_longer_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.viewer_polish_blocked !== true ||
        payload.real_rendering_physics_chemistry_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-region-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "single-session",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (
        selectedScore < 170 ||
        secondBestScore > 135 ||
        scoreMargin < 35 ||
        scoreMargin !== selectedScore - secondBestScore
      ) return {};
      if (
        Number(payload.previous_continuity_score || 0) < 0.92 ||
        Number(payload.previous_enabled_score || 0) < 0.90 ||
        Number(payload.previous_best_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage || 0) < 0.34 ||
        Number(payload.previous_window_count || 0) !== 6 ||
        Number(payload.previous_covered_tick_span || 0) !== 1536 ||
        Number(payload.previous_retained_transfer_continuity_count || 0) < 6 ||
        Number(payload.previous_action_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_consequence_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_feedback_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_continuity_transfer_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_generalization_transfer_retention_continuity_count || 0) < 4 ||
        Number(payload.previous_agent_feedback_transfer_retention_continuity_count || 0) < 4
      ) return {};
      if (
        Number(payload.source_record_count || 0) < 85 ||
        Number(payload.gap_count || 0) !== 9 ||
        Number(payload.candidate_count || 0) !== 10 ||
        Number(payload.score_record_count || 0) !== 10 ||
        Number(payload.blocked_candidate_count || 0) !== 9
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAuditSummary(frame) {
      const payload = postLongerMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousRetainedTransferContinuityCount: Number(payload.previous_retained_transfer_continuity_count || 0),
        previousActionTransferRetentionContinuityCount: Number(payload.previous_action_transfer_retention_continuity_count || 0),
        previousConsequenceTransferRetentionContinuityCount: Number(payload.previous_consequence_transfer_retention_continuity_count || 0),
        previousFeedbackTransferRetentionContinuityCount: Number(payload.previous_feedback_transfer_retention_continuity_count || 0),
        previousContinuityTransferRetentionContinuityCount: Number(payload.previous_continuity_transfer_retention_continuity_count || 0),
        previousGeneralizationTransferRetentionContinuityCount: Number(payload.previous_generalization_transfer_retention_continuity_count || 0),
        previousAgentFeedbackTransferRetentionContinuityCount: Number(payload.previous_agent_feedback_transfer_retention_continuity_count || 0),
        previousAgentFeedbackCount: Number(payload.previous_agent_feedback_transfer_retention_continuity_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function multiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity;
      if (
        !payload ||
        payload.schema !==
          "multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.viewer_polish_blocked !== true ||
        payload.real_rendering_physics_chemistry_blocked !== true ||
        payload.repeated_selection_blocked !== true ||
        payload.repeated_transfer_blocked !== true ||
        payload.repeated_retention_blocked !== true ||
        payload.repeated_longer_continuity_blocked !== true ||
        payload.single_region_only_blocked !== true ||
        payload.single_session_only_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-region-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "cross-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-hardening",
        "multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-hardening",
        "longer-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-hardening",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.enabled_score || 0) < 0.94 ||
        Number(payload.continuity_score || 0) < 0.94 ||
        Number(payload.best_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage || 0) < 0.36 ||
        Number(payload.previous_continuity_score || 0) < 0.92 ||
        Number(payload.previous_enabled_score || 0) < 0.90 ||
        Number(payload.previous_best_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage || 0) < 0.34 ||
        Number(payload.source_record_count || 0) < 100 ||
        Number(payload.region_count || 0) !== 4 ||
        Number(payload.session_count || 0) !== 3 ||
        Number(payload.region_session_cell_count || 0) !== 12 ||
        Number(payload.window_count || 0) !== 6 ||
        Number(payload.covered_tick_span || 0) !== 1536 ||
        Number(payload.retained_transfer_continuity_count || 0) < 12 ||
        Number(payload.action_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.consequence_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.feedback_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.continuity_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.generalization_transfer_retention_continuity_count || 0) < 8 ||
        Number(payload.agent_feedback_transfer_retention_continuity_count || 0) < 8 ||
        Number(payload.cross_axis_edge_count || 0) < 8 ||
        Number(payload.same_source_control_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuitySummary(frame) {
      const payload = multiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        enabledScore: Number(payload.enabled_score || 0),
        continuityScore: Number(payload.continuity_score || 0),
        controlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        regionCount: Number(payload.region_count || 0),
        sessionCount: Number(payload.session_count || 0),
        regionSessionCellCount: Number(payload.region_session_cell_count || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        retainedTransferContinuityCount: Number(payload.retained_transfer_continuity_count || 0),
        actionTransferRetentionContinuityCount: Number(payload.action_transfer_retention_continuity_count || 0),
        consequenceTransferRetentionContinuityCount: Number(payload.consequence_transfer_retention_continuity_count || 0),
        feedbackTransferRetentionContinuityCount: Number(payload.feedback_transfer_retention_continuity_count || 0),
        continuityTransferRetentionContinuityCount: Number(payload.continuity_transfer_retention_continuity_count || 0),
        generalizationTransferRetentionContinuityCount: Number(payload.generalization_transfer_retention_continuity_count || 0),
        agentFeedbackTransferRetentionContinuityCount: Number(payload.agent_feedback_transfer_retention_continuity_count || 0),
        crossAxisEdgeCount: Number(payload.cross_axis_edge_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postMultiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.viewer_polish_blocked !== true ||
        payload.real_rendering_physics_chemistry_blocked !== true ||
        payload.repeated_current_hardening_blocked !== true ||
        payload.repeated_longer_continuity_blocked !== true ||
        payload.repeated_retention_transfer_blocked !== true ||
        payload.single_axis_only_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::large-scale-multi-region-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-stress-and-budget-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "repeat-current",
        "repeat-longer",
        "repeat-retained-transfer",
        "single-axis",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
      ]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (
        selectedScore < 190 ||
        secondBestScore > 145 ||
        scoreMargin < 45 ||
        scoreMargin !== selectedScore - secondBestScore
      ) return {};
      if (
        Number(payload.previous_region_count || 0) !== 4 ||
        Number(payload.previous_session_count || 0) !== 3 ||
        Number(payload.previous_region_session_cell_count || 0) !== 12 ||
        Number(payload.previous_window_count || 0) !== 6 ||
        Number(payload.previous_covered_tick_span || 0) !== 1536 ||
        Number(payload.previous_enabled_score || 0) < 0.94 ||
        Number(payload.previous_continuity_score || 0) < 0.94 ||
        Number(payload.previous_best_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage || 0) < 0.36 ||
        Number(payload.previous_retained_transfer_continuity_count || 0) < 12 ||
        Number(payload.previous_action_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.previous_consequence_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.previous_feedback_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.previous_continuity_transfer_retention_continuity_count || 0) < 12 ||
        Number(payload.previous_generalization_transfer_retention_continuity_count || 0) < 8 ||
        Number(payload.previous_agent_feedback_transfer_retention_continuity_count || 0) < 8 ||
        Number(payload.previous_cross_axis_edge_count || 0) < 8 ||
        Number(payload.source_count || payload.source_record_count || 0) < 120 ||
        Number(payload.gap_count || 0) !== 9 ||
        Number(payload.candidate_count || 0) !== 10 ||
        Number(payload.score_record_count || 0) !== 10 ||
        Number(payload.blocked_candidate_count || 0) !== 9
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAuditSummary(frame) {
      const payload = postMultiRegionMultiSessionLargerScaleRetainedTransferRetentionContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousSessionCount: Number(payload.previous_session_count || 0),
        previousRegionSessionCellCount: Number(payload.previous_region_session_cell_count || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousRetainedTransferContinuityCount: Number(payload.previous_retained_transfer_continuity_count || 0),
        previousActionTransferRetentionContinuityCount: Number(payload.previous_action_transfer_retention_continuity_count || 0),
        previousConsequenceTransferRetentionContinuityCount: Number(payload.previous_consequence_transfer_retention_continuity_count || 0),
        previousFeedbackTransferRetentionContinuityCount: Number(payload.previous_feedback_transfer_retention_continuity_count || 0),
        previousContinuityTransferRetentionContinuityCount: Number(payload.previous_continuity_transfer_retention_continuity_count || 0),
        previousGeneralizationTransferRetentionContinuityCount: Number(payload.previous_generalization_transfer_retention_continuity_count || 0),
        previousAgentFeedbackTransferRetentionContinuityCount: Number(payload.previous_agent_feedback_transfer_retention_continuity_count || 0),
        previousCrossAxisEdgeCount: Number(payload.previous_cross_axis_edge_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function largeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudget(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.large_scale_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_stress_budget;
      if (
        !payload ||
        payload.schema !==
          "large_scale_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_stress_budget_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.repeated_proof_blocked !== true ||
        payload.gap_audit_only_blocked !== true ||
        payload.viewer_polish_blocked !== true ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.real_rendering_physics_chemistry_blocked !== true ||
        payload.single_region_only_blocked !== true ||
        payload.single_session_only_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated") && value !== false) return {};
      }
      const selected = String(payload.selected_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::large-scale-multi-region-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-stress-and-budget-hardening"
      ) return {};
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-large-scale-multi-region-multi-session-larger-scale-retained-action-consequence-feedback-diversity-continuity-generalization-transfer-retention-continuity-stress-budget-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
        "repeat-current",
        "repeat-retained",
        "single-region",
        "single-session",
      ]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.previous_region_count || 0) < 4 ||
        Number(payload.previous_session_count || 0) < 3 ||
        Number(payload.previous_region_session_cell_count || 0) < 12 ||
        Number(payload.previous_window_count || 0) < 6 ||
        Number(payload.previous_covered_tick_span || 0) < 1536 ||
        Number(payload.previous_enabled_score || 0) < 0.986 ||
        Number(payload.previous_continuity_score || 0) < 0.984 ||
        Number(payload.previous_best_control_score || 1) > 0.56 ||
        Number(payload.previous_baseline_advantage || 0) < 0.426 ||
        Number(payload.stressed_region_count || 0) < 6 ||
        Number(payload.stressed_session_count || 0) < 4 ||
        Number(payload.stressed_region_session_cell_count || 0) < 24 ||
        Number(payload.stress_window_count || 0) < 8 ||
        Number(payload.covered_stress_tick_span || 0) < 2048 ||
        Number(payload.retained_transfer_stress_count || 0) < 24 ||
        Number(payload.action_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.consequence_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.feedback_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.continuity_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.generalization_transfer_retention_stress_count || 0) < 12 ||
        Number(payload.agent_feedback_transfer_retention_stress_count || 0) < 12 ||
        Number(payload.runtime_budget_score || 0) < 0.88 ||
        Number(payload.artifact_budget_score || 0) < 0.88 ||
        Number(payload.retained_component_stress_score || 0) < 0.90 ||
        Number(payload.agent_feedback_carryover_score || 0) < 0.90 ||
        Number(payload.same_source_control_score || 1) > 0.60 ||
        Number(payload.baseline_advantage || 0) < 0.30 ||
        Number(payload.hardening_score || 0) < 0.88
      ) return {};
      for (const key of [
        "source_bundle_digest",
        "projection_payload_digest",
        "report_digest",
        "replay_digest",
        "stress_matrix_digest",
        "score_digest",
        "outcome_digest",
      ]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function largeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudgetSummary(frame) {
      const payload = largeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudget(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedActionId: payload.selected_action_id || "unknown",
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousSessionCount: Number(payload.previous_session_count || 0),
        previousRegionSessionCellCount: Number(payload.previous_region_session_cell_count || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        stressedRegionCount: Number(payload.stressed_region_count || 0),
        stressedSessionCount: Number(payload.stressed_session_count || 0),
        stressedCellCount: Number(payload.stressed_region_session_cell_count || 0),
        stressWindowCount: Number(payload.stress_window_count || 0),
        coveredStressTickSpan: Number(payload.covered_stress_tick_span || 0),
        retainedStressCount: Number(payload.retained_transfer_stress_count || 0),
        actionStressCount: Number(payload.action_transfer_retention_stress_count || 0),
        consequenceStressCount: Number(payload.consequence_transfer_retention_stress_count || 0),
        feedbackStressCount: Number(payload.feedback_transfer_retention_stress_count || 0),
        continuityStressCount: Number(payload.continuity_transfer_retention_stress_count || 0),
        generalizationStressCount: Number(payload.generalization_transfer_retention_stress_count || 0),
        agentFeedbackStressCount: Number(payload.agent_feedback_transfer_retention_stress_count || 0),
        runtimeBudgetScore: Number(payload.runtime_budget_score || 0),
        artifactBudgetScore: Number(payload.artifact_budget_score || 0),
        retainedStressScore: Number(payload.retained_component_stress_score || 0),
        agentFeedbackCarryoverScore: Number(payload.agent_feedback_carryover_score || 0),
        stressAlignmentScore: Number(payload.stress_alignment_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        hardeningScore: Number(payload.hardening_score || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        stressMatrixDigestPrefix: String(payload.stress_matrix_digest || "unknown").slice(0, 19),
        scoreDigestPrefix: String(payload.score_digest || "unknown").slice(0, 19),
        outcomeDigestPrefix: String(payload.outcome_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postLargeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudgetGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_large_scale_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_stress_budget_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_large_scale_multi_region_multi_session_larger_scale_retained_action_consequence_feedback_diversity_continuity_generalization_transfer_retention_continuity_stress_budget_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.artifact_budget_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::stress-budget-resilient-multi-region-multi-session-larger-scale-retained-playable-meaning-hardening"
      ) return {};
      for (const term of [
        "production",
        "pilot",
        "invite",
        "external",
        "contact",
        "public",
        "analytics",
        "viewer-polish",
        "viewer polish",
        "real-rendering",
        "real rendering",
        "rendering",
        "physics",
        "chemistry",
        "repeat",
      ]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (
        selectedScore < 170 ||
        secondBestScore > 140 ||
        scoreMargin < 35 ||
        scoreMargin !== selectedScore - secondBestScore
      ) return {};
      if (
        Number(payload.source_count || payload.source_record_count || 0) < 133 ||
        Number(payload.gap_count || 0) !== 9 ||
        Number(payload.candidate_count || 0) !== 10 ||
        Number(payload.score_record_count || payload.score_count || 0) !== 10 ||
        Number(payload.blocked_candidate_count || 0) !== 9 ||
        Number(payload.stressed_region_count || 0) < 6 ||
        Number(payload.stressed_session_count || 0) < 4 ||
        Number(payload.stressed_region_session_cell_count || 0) < 24 ||
        Number(payload.stress_window_count || 0) < 8 ||
        Number(payload.covered_stress_tick_span || 0) < 2048 ||
        Number(payload.retained_transfer_stress_count || 0) < 24 ||
        Number(payload.action_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.consequence_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.feedback_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.continuity_transfer_retention_stress_count || 0) < 24 ||
        Number(payload.generalization_transfer_retention_stress_count || 0) < 12 ||
        Number(payload.agent_feedback_transfer_retention_stress_count || 0) < 12 ||
        Number(payload.runtime_budget_score || 0) < 0.88 ||
        Number(payload.artifact_budget_score || 0) < 0.88 ||
        Number(payload.retained_component_stress_score || 0) < 0.90 ||
        Number(payload.agent_feedback_carryover_score || 0) < 0.90 ||
        Number(payload.same_source_control_score || 1) > 0.60 ||
        Number(payload.baseline_advantage || 0) < 0.30 ||
        Number(payload.hardening_score || 0) < 0.88
      ) return {};
      for (const key of [
        "source_bundle_digest",
        "projection_payload_digest",
        "selection_digest",
        "browser_evidence_digest",
        "report_digest",
        "replay_digest",
      ]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLargeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudgetGapAuditSummary(frame) {
      const payload = postLargeScaleMultiRegionMultiSessionLargerScaleRetainedStressBudgetGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || payload.source_record_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        stressedRegionCount: Number(payload.stressed_region_count || 0),
        stressedSessionCount: Number(payload.stressed_session_count || 0),
        stressedCellCount: Number(payload.stressed_region_session_cell_count || 0),
        stressWindowCount: Number(payload.stress_window_count || 0),
        coveredStressTickSpan: Number(payload.covered_stress_tick_span || 0),
        retainedStressCount: Number(payload.retained_transfer_stress_count || 0),
        actionStressCount: Number(payload.action_transfer_retention_stress_count || 0),
        consequenceStressCount: Number(payload.consequence_transfer_retention_stress_count || 0),
        feedbackStressCount: Number(payload.feedback_transfer_retention_stress_count || 0),
        continuityStressCount: Number(payload.continuity_transfer_retention_stress_count || 0),
        generalizationStressCount: Number(payload.generalization_transfer_retention_stress_count || 0),
        agentFeedbackStressCount: Number(payload.agent_feedback_transfer_retention_stress_count || 0),
        runtimeBudgetScore: Number(payload.runtime_budget_score || 0),
        artifactBudgetScore: Number(payload.artifact_budget_score || 0),
        retainedStressScore: Number(payload.retained_component_stress_score || 0),
        agentFeedbackCarryoverScore: Number(payload.agent_feedback_carryover_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        hardeningScore: Number(payload.hardening_score || 0),
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        browserDigestPrefix: String(payload.browser_evidence_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postStressBudgetUserFacingSessionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_stress_budget_user_facing_session_gap_audit;
      if (
        !payload ||
        payload.schema !== "post_stress_budget_user_facing_session_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::larger-scale-user-facing-world-session-generalization-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer-polish", "viewer polish", "real-rendering", "real rendering", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 190 ||
        Number(payload.score_margin || 0) < 35 ||
        Number(payload.source_record_count || payload.source_count || 0) < 167 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_record_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7 ||
        Number(payload.previous_user_facing_session_score || 0) < 0.90 ||
        Number(payload.previous_min_session_score || 0) < 0.88 ||
        Number(payload.previous_min_region_session_experience_score || 0) < 0.90 ||
        Number(payload.previous_baseline_advantage || 0) < 0.30 ||
        Number(payload.previous_session_count || 0) < 4 ||
        Number(payload.previous_session_step_count || 0) < 24 ||
        Number(payload.previous_region_session_experience_count || 0) < 24 ||
        Number(payload.previous_action_consequence_feedback_readability_count || 0) < 16 ||
        Number(payload.previous_stress_window_count || 0) < 8 ||
        Number(payload.previous_region_session_cell_count || 0) < 24 ||
        Number(payload.previous_covered_stress_tick_span || 0) < 2048 ||
        Number(payload.agent_feedback_session_coverage || 0) < 1.0 ||
        Number(payload.runtime_budget_score || 0) < 0.88 ||
        Number(payload.artifact_budget_score || 0) < 0.88
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postStressBudgetUserFacingSessionGapAuditSummary(frame) {
      const payload = postStressBudgetUserFacingSessionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_record_count || payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreRecordCount: Number(payload.score_record_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousScore: Number(payload.previous_user_facing_session_score || 0),
        previousMinSessionScore: Number(payload.previous_min_session_score || 0),
        previousMinRegionSessionExperienceScore: Number(payload.previous_min_region_session_experience_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousSessionCount: Number(payload.previous_session_count || 0),
        previousSessionStepCount: Number(payload.previous_session_step_count || 0),
        previousRegionSessionExperienceCount: Number(payload.previous_region_session_experience_count || 0),
        previousReadabilityCount: Number(payload.previous_action_consequence_feedback_readability_count || 0),
        stressWindowCount: Number(payload.previous_stress_window_count || 0),
        stressedCellCount: Number(payload.previous_region_session_cell_count || 0),
        coveredStressTickSpan: Number(payload.previous_covered_stress_tick_span || 0),
        agentFeedbackSessionCoverage: Number(payload.agent_feedback_session_coverage || 0),
        runtimeBudgetScore: Number(payload.runtime_budget_score || 0),
        artifactBudgetScore: Number(payload.artifact_budget_score || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLargeScaleRuntimeStressGapAudit(frame) {
      const payload = frame && frame.payload && frame.payload.post_large_scale_runtime_stress_gap_audit;
      if (!payload || payload.schema !== "post_large_scale_runtime_stress_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_stress !== false ||
        payload.viewer_generated_budget !== false ||
        payload.viewer_generated_memory !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_playability !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postLargeScaleRuntimeStressGapAuditSummary(frame) {
      const payload = postLargeScaleRuntimeStressGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        rejectedStressOnlyCandidateId: payload.rejected_stress_only_candidate_id || "unknown",
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function stressResilientAgentFeedbackWorldExperience(frame) {
      const payload = frame && frame.payload && frame.payload.stress_resilient_agent_feedback_world_experience;
      if (!payload || payload.schema !== "stress_resilient_agent_feedback_world_experience_projection_v1") return {};
      if (
        payload.viewer_generated_stress_resilience !== false ||
        payload.viewer_generated_budget !== false ||
        payload.viewer_generated_baseline !== false ||
        payload.viewer_generated_memory !== false ||
        payload.viewer_generated_guidance !== false ||
        payload.viewer_generated_consequence !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function stressResilientAgentFeedbackWorldExperienceSummary(frame) {
      const payload = stressResilientAgentFeedbackWorldExperience(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.recommended_next_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        stressWindowCount: Number(payload.stress_window_count || 0),
        feedbackCarryoverCount: Number(payload.feedback_carryover_count || 0),
        baselineId: payload.baseline_id || "unknown",
        sessionScore: Number(payload.session_resilience_score || 0),
        baselineScore: Number(payload.baseline_resilience_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        budgetSurvivalMin: Number(payload.budget_survival_min || 0),
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function stressResilientAgentFeedbackGapAudit(frame) {
      const payload = frame && frame.payload && frame.payload.stress_resilient_agent_feedback_gap_audit;
      if (!payload || payload.schema !== "stress_resilient_agent_feedback_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_stress_resilience !== false ||
        payload.viewer_generated_budget !== false ||
        payload.viewer_generated_memory !== false ||
        payload.viewer_generated_guidance !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_playability !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function stressResilientAgentFeedbackGapAuditSummary(frame) {
      const payload = stressResilientAgentFeedbackGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        rejectedStressOnlyCandidateId: payload.rejected_repeated_stress_candidate_id || "unknown",
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function stressResilientAgentFeedbackGeneralization(frame) {
      const payload = frame && frame.payload && frame.payload.stress_resilient_agent_feedback_generalization;
      if (!payload || payload.schema !== "stress_resilient_agent_feedback_generalization_projection_v1") return {};
      if (
        payload.viewer_generated_multi_region_generalization !== false ||
        payload.viewer_generated_long_session_support !== false ||
        payload.viewer_generated_stress_resilience !== false ||
        payload.viewer_generated_budget !== false ||
        payload.viewer_generated_memory !== false ||
        payload.viewer_generated_guidance !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_playability !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_success !== false ||
        payload.viewer_generated_score !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function stressResilientAgentFeedbackGeneralizationSummary(frame) {
      const payload = stressResilientAgentFeedbackGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.recommended_next_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        regionCount: Array.isArray(payload.region_ids) ? payload.region_ids.length : 0,
        windowCount: Array.isArray(payload.window_ids) ? payload.window_ids.length : 0,
        carryoverCount: Array.isArray(payload.carryover_ids) ? payload.carryover_ids.length : 0,
        controlId: payload.control_id || "unknown",
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        scoreRecordId: payload.score_record_id || "unknown",
        generalizationScore: Number(payload.generalization_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postGeneralizationGapAudit(frame) {
      const payload = frame && frame.payload && frame.payload.post_generalization_gap_audit;
      if (!payload || payload.schema !== "post_generalization_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_generalization !== false ||
        payload.viewer_generated_stress_resilience !== false ||
        payload.viewer_generated_budget !== false ||
        payload.viewer_generated_memory !== false ||
        payload.viewer_generated_guidance !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_playability !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postGeneralizationGapAuditSummary(frame) {
      const payload = postGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        rejectedRepeatCandidateId: payload.rejected_repeat_generalization_candidate_id || "unknown",
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        generalizationScore: Number(payload.generalization_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function generalizedAgentFeedbackPlayableMeaning(frame) {
      const payload = frame && frame.payload && frame.payload.generalized_agent_feedback_playable_meaning;
      if (!payload || payload.schema !== "generalized_agent_feedback_playable_meaning_projection_v1") return {};
      if (
        payload.viewer_generated_playable_meaning !== false ||
        payload.viewer_generated_actionability !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_success !== false ||
        payload.viewer_generated_score !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function generalizedAgentFeedbackPlayableMeaningSummary(frame) {
      const payload = generalizedAgentFeedbackPlayableMeaning(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        score: Number(payload.score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        contextCount: Number(payload.context_count || 0),
        actionabilityCount: Number(payload.actionability_count || 0),
        feedbackExpectationCount: Number(payload.feedback_expectation_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postGeneralizedPlayableMeaningGapAudit(frame) {
      const payload = frame && frame.payload && frame.payload.post_generalized_playable_meaning_gap_audit;
      if (!payload || payload.schema !== "post_generalized_playable_meaning_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_playable_meaning !== false ||
        payload.viewer_generated_action_usability !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postGeneralizedPlayableMeaningGapAuditSummary(frame) {
      const payload = postGeneralizedPlayableMeaningGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function livePlayableMeaningSessionFluency(frame) {
      const payload = frame && frame.payload && frame.payload.live_playable_meaning_session_fluency;
      if (!payload || payload.schema !== "live_playable_meaning_session_fluency_projection_v1") return {};
      if (
        payload.viewer_generated_live_session_fluency !== false ||
        payload.viewer_generated_playable_meaning !== false ||
        payload.viewer_generated_action_usability !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_success !== false ||
        payload.viewer_generated_score !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function livePlayableMeaningSessionFluencySummary(frame) {
      const payload = livePlayableMeaningSessionFluency(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        score: Number(payload.score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sessionCount: Number(payload.session_count || 0),
        actionUsabilityCount: Number(payload.action_usability_count || 0),
        feedbackReadabilityCount: Number(payload.feedback_readability_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLivePlayableMeaningSessionFluencyGapAudit(frame) {
      const payload = frame && frame.payload && frame.payload.post_live_playable_meaning_session_fluency_gap_audit;
      if (!payload || payload.schema !== "post_live_playable_meaning_session_fluency_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_live_session_fluency !== false ||
        payload.viewer_generated_action_usability !== false ||
        payload.viewer_generated_natural_feedback_readability !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postLivePlayableMeaningSessionFluencyGapAuditSummary(frame) {
      const payload = postLivePlayableMeaningSessionFluencyGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longLivePlayableMeaningSessionContinuity(frame) {
      const payload = frame && frame.payload && frame.payload.long_live_playable_meaning_session_continuity;
      if (!payload || payload.schema !== "long_live_playable_meaning_session_continuity_projection_v1") return {};
      if (
        payload.viewer_generated_continuity !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function longLivePlayableMeaningSessionContinuitySummary(frame) {
      const payload = longLivePlayableMeaningSessionContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        score: Number(payload.score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        actionRecoveryCount: Number(payload.action_recovery_count || 0),
        feedbackReadabilityContinuityCount: Number(payload.feedback_readability_continuity_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongLivePlayableMeaningSessionContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_long_live_playable_meaning_session_continuity_gap_audit;
      if (!payload || payload.schema !== "post_long_live_playable_meaning_session_continuity_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_long_live_continuity !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postLongLivePlayableMeaningSessionContinuityGapAuditSummary(frame) {
      const payload = postLongLivePlayableMeaningSessionContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionLongLivePlayableMeaningGeneralization(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_long_live_playable_meaning_generalization;
      if (!payload || payload.schema !== "multi_region_long_live_playable_meaning_generalization_projection_v1") return {};
      if (
        payload.viewer_generated_multi_region_generalization !== false ||
        payload.viewer_generated_long_live_continuity !== false ||
        payload.viewer_generated_region_window_matrix !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_state !== false ||
        payload.viewer_generated_feedback_state !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_success !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function multiRegionLongLivePlayableMeaningGeneralizationSummary(frame) {
      const payload = multiRegionLongLivePlayableMeaningGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedActionId: payload.selected_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        regionCount: Array.isArray(payload.region_ids) ? payload.region_ids.length : 0,
        windowCount: Array.isArray(payload.window_ids) ? payload.window_ids.length : 0,
        regionWindowCount: Array.isArray(payload.region_window_ids) ? payload.region_window_ids.length : 0,
        actionRecoveryRegionCount: Array.isArray(payload.action_recovery_region_ids) ? payload.action_recovery_region_ids.length : 0,
        feedbackReadabilityRegionCount: Array.isArray(payload.feedback_readability_region_ids) ? payload.feedback_readability_region_ids.length : 0,
        carryoverCount: Array.isArray(payload.agent_feedback_carryover_ids) ? payload.agent_feedback_carryover_ids.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        scoreRecordId: payload.score_record_id || "unknown",
        controlRecordId: payload.control_record_id || "unknown",
        generalizationScore: Number(payload.generalization_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiRegionLongLivePlayableMeaningGeneralizationGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_long_live_playable_meaning_generalization_gap_audit;
      if (!payload || payload.schema !== "post_multi_region_long_live_playable_meaning_generalization_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_multi_region_generalization !== false ||
        payload.viewer_generated_long_live_continuity !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_repair_guidance !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      return payload;
    }

    function postMultiRegionLongLivePlayableMeaningGeneralizationGapAuditSummary(frame) {
      const payload = postMultiRegionLongLivePlayableMeaningGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionLongLivePlayableMeaningComprehensionRepair(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_long_live_playable_meaning_comprehension_repair;
      if (!payload || payload.schema !== "multi_region_long_live_playable_meaning_comprehension_repair_projection_v1") return {};
      if (
        payload.viewer_generated_repair_guidance !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      if (!comprehensionRepairPayloadGuardValid(payload)) return {};
      const score = Number(payload.repair_comprehension_score || 0);
      const control = Number(payload.same_source_control_score || 0);
      const advantage = Number(payload.baseline_advantage_score || 0);
      if (Math.abs((score - control) - advantage) > 0.000001) return {};
      return payload;
    }

    function multiRegionLongLivePlayableMeaningComprehensionRepairSummary(frame) {
      const payload = multiRegionLongLivePlayableMeaningComprehensionRepair(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        sourceRecordCount: Number(payload.source_count || 0),
        repairScenarioCount: Number(payload.repair_scenario_count || 0),
        repairGuidanceCount: Number(payload.repair_guidance_count || 0),
        actionRecoveryClosureCount: Number(payload.action_recovery_closure_count || 0),
        feedbackReadabilityRepairCount: Number(payload.feedback_readability_repair_count || 0),
        agentFeedbackCarryoverRepairCount: Number(payload.agent_feedback_carryover_repair_count || 0),
        promptCount: Number(payload.prompt_count || 0),
        responseCount: Number(payload.response_count || 0),
        scoreRecordId: payload.score_record_id || "unknown",
        repairComprehensionScore: Number(payload.repair_comprehension_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postComprehensionRepairHardeningGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_comprehension_repair_hardening_gap_audit;
      if (!payload || payload.schema !== "post_comprehension_repair_hardening_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_repair_guidance !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      const blockedTerms = Array.isArray(payload.blocked_terms) ? payload.blocked_terms : [];
      if (
        selected !== "world-experience-next::cross-session-long-live-playable-meaning-transfer-hardening" &&
        blockedTerms.some((term) => selected.includes(String(term || "").toLowerCase()))
      ) return {};
      return payload;
    }

    function postComprehensionRepairHardeningGapAuditSummary(frame) {
      const payload = postComprehensionRepairHardeningGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function crossSessionLongLivePlayableMeaningTransfer(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.cross_session_long_live_playable_meaning_transfer;
      if (!payload || payload.schema !== "cross_session_long_live_playable_meaning_transfer_projection_v1") return {};
      if (
        payload.viewer_generated_transfer !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.is_authority !== false ||
        payload.display_only !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const score = Number(payload.cross_session_transfer_score || 0);
      const control = Number(payload.same_source_no_transfer_control_score || 0);
      const advantage = Number(payload.baseline_advantage_score || 0);
      if (Math.abs((score - control) - advantage) > 0.000001) return {};
      if (score < 0.88 || control > 0.62 || advantage < 0.25) return {};
      return payload;
    }

    function crossSessionLongLivePlayableMeaningTransferSummary(frame) {
      const payload = crossSessionLongLivePlayableMeaningTransfer(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        sessionBoundaryCount: Number(payload.session_boundary_count || 0),
        transferCount: Number(payload.transfer_count || 0),
        preservationRecordCount: Number(payload.preservation_record_count || 0),
        actionRecoveryTransferCount: Number(payload.action_recovery_transfer_count || 0),
        feedbackReadabilityTransferCount: Number(payload.feedback_readability_transfer_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        score: Number(payload.cross_session_transfer_score || 0),
        sameSourceControlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        transferRecordCount: Array.isArray(payload.transfer_record_ids) ? payload.transfer_record_ids.length : 0,
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postCrossSessionLongLivePlayableMeaningTransferGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_cross_session_long_live_playable_meaning_transfer_gap_audit;
      if (!payload || payload.schema !== "post_cross_session_transfer_gap_audit_projection_v1") return {};
      if (
        payload.viewer_generated_transfer !== false ||
        payload.viewer_generated_gap_status !== false ||
        payload.viewer_generated_candidate_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.viewer_generated_repair_guidance !== false ||
        payload.viewer_generated_comprehension !== false ||
        payload.viewer_generated_action_recovery !== false ||
        payload.viewer_generated_feedback_readability !== false ||
        payload.viewer_generated_agent_feedback !== false ||
        payload.viewer_generated_success !== false ||
        payload.is_authority_state !== false ||
        payload.display_only !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::multi-session-long-live-playable-meaning-retention-hardening") {
        return {};
      }
      const blockedTerms = Array.isArray(payload.blocked_terms) ? payload.blocked_terms : [];
      if (blockedTerms.some((term) => selected.includes(String(term || "").toLowerCase()))) return {};
      const selectedScore = Number(payload.selected_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const transferScore = Number(payload.cross_session_transfer_score || 0);
      const controlScore = Number(payload.same_source_no_transfer_control_score || 0);
      const advantageScore = Number(payload.baseline_advantage_score || 0);
      if (selectedScore < 90 || scoreMargin < 20) return {};
      if (transferScore < 0.88 || controlScore > 0.62 || advantageScore < 0.25) return {};
      if (
        Number(payload.gap_count || 0) < 6 ||
        Number(payload.candidate_count || 0) < 6 ||
        Number(payload.score_count || 0) < 6
      ) return {};
      return payload;
    }

    function postCrossSessionLongLivePlayableMeaningTransferGapAuditSummary(frame) {
      const payload = postCrossSessionLongLivePlayableMeaningTransferGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        crossSessionTransferScore: Number(payload.cross_session_transfer_score || 0),
        sameSourceControlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        crossSessionReportDigestPrefix: String(payload.cross_session_transfer_report_digest || "unknown").slice(0, 19),
        crossSessionSourceBundleDigestPrefix: String(payload.cross_session_transfer_source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postCrossSessionConsequenceFeedbackTransferGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_cross_session_consequence_feedback_meaning_transfer_gap_audit;
      if (!payload || payload.schema !== "post_cross_session_consequence_feedback_meaning_transfer_gap_audit_projection_v1") return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::multi-session-consequence-feedback-meaning-retention-hardening") {
        return {};
      }
      const blockedTerms = Array.isArray(payload.blocked_terms) ? payload.blocked_terms : [];
      if (blockedTerms.some((term) => selected.includes(String(term || "").toLowerCase()))) return {};
      for (const term of ["viewer-polish", "real-planet", "physics", "rendering"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const transferScore = Number(payload.transfer_score || 0);
      const controlScore = Number(payload.same_source_no_transfer_control_score || 0);
      const advantageScore = Number(payload.baseline_advantage_score || 0);
      if (selectedScore < 90 || secondBestScore < 0 || scoreMargin < 20) return {};
      if (transferScore < 0.88 || controlScore > 0.62 || advantageScore < 0.25) return {};
      if (
        Number(payload.source_count || 0) < 19 ||
        Number(payload.gap_count || 0) < 6 ||
        Number(payload.candidate_count || 0) < 6 ||
        Number(payload.score_count || 0) < 6
      ) return {};
      return payload;
    }

    function postCrossSessionConsequenceFeedbackTransferGapAuditSummary(frame) {
      const payload = postCrossSessionConsequenceFeedbackTransferGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        transferScore: Number(payload.transfer_score || 0),
        sameSourceControlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        crossSessionReportDigestPrefix: String(payload.cross_session_consequence_feedback_transfer_report_digest || "unknown").slice(0, 19),
        crossSessionSourceBundleDigestPrefix: String(payload.cross_session_consequence_feedback_transfer_source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiSessionLongLivePlayableMeaningRetention(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_session_long_live_playable_meaning_retention;
      if (!payload || payload.schema !== "multi_session_long_live_playable_meaning_retention_projection_v1") return {};
      if (
        payload.viewer_generated_retention !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_next_action !== false ||
        payload.authority !== "display_only" ||
        payload.display_only !== true ||
        payload.is_authority_state !== false
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const selected = String(payload.recommended_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::post-multi-session-retention-gap-audit-and-next-capability-selection") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const score = Number(payload.multi_session_retention_score || 0);
      const control = Number(payload.same_source_transfer_only_static_control_score || 0);
      const advantage = Number(payload.baseline_advantage_score || 0);
      if (Math.abs((score - control) - advantage) > 0.000001) return {};
      if (score < 0.89 || control > 0.62 || advantage < 0.25) return {};
      if (
        Number(payload.followup_session_count || 0) < 3 ||
        Number(payload.retained_transfer_count || 0) < 3 ||
        Number(payload.repair_guidance_reuse_count || 0) < 3 ||
        Number(payload.new_action_recovery_count || 0) < 3 ||
        Number(payload.feedback_readability_retention_count || 0) < 3 ||
        Number(payload.agent_feedback_carryover_stress_count || 0) < 3
      ) return {};
      return payload;
    }

    function multiSessionLongLivePlayableMeaningRetentionSummary(frame) {
      const payload = multiSessionLongLivePlayableMeaningRetention(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        score: Number(payload.multi_session_retention_score || 0),
        sameSourceControlScore: Number(payload.same_source_transfer_only_static_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        followupSessionCount: Number(payload.followup_session_count || 0),
        retainedTransferCount: Number(payload.retained_transfer_count || 0),
        repairGuidanceReuseCount: Number(payload.repair_guidance_reuse_count || 0),
        newActionRecoveryCount: Number(payload.new_action_recovery_count || 0),
        feedbackReadabilityRetentionCount: Number(payload.feedback_readability_retention_count || 0),
        agentFeedbackCarryoverStressCount: Number(payload.agent_feedback_carryover_stress_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        timelineCount: Array.isArray(payload.timeline) ? payload.timeline.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiSessionRetentionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_session_retention_gap_audit;
      if (!payload || payload.schema !== "post_multi_session_retention_gap_audit_projection_v1") return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::retention-guided-open-world-action-diversity-hardening") {
        return {};
      }
      const blockedTerms = Array.isArray(payload.blocked_terms) ? payload.blocked_terms : [];
      if (blockedTerms.some((term) => selected.includes(String(term || "").toLowerCase()))) return {};
      for (const term of ["viewer-polish", "real-planet", "physics", "rendering"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const retentionScore = Number(payload.multi_session_retention_score || 0);
      const controlScore = Number(payload.same_source_transfer_only_static_control_score || 0);
      const advantageScore = Number(payload.baseline_advantage_score || 0);
      if (selectedScore !== 135 || secondBestScore !== 100 || scoreMargin !== 35) return {};
      if (retentionScore < 0.89 || controlScore > 0.62 || advantageScore < 0.25) return {};
      if (
        Number(payload.source_count || 0) !== 31 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6
      ) return {};
      if (
        !Array.isArray(payload.required_gap_ids) ||
        payload.required_gap_ids.length !== 6 ||
        !Array.isArray(payload.required_candidate_ids) ||
        payload.required_candidate_ids.length !== 6 ||
        !Array.isArray(payload.source_record_ids) ||
        payload.source_record_ids.length !== 31
      ) return {};
      return payload;
    }

    function postMultiSessionRetentionGapAuditSummary(frame) {
      const payload = postMultiSessionRetentionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        blockedTermCount: Array.isArray(payload.blocked_terms) ? payload.blocked_terms.length : 0,
        multiSessionRetentionScore: Number(payload.multi_session_retention_score || 0),
        sameSourceControlScore: Number(payload.same_source_transfer_only_static_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        retentionReportDigestPrefix: String(payload.multi_session_retention_report_digest || "unknown").slice(0, 19),
        retentionSourceBundleDigestPrefix: String(payload.multi_session_retention_source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function retentionGuidedActionDiversity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.retention_guided_action_diversity;
      if (!payload || payload.schema !== "retention_guided_action_diversity_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.viewer_generated_action_diversity !== false ||
        payload.viewer_generated_guidance !== false ||
        payload.viewer_generated_feedback !== false ||
        payload.viewer_generated_consequence !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (next !== "world-experience-next::post-retention-guided-open-world-action-diversity-gap-audit-and-next-capability-selection") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      const actionCount = Number(payload.action_count || 0);
      const categoryCount = Number(payload.action_category_count || 0);
      const regionCount = Number(payload.region_count || 0);
      const score = Number(payload.diversity_score || 0);
      const control = Number(payload.repeated_retention_control_score || 0);
      const advantage = Number(payload.baseline_advantage || 0);
      if (actionCount < 6 || categoryCount < 4 || regionCount < 3) return {};
      if (score < 0.88 || control > 0.58 || advantage < 0.25) return {};
      if (Math.abs((score - control) - advantage) > 0.000001) return {};
      if (!Array.isArray(payload.action_summaries) || payload.action_summaries.length < actionCount) return {};
      const requiredSummaryKeys = ["action_id", "region_id", "action_category", "guidance_record_ids", "consequence_record_ids", "feedback_expectation_record_ids"];
      for (const summary of payload.action_summaries) {
        for (const key of requiredSummaryKeys) {
          if (!(key in summary)) return {};
        }
      }
      for (const key of ["source_bundle_digest", "audit_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function retentionGuidedActionDiversitySummary(frame) {
      const payload = retentionGuidedActionDiversity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        actionCount: Number(payload.action_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        regionCount: Number(payload.region_count || 0),
        diversityScore: Number(payload.diversity_score || 0),
        repeatedRetentionControlScore: Number(payload.repeated_retention_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        actionSummaryCount: Array.isArray(payload.action_summaries) ? payload.action_summaries.length : 0,
        blockedBoundaryFlagCount: Array.isArray(payload.blocked_boundary_flags) ? payload.blocked_boundary_flags.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        auditDigestPrefix: String(payload.audit_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postRetentionGuidedActionDiversityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_retention_guided_action_diversity_gap_audit;
      if (!payload || payload.schema !== "post_retention_guided_action_diversity_gap_audit_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::longer-retention-guided-open-world-action-diversity-continuity-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const blockedIds = Array.isArray(payload.blocked_candidate_ids) ? payload.blocked_candidate_ids : [];
      const blockedText = blockedIds.join(" ").toLowerCase();
      for (const requiredBlockedTerm of ["repeat-retention", "viewer-polish", "real-planet", "production-pilot"]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const diversityScore = Number(payload.action_diversity_score || 0);
      const controlScore = Number(payload.repeated_retention_control_score || 0);
      const advantageScore = Number(payload.baseline_advantage || 0);
      if (selectedScore !== 102 || secondBestScore !== 92 || scoreMargin !== 10) return {};
      if (diversityScore < 0.88 || controlScore > 0.58 || advantageScore < 0.25) return {};
      if (Math.abs((diversityScore - controlScore) - advantageScore) > 0.000001) return {};
      if (
        Number(payload.source_count || 0) !== 30 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6
      ) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 6) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length < 4) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postRetentionGuidedActionDiversityGapAuditSummary(frame) {
      const payload = postRetentionGuidedActionDiversityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        actionDiversityScore: Number(payload.action_diversity_score || 0),
        repeatedRetentionControlScore: Number(payload.repeated_retention_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        blockedCandidateCount: Array.isArray(payload.blocked_candidate_ids) ? payload.blocked_candidate_ids.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerRetentionGuidedActionDiversityContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_retention_guided_action_diversity_continuity;
      if (!payload || payload.schema !== "longer_retention_guided_action_diversity_continuity_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.viewer_generated_longer_continuity !== false ||
        payload.viewer_generated_action_diversity !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::post-longer-retention-guided-open-world-action-diversity-continuity-gap-audit-and-next-capability-selection") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      const score = Number(payload.longer_retention_guided_action_diversity_continuity_score || 0);
      const baselineAdvantage = Number(payload.baseline_advantage || 0);
      const bestControl = Number(payload.best_control_score || 0);
      const windowCount = Number(payload.window_count || 0);
      const actionCount = Number(payload.action_count || 0);
      const categoryCount = Number(payload.action_category_count || 0);
      const regionCount = Number(payload.region_count || 0);
      const carryoverCount = Number(payload.carryover_count || 0);
      const controlCount = Number(payload.control_count || 0);
      if (score < 0.86 || baselineAdvantage < 0.28 || bestControl > 0.58) return {};
      if (windowCount !== 6 || actionCount < 12 || categoryCount < 6 || regionCount < 4 || carryoverCount !== 5 || controlCount !== 3) return {};
      if (!Array.isArray(payload.window_summaries) || payload.window_summaries.length !== 6) return {};
      if (!Array.isArray(payload.control_summaries) || payload.control_summaries.length !== 3) return {};
      const requiredControls = new Set([
        "control::repeat-retention-only-long-window",
        "control::short-action-diversity-replay-only",
        "control::transfer-only-without-action-diversity"
      ]);
      for (const control of payload.control_summaries) {
        if (!requiredControls.has(control.control_id)) return {};
        if (Number(control.control_score || 0) > 0.58) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerRetentionGuidedActionDiversityContinuitySummary(frame) {
      const payload = longerRetentionGuidedActionDiversityContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedActionId: payload.selected_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        score: Number(payload.longer_retention_guided_action_diversity_continuity_score || 0),
        enabledScore: Number(payload.enabled_score_without_baseline || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sourceCount: Number(payload.source_count || 0),
        windowCount: Number(payload.window_count || 0),
        actionCount: Number(payload.action_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        regionCount: Number(payload.region_count || 0),
        carryoverCount: Number(payload.carryover_count || 0),
        controlCount: Number(payload.control_count || 0),
        windowSummaryCount: Array.isArray(payload.window_summaries) ? payload.window_summaries.length : 0,
        controlSummaryCount: Array.isArray(payload.control_summaries) ? payload.control_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerConsequenceFeedbackActionDiversityContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_consequence_feedback_retention_guided_action_diversity_continuity;
      if (
        !payload ||
        payload.schema !== "longer_consequence_feedback_retention_guided_action_diversity_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.viewer_generated_longer_consequence_feedback_continuity !== false ||
        payload.viewer_generated_action_diversity !== false ||
        payload.viewer_generated_score !== false ||
        payload.viewer_generated_selection !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-longer-consequence-feedback-retention-guided-action-diversity-continuity-gap-audit-and-next-capability-selection"
      ) {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      const score = Number(payload.longer_consequence_feedback_retention_guided_action_diversity_continuity_score || 0);
      const baselineAdvantage = Number(payload.baseline_advantage || 0);
      const bestControl = Number(payload.best_control_score || 0);
      const windowCount = Number(payload.window_count || 0);
      const actionCount = Number(payload.action_count || 0);
      const categoryCount = Number(payload.action_category_count || 0);
      const regionCount = Number(payload.region_count || 0);
      const carryoverCount = Number(payload.carryover_count || 0);
      const controlCount = Number(payload.control_count || 0);
      if (score < 0.86 || baselineAdvantage < 0.28 || bestControl > 0.58) return {};
      if (windowCount !== 6 || actionCount < 12 || categoryCount < 6 || regionCount < 4 || carryoverCount !== 5 || controlCount !== 3) return {};
      if (!Array.isArray(payload.window_summaries) || payload.window_summaries.length !== 6) return {};
      if (!Array.isArray(payload.control_summaries) || payload.control_summaries.length !== 3) return {};
      const requiredControls = new Set([
        "control::repeat-consequence-feedback-retention-only-long-window",
        "control::short-action-diversity-replay-only",
        "control::transfer-only-without-retained-action-diversity"
      ]);
      for (const control of payload.control_summaries) {
        if (!requiredControls.has(control.control_id)) return {};
        if (Number(control.control_score || 0) > 0.58) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerConsequenceFeedbackActionDiversityContinuitySummary(frame) {
      const payload = longerConsequenceFeedbackActionDiversityContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedActionId: payload.selected_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        score: Number(payload.longer_consequence_feedback_retention_guided_action_diversity_continuity_score || 0),
        enabledScore: Number(payload.enabled_score_without_baseline || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        sourceCount: Number(payload.source_count || 0),
        windowCount: Number(payload.window_count || 0),
        actionCount: Number(payload.action_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        regionCount: Number(payload.region_count || 0),
        carryoverCount: Number(payload.carryover_count || 0),
        controlCount: Number(payload.control_count || 0),
        windowSummaryCount: Array.isArray(payload.window_summaries) ? payload.window_summaries.length : 0,
        controlSummaryCount: Array.isArray(payload.control_summaries) ? payload.control_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerRetentionGuidedActionDiversityContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_retention_guided_action_diversity_continuity_gap_audit;
      if (!payload || payload.schema !== "post_longer_retention_guided_action_diversity_continuity_gap_audit_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::multi-region-retention-guided-action-diversity-generalization-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const repeatScore = Number(payload.repeat_score || 0);
      const transferOnlyScore = Number(payload.transfer_only_score || 0);
      const viewerPolishScore = Number(payload.viewer_polish_score || 0);
      const realRenderingScore = Number(payload.real_rendering_score || 0);
      const productionExternalScore = Number(payload.production_external_score || 0);
      if (selectedScore !== 123 || secondBestScore !== 64 || scoreMargin !== 59) return {};
      if (repeatScore > 65 || transferOnlyScore > 60 || viewerPolishScore > 0 || realRenderingScore > 0 || productionExternalScore > 0) return {};
      if (
        Number(payload.source_count || 0) !== 42 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6 ||
        Number(payload.blocked_candidate_count || 0) !== 5
      ) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 6) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length !== 5) return {};
      const blockedText = payload.blocked_candidate_ids.join(" ").toLowerCase();
      for (const requiredBlockedTerm of ["repeat-longer", "transfer-only", "viewer-polish", "real-planet", "production-pilot"]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerRetentionGuidedActionDiversityContinuityGapAuditSummary(frame) {
      const payload = postLongerRetentionGuidedActionDiversityContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        repeatScore: Number(payload.repeat_score || 0),
        transferOnlyScore: Number(payload.transfer_only_score || 0),
        viewerPolishScore: Number(payload.viewer_polish_score || 0),
        realRenderingScore: Number(payload.real_rendering_score || 0),
        productionExternalScore: Number(payload.production_external_score || 0),
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerConsequenceFeedbackActionDiversityContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_consequence_feedback_retention_guided_action_diversity_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_longer_consequence_feedback_retention_guided_action_diversity_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-region-consequence-feedback-retention-guided-action-diversity-generalization-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const repeatScore = Number(payload.repeat_score || 0);
      const transferOnlyScore = Number(payload.transfer_only_score || 0);
      const viewerPolishScore = Number(payload.viewer_polish_score || 0);
      const realRenderingScore = Number(payload.real_rendering_score || 0);
      const productionExternalScore = Number(payload.production_external_score || 0);
      const analyticsScore = Number(payload.analytics_score || 0);
      if (selectedScore !== 126 || secondBestScore !== 63 || scoreMargin !== 63) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        repeatScore > 70 ||
        transferOnlyScore > 65 ||
        viewerPolishScore > 0 ||
        realRenderingScore > 0 ||
        productionExternalScore > 0 ||
        analyticsScore > 0
      ) return {};
      if (
        Number(payload.previous_continuity_score || 0) < 0.86 ||
        Number(payload.previous_baseline_advantage || 0) < 0.28
      ) return {};
      if (
        Number(payload.source_count || 0) !== 27 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 7 ||
        Number(payload.score_count || 0) !== 7 ||
        Number(payload.blocked_candidate_count || 0) !== 6
      ) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 7) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length !== 6) return {};
      const blockedText = payload.blocked_candidate_ids.join(" ").toLowerCase();
      for (const requiredBlockedTerm of [
        "repeat-longer",
        "transfer-only",
        "viewer-polish",
        "real-rendering",
        "production-pilot",
        "production-analytics",
      ]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerConsequenceFeedbackActionDiversityContinuityGapAuditSummary(frame) {
      const payload = postLongerConsequenceFeedbackActionDiversityContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        repeatScore: Number(payload.repeat_score || 0),
        transferOnlyScore: Number(payload.transfer_only_score || 0),
        viewerPolishScore: Number(payload.viewer_polish_score || 0),
        realRenderingScore: Number(payload.real_rendering_score || 0),
        productionExternalScore: Number(payload.production_external_score || 0),
        analyticsScore: Number(payload.analytics_score || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionConsequenceFeedbackActionDiversityGeneralization(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_consequence_feedback_retention_guided_action_diversity_generalization;
      if (
        !payload ||
        payload.schema !==
          "multi_region_consequence_feedback_retention_guided_action_diversity_generalization_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const current = String(payload.current_action_id || "").toLowerCase();
      if (
        current !==
        "world-experience-next::multi-region-consequence-feedback-retention-guided-action-diversity-generalization-hardening"
      ) return {};
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-region-consequence-feedback-retention-guided-action-diversity-generalization-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (next.includes(term)) return {};
      }
      const regionCount = Number(payload.region_count || 0);
      const coveredPairs = Number(payload.covered_region_action_pairs || 0);
      const transitionCount = Number(payload.region_transition_count || 0);
      const retainedGuidance = Number(payload.retained_consequence_feedback_guidance_rate || 0);
      const actionTransfer = Number(payload.action_diversity_transfer_rate || 0);
      const consequenceMeaning = Number(payload.consequence_meaning_transfer_rate || 0);
      const feedbackReadability = Number(payload.feedback_readability_rate || 0);
      const transitionMeaning = Number(payload.transition_meaning_reuse_rate || 0);
      const carryover = Number(payload.agent_feedback_carryover_rate || 0);
      const score = Number(payload.generalization_score || 0);
      const bestControl = Number(payload.best_control_score || 0);
      const baselineAdvantage = Number(payload.baseline_advantage || 0);
      if (regionCount < 4 || coveredPairs < 24 || transitionCount < 6) return {};
      if (
        retainedGuidance < 0.88 ||
        actionTransfer < 0.86 ||
        consequenceMeaning < 0.85 ||
        feedbackReadability < 0.84 ||
        transitionMeaning < 0.82 ||
        carryover < 0.80
      ) return {};
      if (score < 0.90 || bestControl > 0.58 || baselineAdvantage < 0.32) return {};
      if (!Array.isArray(payload.region_summaries) || payload.region_summaries.length < 4) return {};
      if (!Array.isArray(payload.transition_summaries) || payload.transition_summaries.length < 6) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionConsequenceFeedbackActionDiversityGeneralizationGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::longer-multi-region-consequence-feedback-retention-guided-action-diversity-generalization-continuity-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const repeatScore = Number(payload.repeat_score || 0);
      const singleRegionScore = Number(payload.single_region_score || 0);
      const viewerPolishScore = Number(payload.viewer_polish_score || 0);
      const realRenderingScore = Number(payload.real_rendering_score || 0);
      const productionExternalScore = Number(payload.production_external_score || 0);
      const analyticsScore = Number(payload.analytics_score || 0);
      if (selectedScore !== 126 || secondBestScore !== 68 || scoreMargin !== 58) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        repeatScore > 75 ||
        singleRegionScore > 70 ||
        viewerPolishScore > 0 ||
        realRenderingScore > 0 ||
        productionExternalScore > 0 ||
        analyticsScore > 0
      ) return {};
      if (
        Number(payload.previous_generalization_score || 0) < 0.9 ||
        Number(payload.previous_best_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_region_count || 0) < 4 ||
        Number(payload.previous_region_action_pair_count || 0) < 24 ||
        Number(payload.previous_transition_count || 0) < 6
      ) return {};
      if (
        Number(payload.source_count || 0) !== 16 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 7 ||
        Number(payload.score_count || 0) !== 7 ||
        Number(payload.blocked_candidate_count || 0) !== 6
      ) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 7) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length !== 6) return {};
      const blockedText = payload.blocked_candidate_ids.join(" ").toLowerCase();
      for (const requiredBlockedTerm of [
        "repeat-multi-region",
        "single-region",
        "viewer-polish",
        "real-rendering",
        "production-pilot",
        "production-analytics",
      ]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionConsequenceFeedbackActionDiversityGeneralizationGapAuditSummary(frame) {
      const payload = postMultiRegionConsequenceFeedbackActionDiversityGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousGeneralizationScore: Number(payload.previous_generalization_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousRegionActionPairCount: Number(payload.previous_region_action_pair_count || 0),
        previousTransitionCount: Number(payload.previous_transition_count || 0),
        repeatScore: Number(payload.repeat_score || 0),
        singleRegionScore: Number(payload.single_region_score || 0),
        viewerPolishScore: Number(payload.viewer_polish_score || 0),
        realRenderingScore: Number(payload.real_rendering_score || 0),
        productionExternalScore: Number(payload.production_external_score || 0),
        analyticsScore: Number(payload.analytics_score || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerMultiRegionConsequenceFeedbackActionDiversityGeneralizationContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_continuity;
      if (
        !payload ||
        payload.schema !==
          "longer_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const current = String(payload.current_action_id || "").toLowerCase();
      if (
        current !==
        "world-experience-next::longer-multi-region-consequence-feedback-retention-guided-action-diversity-generalization-continuity-hardening"
      ) return {};
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-longer-multi-region-consequence-feedback-retention-guided-action-diversity-generalization-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (next.includes(term)) return {};
      }
      const windowCount = Number(payload.window_count || 0);
      const coveredTickSpan = Number(payload.covered_tick_span || 0);
      const regionCount = Number(payload.region_count || 0);
      const coveredPairs = Number(payload.covered_region_action_pairs || 0);
      const categoryCount = Number(payload.action_category_count || 0);
      const transitionCount = Number(payload.transition_meaning_record_count || 0);
      const retainedGuidance = Number(payload.retained_consequence_feedback_guidance_rate || 0);
      const consequenceMeaning = Number(payload.consequence_meaning_transfer_rate || 0);
      const feedbackReadability = Number(payload.feedback_readability_rate || 0);
      const transitionMeaning = Number(payload.transition_meaning_reuse_rate || 0);
      const carryover = Number(payload.agent_feedback_carryover_rate || 0);
      const carryoverCount = Number(payload.agent_feedback_carryover_count || 0);
      const score = Number(payload.continuity_score || 0);
      const bestControl = Number(payload.best_control_score || 0);
      const baselineAdvantage = Number(payload.baseline_advantage || 0);
      if (windowCount < 6 || coveredTickSpan < 1536) return {};
      if (regionCount < 4 || coveredPairs < 24 || categoryCount < 6 || transitionCount < 10) return {};
      if (
        retainedGuidance < 0.88 ||
        consequenceMeaning < 0.85 ||
        feedbackReadability < 0.84 ||
        transitionMeaning < 0.82 ||
        carryover < 0.80 ||
        carryoverCount < 5
      ) return {};
      if (score < 0.90 || bestControl > 0.58 || baselineAdvantage < 0.32) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerMultiRegionConsequenceFeedbackActionDiversityGeneralizationContinuitySummary(frame) {
      const payload = longerMultiRegionConsequenceFeedbackActionDiversityGeneralizationContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        currentActionId: payload.current_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        regionCount: Number(payload.region_count || 0),
        coveredRegionActionPairs: Number(payload.covered_region_action_pairs || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        transitionCount: Number(payload.transition_meaning_record_count || 0),
        retainedConsequenceFeedbackGuidanceRate: Number(payload.retained_consequence_feedback_guidance_rate || 0),
        consequenceMeaningTransferRate: Number(payload.consequence_meaning_transfer_rate || 0),
        feedbackReadabilityRate: Number(payload.feedback_readability_rate || 0),
        transitionMeaningReuseRate: Number(payload.transition_meaning_reuse_rate || 0),
        agentFeedbackCarryoverRate: Number(payload.agent_feedback_carryover_rate || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        continuityScore: Number(payload.continuity_score || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerMultiRegionConsequenceFeedbackActionDiversityGeneralizedContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_longer_multi_region_consequence_feedback_retention_guided_action_diversity_generalization_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::cross-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 139 || secondBestScore !== 45 || scoreMargin !== 94) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        Number(payload.previous_continuity_score || 0) < 0.94 ||
        Number(payload.previous_enabled_score || 0) < 0.93 ||
        Number(payload.previous_best_control_score || 1) > 0.56 ||
        Number(payload.previous_baseline_advantage || 0) < 0.36 ||
        Number(payload.previous_window_count || 0) < 6 ||
        Number(payload.previous_covered_tick_span || 0) < 1536 ||
        Number(payload.previous_region_count || 0) < 4 ||
        Number(payload.previous_region_action_pair_count || 0) < 24 ||
        Number(payload.previous_action_category_count || 0) < 6 ||
        Number(payload.previous_transition_meaning_record_count || 0) < 10 ||
        Number(payload.previous_agent_feedback_carryover_count || 0) < 5
      ) return {};
      if (
        Number(payload.source_count || 0) !== 34 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 7 ||
        Number(payload.score_count || 0) !== 7 ||
        Number(payload.blocked_candidate_count || 0) !== 6
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerMultiRegionConsequenceFeedbackActionDiversityGeneralizedContinuityGapAuditSummary(frame) {
      const payload = postLongerMultiRegionConsequenceFeedbackActionDiversityGeneralizedContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousRegionActionPairCount: Number(payload.previous_region_action_pair_count || 0),
        previousActionCategoryCount: Number(payload.previous_action_category_count || 0),
        previousTransitionMeaningRecordCount: Number(payload.previous_transition_meaning_record_count || 0),
        previousAgentFeedbackCarryoverCount: Number(payload.previous_agent_feedback_carryover_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionConsequenceFeedbackActionDiversityGeneralizationSummary(frame) {
      const payload = multiRegionConsequenceFeedbackActionDiversityGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        currentActionId: payload.current_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        regionCount: Number(payload.region_count || 0),
        coveredRegionActionPairs: Number(payload.covered_region_action_pairs || 0),
        transitionCount: Number(payload.region_transition_count || 0),
        retainedConsequenceFeedbackGuidanceRate: Number(payload.retained_consequence_feedback_guidance_rate || 0),
        actionDiversityTransferRate: Number(payload.action_diversity_transfer_rate || 0),
        consequenceMeaningTransferRate: Number(payload.consequence_meaning_transfer_rate || 0),
        feedbackReadabilityRate: Number(payload.feedback_readability_rate || 0),
        transitionMeaningReuseRate: Number(payload.transition_meaning_reuse_rate || 0),
        agentFeedbackCarryoverRate: Number(payload.agent_feedback_carryover_rate || 0),
        generalizationScore: Number(payload.generalization_score || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        regionSummaryCount: Array.isArray(payload.region_summaries) ? payload.region_summaries.length : 0,
        transitionSummaryCount: Array.isArray(payload.transition_summaries) ? payload.transition_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionRetentionGuidedActionDiversityGeneralization(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_retention_guided_action_diversity_generalization;
      if (!payload || payload.schema !== "multi_region_retention_guided_action_diversity_generalization_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_source_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::multi-region-retention-guided-action-diversity-generalization-hardening") {
        return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::post-multi-region-retention-guided-action-diversity-generalization-gap-audit-and-next-capability-selection") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      const regionCount = Number(payload.region_count || 0);
      const coveredPairs = Number(payload.covered_region_action_pairs || 0);
      const transitionCount = Number(payload.region_transition_count || 0);
      const guidance = Number(payload.retained_guidance_transfer_rate || 0);
      const recovery = Number(payload.action_recovery_cross_region_rate || 0);
      const readability = Number(payload.feedback_readability_cross_region_rate || 0);
      const carryover = Number(payload.agent_feedback_carryover_rate || 0);
      const score = Number(payload.generalization_score || 0);
      const bestControl = Number(payload.best_control_score || 0);
      const baselineAdvantage = Number(payload.baseline_advantage || 0);
      if (regionCount < 4 || coveredPairs < 24 || transitionCount < 6) return {};
      if (guidance < 0.86 || recovery < 0.84 || readability < 0.82 || carryover < 0.80) return {};
      if (score < 0.88 || bestControl > 0.58 || baselineAdvantage < 0.30) return {};
      if (!Array.isArray(payload.region_summaries) || payload.region_summaries.length < 4) return {};
      if (!Array.isArray(payload.transition_summaries) || payload.transition_summaries.length < 6) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiRegionRetentionGuidedActionDiversityGeneralizationSummary(frame) {
      const payload = multiRegionRetentionGuidedActionDiversityGeneralization(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedSourceActionId: payload.selected_source_action_id || "unknown",
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        sourceCount: Number(payload.source_count || 0),
        regionCount: Number(payload.region_count || 0),
        coveredRegionActionPairs: Number(payload.covered_region_action_pairs || 0),
        transitionCount: Number(payload.region_transition_count || 0),
        retainedGuidanceTransferRate: Number(payload.retained_guidance_transfer_rate || 0),
        actionRecoveryCrossRegionRate: Number(payload.action_recovery_cross_region_rate || 0),
        feedbackReadabilityCrossRegionRate: Number(payload.feedback_readability_cross_region_rate || 0),
        agentFeedbackCarryoverRate: Number(payload.agent_feedback_carryover_rate || 0),
        generalizationScore: Number(payload.generalization_score || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        regionSummaryCount: Array.isArray(payload.region_summaries) ? payload.region_summaries.length : 0,
        transitionSummaryCount: Array.isArray(payload.transition_summaries) ? payload.transition_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiRegionRetentionGuidedActionDiversityGeneralizationGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_retention_guided_action_diversity_generalization_gap_audit;
      if (!payload || payload.schema !== "post_multi_region_retention_guided_action_diversity_generalization_gap_audit_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (selected !== "world-experience-next::multi-region-retention-guided-action-consequence-feedback-meaning-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const secondBestCandidateId = String(payload.second_best_candidate_id || "").toLowerCase();
      if (secondBestCandidateId !== "world-experience-next::repeat-multi-region-action-diversity-generalization-proof") {
        return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      const repeatGeneralizationScore = Number(payload.repeat_generalization_score || 0);
      const retentionOnlyScore = Number(payload.retention_only_score || 0);
      const transferOnlyScore = Number(payload.transfer_only_score || 0);
      const viewerRealRenderingScore = Number(payload.viewer_real_rendering_score || 0);
      const productionExternalScore = Number(payload.production_external_score || 0);
      if (selectedScore !== 121 || secondBestScore !== 42 || scoreMargin < 35) return {};
      if (
        repeatGeneralizationScore > 55 ||
        retentionOnlyScore > 45 ||
        transferOnlyScore > 10 ||
        viewerRealRenderingScore > 0 ||
        productionExternalScore > 0
      ) return {};
      if (
        Number(payload.source_count || 0) < 49 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6 ||
        Number(payload.blocked_candidate_count || 0) !== 5
      ) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 6) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length !== 5) return {};
      const blockedText = payload.blocked_candidate_ids.join(" ").toLowerCase();
      for (const requiredBlockedTerm of ["repeat-multi-region", "retention-guided", "transfer-only", "viewer-polish", "real-rendering", "production-pilot"]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionRetentionGuidedActionDiversityGeneralizationGapAuditSummary(frame) {
      const payload = postMultiRegionRetentionGuidedActionDiversityGeneralizationGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        repeatGeneralizationScore: Number(payload.repeat_generalization_score || 0),
        retentionOnlyScore: Number(payload.retention_only_score || 0),
        transferOnlyScore: Number(payload.transfer_only_score || 0),
        viewerRealRenderingScore: Number(payload.viewer_real_rendering_score || 0),
        productionExternalScore: Number(payload.production_external_score || 0),
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiRegionRetentionGuidedActionConsequenceFeedbackMeaning(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_retention_guided_action_consequence_feedback_meaning;
      if (!payload || payload.schema !== "multi_region_retention_guided_action_consequence_feedback_meaning_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !== "world-experience-next::post-multi-region-consequence-feedback-meaning-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (Number(payload.hardening_score || 0) < 0.88) return {};
      if (Number(payload.best_same_source_control_score || 0) > 0.58) return {};
      if (Number(payload.baseline_advantage || 0) < 0.30) return {};
      if (
        Number(payload.region_count || 0) !== 4 ||
        Number(payload.action_category_count || 0) !== 6 ||
        Number(payload.consequence_record_count || 0) !== 24 ||
        Number(payload.feedback_meaning_record_count || 0) !== 24 ||
        Number(payload.transition_meaning_record_count || 0) !== 6 ||
        Number(payload.agent_feedback_carryover_count || 0) < 8
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiRegionRetentionGuidedActionConsequenceFeedbackMeaningSummary(frame) {
      const payload = multiRegionRetentionGuidedActionConsequenceFeedbackMeaning(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        hardeningScore: Number(payload.hardening_score || 0),
        bestControlScore: Number(payload.best_same_source_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        regionCount: Number(payload.region_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        consequenceRecordCount: Number(payload.consequence_record_count || 0),
        feedbackMeaningRecordCount: Number(payload.feedback_meaning_record_count || 0),
        transitionMeaningRecordCount: Number(payload.transition_meaning_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiRegionConsequenceFeedbackMeaningGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_consequence_feedback_meaning_gap_audit;
      if (!payload || payload.schema !== "post_multi_region_consequence_feedback_meaning_gap_audit_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !== "world-experience-next::longer-multi-region-consequence-feedback-meaning-continuity-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (selected.includes(term)) return {};
      }
      const secondBestCandidateId = String(payload.second_best_candidate_id || "").toLowerCase();
      if (
        secondBestCandidateId !== "world-experience-next::repeat-multi-region-consequence-feedback-meaning-proof"
      ) return {};
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 130 || secondBestScore !== 39 || scoreMargin < 35) return {};
      if (
        Number(payload.repeat_consequence_feedback_score || 0) > 50 ||
        Number(payload.action_only_score || 0) > 15 ||
        Number(payload.viewer_real_rendering_score || 0) > 0 ||
        Number(payload.production_external_score || 0) > 0 ||
        Number(payload.analytics_score || 0) > 0
      ) return {};
      if (
        Number(payload.source_count || 0) < 63 ||
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6 ||
        Number(payload.blocked_candidate_count || 0) !== 5
      ) return {};
      if (Number(payload.hardening_score || 0) < 0.88) return {};
      if (Number(payload.best_same_source_control_score || 0) > 0.58) return {};
      if (Number(payload.baseline_advantage || 0) < 0.30) return {};
      if (!Array.isArray(payload.candidate_summaries) || payload.candidate_summaries.length !== 6) return {};
      if (!Array.isArray(payload.blocked_candidate_ids) || payload.blocked_candidate_ids.length !== 5) return {};
      const blockedText = payload.blocked_candidate_ids.join(" ").toLowerCase();
      for (const requiredBlockedTerm of ["repeat-multi-region", "action-diversity-only", "viewer-polish", "real-rendering", "production-pilot", "analytics"]) {
        if (!blockedText.includes(requiredBlockedTerm)) return {};
      }
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionConsequenceFeedbackMeaningGapAuditSummary(frame) {
      const payload = postMultiRegionConsequenceFeedbackMeaningGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        repeatConsequenceFeedbackScore: Number(payload.repeat_consequence_feedback_score || 0),
        actionOnlyScore: Number(payload.action_only_score || 0),
        viewerRealRenderingScore: Number(payload.viewer_real_rendering_score || 0),
        productionExternalScore: Number(payload.production_external_score || 0),
        analyticsScore: Number(payload.analytics_score || 0),
        hardeningScore: Number(payload.hardening_score || 0),
        consequenceRecordCount: Number(payload.consequence_record_count || 0),
        feedbackMeaningRecordCount: Number(payload.feedback_meaning_record_count || 0),
        transitionMeaningRecordCount: Number(payload.transition_meaning_record_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        candidateSummaryCount: Array.isArray(payload.candidate_summaries) ? payload.candidate_summaries.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerMultiRegionConsequenceFeedbackMeaningContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_multi_region_consequence_feedback_meaning_continuity;
      if (!payload || payload.schema !== "longer_multi_region_consequence_feedback_meaning_continuity_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !== "world-experience-next::post-longer-multi-region-consequence-feedback-meaning-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (Number(payload.continuity_score || 0) < 0.88) return {};
      if (Number(payload.best_same_source_control_score || 0) > 0.58) return {};
      if (Number(payload.baseline_advantage || 0) < 0.30) return {};
      if (
        Number(payload.window_count || 0) !== 6 ||
        Number(payload.covered_tick_span || 0) !== 1536 ||
        Number(payload.region_count || 0) !== 4 ||
        Number(payload.action_category_count || 0) !== 6 ||
        Number(payload.consequence_continuity_record_count || 0) !== 36 ||
        Number(payload.feedback_meaning_continuity_record_count || 0) !== 36 ||
        Number(payload.transition_meaning_continuity_record_count || 0) !== 10 ||
        Number(payload.agent_feedback_carryover_record_count || 0) !== 10
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerMultiRegionConsequenceFeedbackMeaningContinuitySummary(frame) {
      const payload = longerMultiRegionConsequenceFeedbackMeaningContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        continuityScore: Number(payload.continuity_score || 0),
        continuitySignalScore: Number(payload.continuity_signal_score || 0),
        bestControlScore: Number(payload.best_same_source_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        regionCount: Number(payload.region_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        consequenceContinuityRecordCount: Number(payload.consequence_continuity_record_count || 0),
        feedbackMeaningContinuityRecordCount: Number(payload.feedback_meaning_continuity_record_count || 0),
        transitionMeaningContinuityRecordCount: Number(payload.transition_meaning_continuity_record_count || 0),
        agentFeedbackCarryoverRecordCount: Number(payload.agent_feedback_carryover_record_count || 0),
        sourceCount: Number(payload.source_count || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerMultiRegionConsequenceFeedbackMeaningContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_multi_region_consequence_feedback_meaning_continuity_gap_audit;
      if (!payload || payload.schema !== "post_longer_multi_region_consequence_feedback_meaning_continuity_gap_audit_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.selected_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::cross-session-consequence-feedback-meaning-transfer-hardening") return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (Number(payload.selected_score || 0) < 120) return {};
      if (Number(payload.score_margin || 0) < 70) return {};
      if (Number(payload.source_count || 0) < 77) return {};
      if (
        Number(payload.gap_count || 0) !== 6 ||
        Number(payload.candidate_count || 0) !== 6 ||
        Number(payload.score_count || 0) !== 6 ||
        Number(payload.blocked_candidate_count || 0) !== 5
      ) return {};
      if (Number(payload.previous_continuity_score || 0) < 0.88) return {};
      if (Number(payload.previous_baseline_advantage || 0) < 0.30) return {};
      for (const key of ["source_bundle_digest", "selection_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerMultiRegionConsequenceFeedbackMeaningContinuityGapAuditSummary(frame) {
      const payload = postLongerMultiRegionConsequenceFeedbackMeaningContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function crossSessionConsequenceFeedbackMeaningTransfer(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.cross_session_consequence_feedback_meaning_transfer;
      if (!payload || payload.schema !== "cross_session_consequence_feedback_meaning_transfer_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.selected_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::cross-session-consequence-feedback-meaning-transfer-hardening") return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (Number(payload.transfer_score || 0) < 0.88) return {};
      if (Number(payload.same_source_no_transfer_control_score || 1) > 0.62) return {};
      if (Number(payload.baseline_advantage_score || 0) < 0.25) return {};
      if (
        Number(payload.previous_selection_source_count || 0) < 84 ||
        Number(payload.current_source_record_count || 0) < 18 ||
        Number(payload.session_boundary_count || 0) < 2 ||
        Number(payload.transfer_record_count || 0) < 4 ||
        Number(payload.consequence_meaning_transfer_count || 0) < 4 ||
        Number(payload.feedback_meaning_transfer_count || 0) < 4 ||
        Number(payload.transition_meaning_transfer_count || 0) < 3 ||
        Number(payload.agent_feedback_carryover_transfer_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function crossSessionConsequenceFeedbackMeaningTransferSummary(frame) {
      const payload = crossSessionConsequenceFeedbackMeaningTransfer(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        transferScore: Number(payload.transfer_score || 0),
        controlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage_score || 0),
        previousSelectionSourceCount: Number(payload.previous_selection_source_count || 0),
        currentSourceRecordCount: Number(payload.current_source_record_count || 0),
        sessionBoundaryCount: Number(payload.session_boundary_count || 0),
        transferRecordCount: Number(payload.transfer_record_count || 0),
        consequenceMeaningTransferCount: Number(payload.consequence_meaning_transfer_count || 0),
        feedbackMeaningTransferCount: Number(payload.feedback_meaning_transfer_count || 0),
        transitionMeaningTransferCount: Number(payload.transition_meaning_transfer_count || 0),
        agentFeedbackCarryoverTransferCount: Number(payload.agent_feedback_carryover_transfer_count || 0),
        transferRecordIds: Array.isArray(payload.transfer_record_ids) ? payload.transfer_record_ids : [],
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function crossSessionGeneralizedTransfer(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.cross_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer;
      if (!payload || payload.schema !== "cross_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_projection_v1") return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.selected_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::post-cross-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-gap-audit-and-next-capability-selection") return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (Number(payload.transfer_score || 0) < 0.90) return {};
      if (Number(payload.same_source_no_transfer_control_score || 1) > 0.58) return {};
      if (Number(payload.baseline_advantage_score || 0) < 0.30) return {};
      if (
        Number(payload.current_source_record_count || 0) < 30 ||
        Number(payload.session_boundary_count || 0) < 2 ||
        Number(payload.transfer_record_count || 0) < 4 ||
        Number(payload.retained_guidance_transfer_count || 0) < 4 ||
        Number(payload.action_diversity_generalization_transfer_count || 0) < 4 ||
        Number(payload.consequence_meaning_transfer_count || 0) < 4 ||
        Number(payload.feedback_readability_transfer_count || 0) < 4 ||
        Number(payload.transition_meaning_transfer_count || 0) < 4 ||
        Number(payload.agent_feedback_carryover_transfer_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function crossSessionGeneralizedTransferSummary(frame) {
      const payload = crossSessionGeneralizedTransfer(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        transferScore: Number(payload.transfer_score || 0),
        controlScore: Number(payload.same_source_no_transfer_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage_score || 0),
        sourceRecordCount: Number(payload.current_source_record_count || 0),
        sessionBoundaryCount: Number(payload.session_boundary_count || 0),
        transferRecordCount: Number(payload.transfer_record_count || 0),
        retainedGuidanceTransferCount: Number(payload.retained_guidance_transfer_count || 0),
        actionDiversityGeneralizationTransferCount: Number(payload.action_diversity_generalization_transfer_count || 0),
        consequenceMeaningTransferCount: Number(payload.consequence_meaning_transfer_count || 0),
        feedbackReadabilityTransferCount: Number(payload.feedback_readability_transfer_count || 0),
        transitionMeaningTransferCount: Number(payload.transition_meaning_transfer_count || 0),
        agentFeedbackCarryoverTransferCount: Number(payload.agent_feedback_carryover_transfer_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postCrossSessionGeneralizedTransferGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_cross_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_cross_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 151 || secondBestScore !== 104 || scoreMargin !== 47) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        Number(payload.previous_transfer_score || 0) < 0.90 ||
        Number(payload.previous_same_source_no_transfer_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage_score || 0) < 0.30 ||
        Number(payload.previous_session_boundary_count || 0) < 2 ||
        Number(payload.previous_transfer_record_count || 0) < 4 ||
        Number(payload.previous_retained_guidance_transfer_count || 0) < 4 ||
        Number(payload.previous_action_diversity_generalization_transfer_count || 0) < 4 ||
        Number(payload.previous_consequence_meaning_transfer_count || 0) < 4 ||
        Number(payload.previous_feedback_readability_transfer_count || 0) < 4 ||
        Number(payload.previous_transition_meaning_transfer_count || 0) < 4 ||
        Number(payload.previous_agent_feedback_carryover_transfer_count || 0) < 4
      ) return {};
      if (
        Number(payload.source_count || 0) < 40 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postCrossSessionGeneralizedTransferGapAuditSummary(frame) {
      const payload = postCrossSessionGeneralizedTransferGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousTransferScore: Number(payload.previous_transfer_score || 0),
        previousControlScore: Number(payload.previous_same_source_no_transfer_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage_score || 0),
        previousSessionBoundaryCount: Number(payload.previous_session_boundary_count || 0),
        previousTransferRecordCount: Number(payload.previous_transfer_record_count || 0),
        previousRetainedGuidanceTransferCount: Number(payload.previous_retained_guidance_transfer_count || 0),
        previousActionDiversityGeneralizationTransferCount: Number(payload.previous_action_diversity_generalization_transfer_count || 0),
        previousConsequenceMeaningTransferCount: Number(payload.previous_consequence_meaning_transfer_count || 0),
        previousFeedbackReadabilityTransferCount: Number(payload.previous_feedback_readability_transfer_count || 0),
        previousTransitionMeaningTransferCount: Number(payload.previous_transition_meaning_transfer_count || 0),
        previousAgentFeedbackCarryoverTransferCount: Number(payload.previous_agent_feedback_carryover_transfer_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function multiSessionGeneralizedTransferRetention(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention;
      if (
        !payload ||
        payload.schema !==
          "multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.retention_score || 0) < 0.90 ||
        Number(payload.same_source_transfer_only_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage_score || 0) < 0.30 ||
        Number(payload.previous_transfer_score || 0) < 0.90
      ) return {};
      if (
        Number(payload.source_record_count || 0) < 40 ||
        Number(payload.followup_session_count || 0) < 3 ||
        Number(payload.retained_transfer_count || 0) < 4 ||
        Number(payload.retained_guidance_retention_count || 0) < 4 ||
        Number(payload.action_diversity_generalization_retention_count || 0) < 4 ||
        Number(payload.consequence_meaning_retention_count || 0) < 4 ||
        Number(payload.feedback_readability_retention_count || 0) < 4 ||
        Number(payload.transition_meaning_retention_count || 0) < 4 ||
        Number(payload.agent_feedback_carryover_retention_count || 0) < 4
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiSessionGeneralizedTransferRetentionSummary(frame) {
      const payload = multiSessionGeneralizedTransferRetention(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        retentionScore: Number(payload.retention_score || 0),
        controlScore: Number(payload.same_source_transfer_only_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage_score || 0),
        previousTransferScore: Number(payload.previous_transfer_score || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        followupSessionCount: Number(payload.followup_session_count || 0),
        retainedTransferCount: Number(payload.retained_transfer_count || 0),
        retainedGuidanceRetentionCount: Number(payload.retained_guidance_retention_count || 0),
        actionDiversityGeneralizationRetentionCount: Number(payload.action_diversity_generalization_retention_count || 0),
        consequenceMeaningRetentionCount: Number(payload.consequence_meaning_retention_count || 0),
        feedbackReadabilityRetentionCount: Number(payload.feedback_readability_retention_count || 0),
        transitionMeaningRetentionCount: Number(payload.transition_meaning_retention_count || 0),
        agentFeedbackCarryoverRetentionCount: Number(payload.agent_feedback_carryover_retention_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function postMultiSessionGeneralizedTransferRetentionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::longer-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-continuity-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 160 || secondBestScore !== 120 || scoreMargin !== 40) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        Number(payload.previous_retention_score || 0) < 0.90 ||
        Number(payload.previous_same_source_transfer_only_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage_score || 0) < 0.30 ||
        Number(payload.previous_followup_session_count || 0) < 3 ||
        Number(payload.previous_retained_transfer_count || 0) < 4 ||
        Number(payload.previous_retained_guidance_retention_count || 0) < 4 ||
        Number(payload.previous_action_diversity_generalization_retention_count || 0) < 4 ||
        Number(payload.previous_consequence_meaning_retention_count || 0) < 4 ||
        Number(payload.previous_feedback_readability_retention_count || 0) < 4 ||
        Number(payload.previous_transition_meaning_retention_count || 0) < 4 ||
        Number(payload.previous_agent_feedback_carryover_retention_count || 0) < 4
      ) return {};
      if (
        Number(payload.source_count || 0) < 50 ||
        Number(payload.gap_count || 0) !== 8 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiSessionGeneralizedTransferRetentionGapAuditSummary(frame) {
      const payload = postMultiSessionGeneralizedTransferRetentionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        previousControlScore: Number(payload.previous_same_source_transfer_only_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage_score || 0),
        previousFollowupSessionCount: Number(payload.previous_followup_session_count || 0),
        previousRetainedTransferCount: Number(payload.previous_retained_transfer_count || 0),
        previousRetainedGuidanceRetentionCount: Number(payload.previous_retained_guidance_retention_count || 0),
        previousActionDiversityGeneralizationRetentionCount: Number(payload.previous_action_diversity_generalization_retention_count || 0),
        previousConsequenceMeaningRetentionCount: Number(payload.previous_consequence_meaning_retention_count || 0),
        previousFeedbackReadabilityRetentionCount: Number(payload.previous_feedback_readability_retention_count || 0),
        previousTransitionMeaningRetentionCount: Number(payload.previous_transition_meaning_retention_count || 0),
        previousAgentFeedbackCarryoverRetentionCount: Number(payload.previous_agent_feedback_carryover_retention_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postLongerMultiSessionGeneralizedTransferRetentionContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_longer_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_longer_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::multi-region-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-continuity-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 164 || secondBestScore !== 124 || scoreMargin !== 40) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        Number(payload.previous_continuity_score || 0) < 0.94 ||
        Number(payload.previous_enabled_score || 0) < 0.93 ||
        Number(payload.previous_best_control_score || 1) > 0.60 ||
        Number(payload.previous_baseline_advantage || 0) < 0.30 ||
        Number(payload.previous_retention_score || 0) < 0.90 ||
        Number(payload.previous_window_count || 0) < 6 ||
        Number(payload.previous_covered_tick_span || 0) < 1536 ||
        Number(payload.previous_retained_transfer_continuity_count || 0) < 6 ||
        Number(payload.previous_retained_guidance_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_action_diversity_generalization_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_consequence_meaning_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_feedback_readability_retention_continuity_count || 0) < 6 ||
        Number(payload.previous_transition_meaning_retention_continuity_count || 0) < 5 ||
        Number(payload.previous_agent_feedback_carryover_retention_continuity_count || 0) < 5
      ) return {};
      if (
        Number(payload.source_count || 0) < 70 ||
        Number(payload.gap_count || 0) !== 7 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postLongerMultiSessionGeneralizedTransferRetentionContinuityGapAuditSummary(frame) {
      const payload = postLongerMultiSessionGeneralizedTransferRetentionContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousRetainedTransferContinuityCount: Number(payload.previous_retained_transfer_continuity_count || 0),
        previousRetainedGuidanceRetentionContinuityCount: Number(payload.previous_retained_guidance_retention_continuity_count || 0),
        previousActionDiversityGeneralizationRetentionContinuityCount: Number(payload.previous_action_diversity_generalization_retention_continuity_count || 0),
        previousConsequenceMeaningRetentionContinuityCount: Number(payload.previous_consequence_meaning_retention_continuity_count || 0),
        previousFeedbackReadabilityRetentionContinuityCount: Number(payload.previous_feedback_readability_retention_continuity_count || 0),
        previousTransitionMeaningRetentionContinuityCount: Number(payload.previous_transition_meaning_retention_continuity_count || 0),
        previousAgentFeedbackCarryoverRetentionContinuityCount: Number(payload.previous_agent_feedback_carryover_retention_continuity_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiRegionMultiSessionGeneralizedTransferRetentionContinuityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_region_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_gap_audit;
      if (
        !payload ||
        payload.schema !==
          "post_multi_region_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_gap_audit_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const selected = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        selected !==
        "world-experience-next::large-scale-multi-region-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-continuity-stress-and-budget-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (selected.includes(term)) return {};
      }
      const selectedScore = Number(payload.selected_score || 0);
      const secondBestScore = Number(payload.second_best_score || 0);
      const scoreMargin = Number(payload.score_margin || 0);
      if (selectedScore !== 152 || secondBestScore !== 112 || scoreMargin !== 40) return {};
      if (scoreMargin !== selectedScore - secondBestScore) return {};
      if (
        Number(payload.previous_continuity_score || 0) < 0.93 ||
        Number(payload.previous_enabled_score || 0) < 0.92 ||
        Number(payload.previous_best_control_score || 1) > 0.60 ||
        Number(payload.previous_baseline_advantage || 0) < 0.32 ||
        Number(payload.previous_region_count || 0) !== 4 ||
        Number(payload.previous_session_count || 0) !== 3 ||
        Number(payload.previous_region_session_cell_count || 0) !== 12 ||
        Number(payload.previous_window_count || 0) !== 6 ||
        Number(payload.previous_covered_tick_span || 0) !== 1536 ||
        Number(payload.previous_cross_axis_edge_coverage || 0) !== 1
      ) return {};
      if (
        Number(payload.source_count || 0) < 87 ||
        Number(payload.gap_count || 0) !== 7 ||
        Number(payload.candidate_count || 0) !== 8 ||
        Number(payload.score_count || 0) !== 8 ||
        Number(payload.blocked_candidate_count || 0) !== 7
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "selection_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiRegionMultiSessionGeneralizedTransferRetentionContinuityGapAuditSummary(frame) {
      const payload = postMultiRegionMultiSessionGeneralizedTransferRetentionContinuityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousSessionCount: Number(payload.previous_session_count || 0),
        previousRegionSessionCellCount: Number(payload.previous_region_session_cell_count || 0),
        previousWindowCount: Number(payload.previous_window_count || 0),
        previousCoveredTickSpan: Number(payload.previous_covered_tick_span || 0),
        previousContinuityScore: Number(payload.previous_continuity_score || 0),
        previousEnabledScore: Number(payload.previous_enabled_score || 0),
        previousBestControlScore: Number(payload.previous_best_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousCrossAxisEdgeCoverage: Number(payload.previous_cross_axis_edge_coverage || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        selectionDigestPrefix: String(payload.selection_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function longerMultiSessionGeneralizedTransferRetentionContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.longer_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity;
      if (
        !payload ||
        payload.schema !==
          "longer_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-longer-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.enabled_score || 0) < 0.90 ||
        Number(payload.continuity_score || 0) < 0.92 ||
        Number(payload.best_control_score || 1) > 0.60 ||
        Number(payload.baseline_advantage || 0) < 0.30 ||
        Number(payload.previous_retention_score || 0) < 0.90
      ) return {};
      if (
        Number(payload.source_record_count || 0) < 60 ||
        Number(payload.window_count || 0) !== 6 ||
        Number(payload.covered_tick_span || 0) !== 1536 ||
        Number(payload.retained_transfer_continuity_count || 0) < 6 ||
        Number(payload.retained_guidance_retention_continuity_count || 0) < 6 ||
        Number(payload.action_diversity_generalization_retention_continuity_count || 0) < 6 ||
        Number(payload.consequence_meaning_retention_continuity_count || 0) < 6 ||
        Number(payload.feedback_readability_retention_continuity_count || 0) < 6 ||
        Number(payload.transition_meaning_retention_continuity_count || 0) !== 5 ||
        Number(payload.agent_feedback_carryover_retention_continuity_count || 0) !== 5
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function longerMultiSessionGeneralizedTransferRetentionContinuitySummary(frame) {
      const payload = longerMultiSessionGeneralizedTransferRetentionContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        enabledScore: Number(payload.enabled_score || 0),
        continuityScore: Number(payload.continuity_score || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        sourceRecordCount: Number(payload.source_record_count || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        retainedTransferContinuityCount: Number(payload.retained_transfer_continuity_count || 0),
        retainedGuidanceRetentionContinuityCount: Number(payload.retained_guidance_retention_continuity_count || 0),
        actionDiversityGeneralizationRetentionContinuityCount: Number(payload.action_diversity_generalization_retention_continuity_count || 0),
        consequenceMeaningRetentionContinuityCount: Number(payload.consequence_meaning_retention_continuity_count || 0),
        feedbackReadabilityRetentionContinuityCount: Number(payload.feedback_readability_retention_continuity_count || 0),
        transitionMeaningRetentionContinuityCount: Number(payload.transition_meaning_retention_continuity_count || 0),
        agentFeedbackCarryoverRetentionContinuityCount: Number(payload.agent_feedback_carryover_retention_continuity_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function multiRegionMultiSessionGeneralizedTransferRetentionContinuity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_region_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity;
      if (
        !payload ||
        payload.schema !==
          "multi_region_multi_session_consequence_feedback_retention_guided_action_diversity_generalization_transfer_retention_continuity_projection_v1"
      ) return {};
      if (
        payload.display_only !== true ||
        payload.is_authority_state !== false ||
        payload.production_external_blocked !== true ||
        payload.analytics_blocked !== true ||
        payload.browser_evidence_status !== "passed" ||
        payload.artifact_budget_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::post-multi-region-multi-session-consequence-feedback-retention-guided-action-diversity-generalization-transfer-retention-continuity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics", "viewer", "rendering", "physics"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.region_count || 0) !== 4 ||
        Number(payload.session_count || 0) !== 3 ||
        Number(payload.region_session_cell_count || 0) !== 12 ||
        Number(payload.window_count || 0) !== 6 ||
        Number(payload.covered_tick_span || 0) !== 1536
      ) return {};
      if (
        Number(payload.enabled_score || 0) < 0.92 ||
        Number(payload.continuity_score || 0) < 0.93 ||
        Number(payload.best_control_score || 1) > 0.60 ||
        Number(payload.baseline_advantage || 0) < 0.32 ||
        Number(payload.cross_axis_edge_coverage || 0) < 1
      ) return {};
      if (
        Number(payload.retained_transfer_continuity_count || 0) < 12 ||
        Number(payload.retained_guidance_retention_continuity_count || 0) < 12 ||
        Number(payload.action_diversity_generalization_retention_continuity_count || 0) < 12 ||
        Number(payload.consequence_meaning_retention_continuity_count || 0) < 12 ||
        Number(payload.feedback_readability_retention_continuity_count || 0) < 12 ||
        Number(payload.transition_meaning_continuity_count || 0) < 2 ||
        Number(payload.agent_feedback_carryover_count || 0) < 2
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiRegionMultiSessionGeneralizedTransferRetentionContinuitySummary(frame) {
      const payload = multiRegionMultiSessionGeneralizedTransferRetentionContinuity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        enabledScore: Number(payload.enabled_score || 0),
        continuityScore: Number(payload.continuity_score || 0),
        bestControlScore: Number(payload.best_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        crossAxisEdgeCoverage: Number(payload.cross_axis_edge_coverage || 0),
        sourceRecordCount: Number(payload.source_count || payload.source_record_count || 0),
        regionCount: Number(payload.region_count || 0),
        sessionCount: Number(payload.session_count || 0),
        regionSessionCellCount: Number(payload.region_session_cell_count || 0),
        windowCount: Number(payload.window_count || 0),
        coveredTickSpan: Number(payload.covered_tick_span || 0),
        retainedTransferContinuityCount: Number(payload.retained_transfer_continuity_count || 0),
        retainedGuidanceRetentionContinuityCount: Number(payload.retained_guidance_retention_continuity_count || 0),
        actionDiversityGeneralizationRetentionContinuityCount: Number(payload.action_diversity_generalization_retention_continuity_count || 0),
        consequenceMeaningRetentionContinuityCount: Number(payload.consequence_meaning_retention_continuity_count || 0),
        feedbackReadabilityRetentionContinuityCount: Number(payload.feedback_readability_retention_continuity_count || 0),
        transitionMeaningContinuityCount: Number(payload.transition_meaning_continuity_count || 0),
        agentFeedbackCarryoverCount: Number(payload.agent_feedback_carryover_count || 0),
        browserEvidenceStatus: payload.browser_evidence_status || "unknown",
        artifactBudgetStatus: payload.artifact_budget_status || "unknown",
        replayStatus: payload.replay_status || "unknown",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
      };
    }

    function multiSessionConsequenceFeedbackMeaningRetention(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.multi_session_consequence_feedback_meaning_retention;
      if (!payload || payload.schema !== "multi_session_consequence_feedback_meaning_retention_projection_v1") return {};
      if (
        payload.authority !== "display_only" ||
        payload.display_only !== true ||
        payload.is_authority_state !== false
      ) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.recommended_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::post-multi-session-consequence-feedback-meaning-retention-gap-audit-and-next-capability-selection") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      const score = Number(payload.multi_session_consequence_feedback_meaning_retention_score || 0);
      const control = Number(payload.same_source_transfer_only_static_control_score || 0);
      const advantage = Number(payload.baseline_advantage_score || 0);
      if (Math.abs((score - control) - advantage) > 0.000001) return {};
      if (score < 0.88 || control > 0.62 || advantage < 0.25) return {};
      if (
        Number(payload.followup_session_count || 0) < 3 ||
        Number(payload.retained_transfer_count || 0) < 3 ||
        Number(payload.retained_consequence_meaning_count || 0) < 3 ||
        Number(payload.retained_feedback_meaning_count || 0) < 3 ||
        Number(payload.transition_meaning_reuse_count || 0) < 3 ||
        Number(payload.agent_feedback_carryover_stress_count || 0) < 3
      ) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function multiSessionConsequenceFeedbackMeaningRetentionSummary(frame) {
      const payload = multiSessionConsequenceFeedbackMeaningRetention(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        recommendedNextActionId: payload.recommended_next_action_id || "unknown",
        score: Number(payload.multi_session_consequence_feedback_meaning_retention_score || 0),
        sameSourceControlScore: Number(payload.same_source_transfer_only_static_control_score || 0),
        baselineAdvantageScore: Number(payload.baseline_advantage_score || 0),
        followupSessionCount: Number(payload.followup_session_count || 0),
        retainedTransferCount: Number(payload.retained_transfer_count || 0),
        retainedConsequenceMeaningCount: Number(payload.retained_consequence_meaning_count || 0),
        retainedFeedbackMeaningCount: Number(payload.retained_feedback_meaning_count || 0),
        transitionMeaningReuseCount: Number(payload.transition_meaning_reuse_count || 0),
        agentFeedbackCarryoverStressCount: Number(payload.agent_feedback_carryover_stress_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        timelineCount: Array.isArray(payload.timeline) ? payload.timeline.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postMultiSessionConsequenceFeedbackMeaningRetentionGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_multi_session_consequence_feedback_meaning_retention_gap_audit;
      if (
        !payload ||
        payload.schema !== "post_multi_session_consequence_feedback_meaning_retention_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.selected_next_action_id || "").toLowerCase();
      if (next !== "world-experience-next::consequence-feedback-retention-guided-open-world-action-diversity-hardening") {
        return {};
      }
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      for (const term of ["viewer-polish", "real-rendering", "planet-visual", "physics", "rendering"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 90 ||
        Number(payload.score_margin || 0) < 20 ||
        Number(payload.previous_retention_score || 0) < 0.88 ||
        Number(payload.previous_control_score || 1) > 0.62 ||
        Number(payload.previous_baseline_advantage || 0) < 0.25
      ) return {};
      if (
        Number(payload.source_count || 0) < 21 ||
        Number(payload.gap_count || 0) < 6 ||
        Number(payload.candidate_count || 0) < 6 ||
        Number(payload.score_count || 0) < 6 ||
        Number(payload.blocked_candidate_count || 0) < 4
      ) return {};
      if (
        !Array.isArray(payload.source_record_ids) ||
        payload.source_record_ids.length < 21 ||
        !Array.isArray(payload.required_gap_ids) ||
        payload.required_gap_ids.length < 6 ||
        !Array.isArray(payload.required_candidate_ids) ||
        payload.required_candidate_ids.length < 6
      ) return {};
      for (const key of [
        "source_bundle_digest",
        "accepted_score_rows_digest",
        "projection_payload_digest",
        "report_digest",
        "replay_digest"
      ]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postMultiSessionConsequenceFeedbackMeaningRetentionGapAuditSummary(frame) {
      const payload = postMultiSessionConsequenceFeedbackMeaningRetentionGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousRetentionScore: Number(payload.previous_retention_score || 0),
        previousControlScore: Number(payload.previous_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function consequenceFeedbackRetentionGuidedActionDiversity(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.consequence_feedback_retention_guided_action_diversity;
      if (
        !payload ||
        payload.schema !== "consequence_feedback_retention_guided_action_diversity_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.next_recommended_action_id || "").toLowerCase();
      if (
        next !== "world-experience-next::post-consequence-feedback-retention-guided-action-diversity-gap-audit-and-next-capability-selection"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.guided_score || 0) < 0.9 ||
        Number(payload.same_source_control_score || 1) > 0.58 ||
        Number(payload.baseline_advantage || 0) < 0.3 ||
        Number(payload.action_count || 0) < 6 ||
        Number(payload.action_category_count || 0) < 6 ||
        Number(payload.region_count || 0) < 4 ||
        Number(payload.guidance_count || 0) < 6 ||
        Number(payload.carryover_count || 0) < 3
      ) return {};
      if (!Array.isArray(payload.source_record_ids) || payload.source_record_ids.length < 19) return {};
      for (const key of ["source_bundle_digest", "projection_payload_digest", "report_digest", "replay_digest"]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function consequenceFeedbackRetentionGuidedActionDiversitySummary(frame) {
      const payload = consequenceFeedbackRetentionGuidedActionDiversity(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        nextRecommendedActionId: payload.next_recommended_action_id || "unknown",
        guidedScore: Number(payload.guided_score || 0),
        sameSourceControlScore: Number(payload.same_source_control_score || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        actionCount: Number(payload.action_count || 0),
        actionCategoryCount: Number(payload.action_category_count || 0),
        regionCount: Number(payload.region_count || 0),
        guidanceCount: Number(payload.guidance_count || 0),
        carryoverCount: Number(payload.carryover_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function postConsequenceFeedbackRetentionGuidedActionDiversityGapAudit(frame) {
      const payload =
        frame &&
        frame.payload &&
        frame.payload.post_consequence_feedback_retention_guided_action_diversity_gap_audit;
      if (
        !payload ||
        payload.schema !== "post_consequence_feedback_retention_guided_action_diversity_gap_audit_projection_v1"
      ) return {};
      if (payload.display_only !== true || payload.is_authority_state !== false) return {};
      if (!projectionPayloadGuardValid(payload)) return {};
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return {};
      }
      const next = String(payload.selected_next_action_id || "").toLowerCase();
      if (
        next !==
        "world-experience-next::longer-consequence-feedback-retention-guided-open-world-action-diversity-continuity-hardening"
      ) return {};
      for (const term of ["production", "pilot", "invite", "external", "contact", "public", "analytics"]) {
        if (next.includes(term)) return {};
      }
      for (const term of ["viewer-polish", "real-rendering", "planet-visual", "physics", "rendering"]) {
        if (next.includes(term)) return {};
      }
      if (
        Number(payload.selected_score || 0) < 45 ||
        Number(payload.score_margin || 0) < 10 ||
        Number(payload.second_best_score || 0) < 30 ||
        Number(payload.source_count || 0) < 26 ||
        Number(payload.gap_count || 0) < 6 ||
        Number(payload.candidate_count || 0) < 7 ||
        Number(payload.score_count || 0) < 7 ||
        Number(payload.blocked_candidate_count || 0) < 5 ||
        Number(payload.previous_guided_score || 0) < 0.95 ||
        Number(payload.previous_control_score || 1) > 0.58 ||
        Number(payload.previous_baseline_advantage || 0) < 0.4 ||
        Number(payload.previous_action_count || 0) < 6 ||
        Number(payload.previous_action_category_count || 0) < 6 ||
        Number(payload.previous_region_count || 0) < 4 ||
        Number(payload.previous_guidance_count || 0) < 6 ||
        Number(payload.previous_carryover_count || 0) < 3
      ) return {};
      if (
        !Array.isArray(payload.source_record_ids) ||
        payload.source_record_ids.length < 26 ||
        !Array.isArray(payload.required_gap_ids) ||
        payload.required_gap_ids.length < 6 ||
        !Array.isArray(payload.required_candidate_ids) ||
        payload.required_candidate_ids.length < 7
      ) return {};
      for (const key of [
        "source_bundle_digest",
        "accepted_score_rows_digest",
        "projection_payload_digest",
        "report_digest",
        "replay_digest"
      ]) {
        if (!String(payload[key] || "").startsWith("sha256:")) return {};
      }
      return payload;
    }

    function postConsequenceFeedbackRetentionGuidedActionDiversityGapAuditSummary(frame) {
      const payload = postConsequenceFeedbackRetentionGuidedActionDiversityGapAudit(frame);
      if (!payload.schema) return null;
      return {
        schema: payload.schema,
        selectedNextActionId: payload.selected_next_action_id || "unknown",
        selectedScore: Number(payload.selected_score || 0),
        secondBestCandidateId: payload.second_best_candidate_id || "unknown",
        secondBestScore: Number(payload.second_best_score || 0),
        scoreMargin: Number(payload.score_margin || 0),
        sourceCount: Number(payload.source_count || 0),
        gapCount: Number(payload.gap_count || 0),
        candidateCount: Number(payload.candidate_count || 0),
        scoreCount: Number(payload.score_count || 0),
        blockedCandidateCount: Number(payload.blocked_candidate_count || 0),
        previousGuidedScore: Number(payload.previous_guided_score || 0),
        previousControlScore: Number(payload.previous_control_score || 0),
        previousBaselineAdvantage: Number(payload.previous_baseline_advantage || 0),
        previousActionCount: Number(payload.previous_action_count || 0),
        previousActionCategoryCount: Number(payload.previous_action_category_count || 0),
        previousRegionCount: Number(payload.previous_region_count || 0),
        previousGuidanceCount: Number(payload.previous_guidance_count || 0),
        previousCarryoverCount: Number(payload.previous_carryover_count || 0),
        sourceRecordCount: Array.isArray(payload.source_record_ids) ? payload.source_record_ids.length : 0,
        requiredGapCount: Array.isArray(payload.required_gap_ids) ? payload.required_gap_ids.length : 0,
        requiredCandidateCount: Array.isArray(payload.required_candidate_ids) ? payload.required_candidate_ids.length : 0,
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.is_authority_state === false ? "non-authority" : "authority",
        sourceBundleDigestPrefix: String(payload.source_bundle_digest || "unknown").slice(0, 19),
        acceptedScoreRowsDigestPrefix: String(payload.accepted_score_rows_digest || "unknown").slice(0, 19),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        reportDigestPrefix: String(payload.report_digest || "unknown").slice(0, 19),
        replayDigestPrefix: String(payload.replay_digest || "unknown").slice(0, 19),
      };
    }

    function largeScalePersistentWorld(frame) {
      const payload = frame && frame.payload && frame.payload.large_scale_persistent_world;
      if (!payload || payload.schema !== "large_scale_persistent_world_projection_v1") return {};
      if (payload.viewer_generated_persistence_allowed !== false) return {};
      const required = [
        "persistent_world_session",
        "persistent_session_segment",
        "persistent_region_graph",
        "persistent_session_checkpoint",
        "large_scale_navigation_matrix",
        "persistent_interaction_carryovers",
        "user_browser_flow_evidence",
      ];
      for (const key of required) {
        if (!payload[key]) return {};
      }
      return payload;
    }

    function largeScalePersistentWorldSummary(frame) {
      const payload = largeScalePersistentWorld(frame);
      if (!payload.schema) return null;
      const session = payload.persistent_world_session || {};
      const graph = payload.persistent_region_graph || {};
      const checkpoint = payload.persistent_session_checkpoint || {};
      const matrix = payload.large_scale_navigation_matrix || {};
      const flow = payload.user_browser_flow_evidence || {};
      const carryovers = Array.isArray(payload.persistent_interaction_carryovers)
        ? payload.persistent_interaction_carryovers
        : [];
      if (!session.session_id || !graph.graph_digest || !checkpoint.checkpoint_id || !matrix.navigation_matrix_id) {
        return null;
      }
      return {
        sessionId: session.session_id,
        segmentCount: Array.isArray(session.session_segment_ids) ? session.session_segment_ids.length : 0,
        regionCount: Array.isArray(graph.region_ids) ? graph.region_ids.length : 0,
        checkpointCount: Array.isArray(session.checkpoint_ids) ? session.checkpoint_ids.length : 0,
        routeStepCount: Number(matrix.route_step_count || 0),
        carryoverCount: carryovers.length,
        flowButtonCount: Array.isArray(flow.button_sequence) ? flow.button_sequence.length : 0,
      };
    }

    function scaledFieldSignatureAuthoring(frame) {
      const payload = frame && frame.payload && frame.payload.scaled_field_signature_authoring;
      if (!payload || payload.schema !== "scaled_field_signature_authoring_projection_v1") return {};
      if (payload.viewer_generated_structure_allowed !== false) return {};
      return payload;
    }

    function decodeRicherDensityCells(densityMap) {
      if (!densityMap || densityMap.schema !== "local_content_density_map_v1" || densityMap.is_authority_state !== false) return [];
      const encoded = densityMap.cells_rle_base64 || "";
      if (!encoded.startsWith("base64:")) return [];
      const binary = atob(encoded.slice("base64:".length));
      const cells = [];
      for (let i = 0; i + 4 < binary.length; i += 5) {
        const run = binary.charCodeAt(i);
        const cell = [
          binary.charCodeAt(i + 1),
          binary.charCodeAt(i + 2),
          binary.charCodeAt(i + 3),
          binary.charCodeAt(i + 4),
        ];
        for (let j = 0; j < run; j++) cells.push(cell);
      }
      return cells;
    }

    function macroStateOverlays(frame) {
      return debugLayerValue(frame, "macro_state_overlays", []);
    }

    function fineRefinementOverlays(frame) {
      return debugLayerValue(frame, "fine_refinement_overlays", []);
    }

    function macroCorrectionOverlays(frame) {
      return debugLayerValue(frame, "macro_correction_overlays", []);
    }

    function macroBoundaryExchangeOverlays(frame) {
      return debugLayerValue(frame, "macro_boundary_exchange_overlays", []);
    }

    function regionOverlays(frame) {
      return debugLayerValue(frame, "region_overlays", []);
    }

    function regionLifecycleOverlays(frame) {
      return debugLayerValue(frame, "region_lifecycle_overlays", []);
    }
"""


def viewer_legacy_post_route_reentry_summary_js() -> str:
    return _VIEWER_LEGACY_POST_ROUTE_REENTRY_SUMMARY_JS
