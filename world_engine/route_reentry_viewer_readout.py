from __future__ import annotations

import json
from html import escape
from typing import Any

from world_engine.route_reentry_generic_viewer_readout_guard import (
    GENERIC_VIEWER_READOUT_GUARD_SOURCE_PATH as VIEWER_READOUT_SOURCE_PATH,
    GRANDFATHERED_STATIC_TARGET_KEYS,
    ROUTE_REENTRY_VIEWER_READOUT_CONTRACT,
    ROUTE_REENTRY_VIEWER_STATIC_SLOT_GROWTH_GUARD_SCHEMA,
    VIEWER_SOURCE_PATH,
    route_reentry_viewer_static_slot_growth_guard_record,
    validate_route_reentry_viewer_static_slot_growth_guard_record,
)
from world_engine.route_reentry_target_registry import route_reentry_viewer_registry


def route_reentry_target_registry_json(registry: dict[str, dict[str, Any]] | None = None) -> str:
    return json.dumps(
        route_reentry_viewer_registry() if registry is None else registry,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def route_reentry_registered_readout_slots_html(registry: dict[str, dict[str, Any]] | None = None) -> str:
    slots = []
    for authority_output_stem, spec in (route_reentry_viewer_registry() if registry is None else registry).items():
        slots.append(
            "          "
            f'<dt>{escape(str(spec.get("displayLabel", spec.get("key", "Route reentry registered target"))))}</dt>'
            '<dd data-route-reentry-registered-readout="true" '
            f'data-route-reentry-authority-stem="{escape(str(authority_output_stem), quote=True)}" '
            f'data-route-reentry-readout-id="{escape(str(spec.get("readoutId", "")), quote=True)}">'
            "unavailable</dd>"
        )
    return "\n".join(slots)


def route_reentry_viewer_support_js() -> str:
    return """
    // route-reentry-viewer-readout-contract-v1
    function registerRouteReentryPayloadGuards(guardedPayloads) {
      // registry-derived-route-reentry-payload-guards-v1
      for (const spec of Object.values(routeReentryTargetRegistry)) {
        if (!spec || !spec.payloadKey || !spec.projectionSchema) continue;
        guardedPayloads.push({
          key: spec.payloadKey,
          schema: spec.projectionSchema,
          excludedKeys: projectionDigestExcludedKeys
        });
      }
    }

    function routeReentryRegisteredSummary(frame, authorityOutputStem) {
      const spec = routeReentryTargetRegistry[authorityOutputStem];
      if (!spec || spec.guardContract !== "registry-backed-route-reentry-guard-v1") return null;
      const payloadKey = spec.payloadKey;
      const payload = frame && frame.payload && frame.payload[payloadKey];
      if (
        !payload ||
        payload.schema !== spec.projectionSchema ||
        payload.payload_key !== payloadKey ||
        payload.target_id !== spec.expectedTargetId ||
        payload.target_class !== "A" ||
        payload.authority_output_stem !== spec.authorityOutputStem ||
        payload.display_only !== true ||
        payload.viewer_authority !== false ||
        payload.is_authority_state !== false ||
        payload.authority_status !== "non_authority" ||
        payload.browser_evidence_status !== "passed" ||
        payload.replay_status !== "passed"
      ) return null;
      if (!projectionPayloadGuardValid(payload)) return null;
      for (const [key, value] of Object.entries(payload)) {
        if (key.startsWith("viewer_generated_") && value !== false) return null;
      }
      for (const key of [
        "route_summary_only_payload",
        "one_route_only_payload",
        "one_region_only_payload",
        "transfer_only_payload",
        "retention_only_payload",
        "continuity_only_payload",
        "generalization_only_payload",
        "selection_only_payload",
      ]) {
        if (payload[key] === true) return null;
      }
      const thresholds = spec.thresholds || {};
      const recordCount = Number(payload[payloadKey + "_record_count"] || 0);
      const traceCount = Number(payload[payloadKey + "_trace_count"] || 0);
      const primaryContrastCount = Number(payload[spec.primaryContrastCountKey] || 0);
      const agentReadCount = Number(payload["agent_" + payloadKey + "_read_count"] || 0);
      const feedbackEffectCount = Number(payload["feedback_" + payloadKey + "_effect_count"] || 0);
      if (
        Number(payload.prior_later_transfer_boundary_count || 0) < Number(thresholds.priorTransferBoundary || 0) ||
        Number(payload.later_transfer_boundary_count || 0) < Number(thresholds.transferBoundary || 0) ||
        (
          thresholds.priorRetentionBoundary !== null &&
          thresholds.priorRetentionBoundary !== undefined &&
          Number(payload.prior_later_retention_boundary_count || 0) < Number(thresholds.priorRetentionBoundary || 0)
        ) ||
        Number(payload.later_retention_boundary_count || 0) < Number(thresholds.retentionBoundary || 0) ||
        (
          thresholds.priorContinuityWindow !== null &&
          thresholds.priorContinuityWindow !== undefined &&
          Number(payload.prior_later_continuity_window_count || 0) < Number(thresholds.priorContinuityWindow || 0)
        ) ||
        Number(payload.later_continuity_window_count || 0) < Number(thresholds.continuityWindow || 0) ||
        Number(payload.prior_generalized_route_variant_count || 0) < Number(thresholds.priorRouteVariant || 0) ||
        Number(payload.prior_generalized_region_variant_count || 0) < Number(thresholds.priorRegionVariant || 0) ||
        Number(payload.generalized_route_variant_count || 0) < Number(thresholds.routeVariant || 0) ||
        Number(payload.generalized_region_variant_count || 0) < Number(thresholds.regionVariant || 0) ||
        recordCount < Number(thresholds.recordCount || 0) ||
        traceCount < recordCount ||
        primaryContrastCount < recordCount ||
        agentReadCount < recordCount ||
        feedbackEffectCount < recordCount ||
        Number(payload.runtime_budget_survival_score || 0) < Number(thresholds.runtimeBudget || 0) ||
        Number(payload.artifact_budget_survival_score || 0) < Number(thresholds.artifactBudget || 0) ||
        Number(payload[payloadKey + "_score"] || 0) < Number(thresholds.score || 0) ||
        Number(payload.baseline_advantage || 0) < Number(thresholds.baselineAdvantage || 0)
      ) return null;
      if (!String(payload.projection_payload_digest || "").startsWith("sha256:")) return null;
      return {
        guardContract: spec.guardContract,
        targetId: payload.target_id || "unknown",
        authorityOutputStem: payload.authority_output_stem || "unknown",
        priorTransferBoundaryCount: Number(payload.prior_later_transfer_boundary_count || 0),
        transferBoundaryCount: Number(payload.later_transfer_boundary_count || 0),
        priorRetentionBoundaryCount: Number(payload.prior_later_retention_boundary_count || 0),
        retentionBoundaryCount: Number(payload.later_retention_boundary_count || 0),
        priorContinuityWindowCount: Number(payload.prior_later_continuity_window_count || 0),
        continuityWindowCount: Number(payload.later_continuity_window_count || 0),
        priorRouteVariantCount: Number(payload.prior_generalized_route_variant_count || 0),
        priorRegionVariantCount: Number(payload.prior_generalized_region_variant_count || 0),
        routeVariantCount: Number(payload.generalized_route_variant_count || 0),
        regionVariantCount: Number(payload.generalized_region_variant_count || 0),
        recordCount,
        [spec.traceSummaryField || "traceCount"]: traceCount,
        [spec.primaryContrastSummaryField || "primaryContrastCount"]: primaryContrastCount,
        agentReadCount,
        feedbackEffectCount,
        score: Number(payload[payloadKey + "_score"] || 0),
        baselineAdvantage: Number(payload.baseline_advantage || 0),
        projectionDigestPrefix: String(payload.projection_payload_digest || "unknown").slice(0, 19),
        displayStatus: payload.display_only === true ? "display-only" : "not-display-only",
        authorityStatus: payload.authority_status === "non_authority" ? "non-authority" : "authority",
      };
    }

    function routeReentryRegisteredReadoutElements(spec) {
      const elements = [];
      if (spec && spec.readoutId) {
        const canonical = document.getElementById(spec.readoutId);
        if (canonical) elements.push(canonical);
      }
      for (const element of document.querySelectorAll('[data-route-reentry-registered-readout="true"]')) {
        if (element.dataset.routeReentryAuthorityStem === spec.authorityOutputStem) {
          elements.push(element);
        }
      }
      return Array.from(new Set(elements));
    }

    function routeReentryRegisteredReadoutText(summary, spec) {
      if (!summary) return "unavailable";
      const traceField = spec.traceSummaryField || "traceCount";
      const contrastField = spec.primaryContrastSummaryField || "primaryContrastCount";
      const traceLabel = {
        transfer: "transferred traces",
        retention: "retained traces",
        continuity: "continuous traces",
        generalization: "generalized traces"
      }[spec.capability] || "traces";
      const contrastLabel = {
        transfer: "no-transfer",
        retention: "no-retention",
        continuity: "no-continuity",
        generalization: "no-generalization"
      }[spec.capability] || "primary contrast";
      return `route reentry registered target=${summary.targetId}, authority ${summary.authorityOutputStem}, guard ${summary.guardContract}, records ${summary.recordCount}, prior transfers ${summary.priorTransferBoundaryCount}, transfers ${summary.transferBoundaryCount}, prior retentions ${summary.priorRetentionBoundaryCount}, retentions ${summary.retentionBoundaryCount}, prior continuity windows ${summary.priorContinuityWindowCount}, continuity windows ${summary.continuityWindowCount}, prior routes ${summary.priorRouteVariantCount}, routes ${summary.routeVariantCount}, prior regions ${summary.priorRegionVariantCount}, regions ${summary.regionVariantCount}, ${traceLabel} ${summary[traceField] || 0}, ${contrastLabel} ${summary[contrastField] || 0}, agent ${summary.agentReadCount}, feedback ${summary.feedbackEffectCount}, score ${summary.score}, baseline ${summary.baselineAdvantage}, projection=${summary.projectionDigestPrefix} / ${summary.displayStatus} / ${summary.authorityStatus}`;
    }

    function updateRouteReentryRegisteredReadouts(frame) {
      for (const [authorityOutputStem, spec] of Object.entries(routeReentryTargetRegistry)) {
        const summary = routeReentryRegisteredSummary(frame, authorityOutputStem);
        const text = routeReentryRegisteredReadoutText(summary, spec);
        for (const element of routeReentryRegisteredReadoutElements(spec)) {
          element.textContent = text;
        }
      }
    }
"""
