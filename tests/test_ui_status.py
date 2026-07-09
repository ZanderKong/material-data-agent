"""Tests for display status derivation."""
import pytest
from data_agent.ui.status import derive_display_status, status_display_name


class TestDeriveDisplayStatus:
    def test_ingested_when_no_runs(self):
        assert derive_display_status("ingested", [], [], []) == "ingested"

    def test_processed_when_runs_and_no_flags(self):
        runs = [{"status": "succeeded", "tool_name": "data_agent"}]
        assert derive_display_status("processed", runs, [], []) == "processed"

    def test_needs_review_when_requires_review_flag(self):
        runs = [{"status": "succeeded"}]
        flags = [{"requires_review": True, "message": "test"}]
        assert derive_display_status("processed", runs, flags, []) == "needs_review"

    def test_reviewed_with_approve_review(self):
        runs = [{"status": "succeeded"}]
        flags = [{"requires_review": True}]
        reviews = [{"action": "approve"}]
        assert derive_display_status("processed", runs, flags, reviews) == "reviewed"

    def test_reviewed_without_requires_review(self):
        runs = [{"status": "succeeded"}]
        reviews = [{"action": "approve"}]
        assert derive_display_status("processed", runs, [], reviews) == "reviewed"

    def test_returned_for_rerun(self):
        runs = [{"status": "succeeded"}]
        reviews = [{"action": "return_for_rerun"}]
        assert derive_display_status("processed", runs, [], reviews) == "returned_for_rerun"

    def test_deprecated(self):
        reviews = [{"action": "deprecate"}]
        assert derive_display_status("processed", [], [], reviews) == "deprecated"

    def test_deprecated_takes_priority_over_reviewed(self):
        flags = [{"requires_review": True}]
        reviews = [{"action": "approve"}, {"action": "deprecate"}]
        assert derive_display_status("processed", [], flags, reviews) == "deprecated"

    def test_deprecated_takes_priority_over_return(self):
        reviews = [{"action": "return_for_rerun"}, {"action": "deprecate"}]
        assert derive_display_status("processed", [], [], reviews) == "deprecated"

    def test_failed_or_warning_when_failed_run(self):
        runs = [{"status": "failed"}]
        assert derive_display_status("processed", runs, [], []) == "failed_or_warning"

    def test_failed_or_warning_when_model_unavailable_flag(self):
        runs = [{"status": "succeeded"}]
        flags = [{"message": "model_unavailable: test"}]
        assert derive_display_status("processed", runs, flags, []) == "failed_or_warning"

    def test_returned_takes_priority_over_needs_review(self):
        runs = [{"status": "succeeded"}]
        flags = [{"requires_review": True}]
        reviews = [{"action": "return_for_rerun"}]
        assert derive_display_status("processed", runs, flags, reviews) == "returned_for_rerun"

    def test_empty_inputs_default(self):
        assert derive_display_status("unknown") == "ingested"


class TestStatusDisplayName:
    def test_known_statuses(self):
        assert status_display_name("ingested") == "Ingested"
        assert status_display_name("processed") == "Processed"
        assert status_display_name("needs_review") == "Needs Review"
        assert status_display_name("reviewed") == "Reviewed"
        assert status_display_name("returned_for_rerun") == "Returned for Rerun"
        assert status_display_name("failed_or_warning") == "Failed / Warning"
        assert status_display_name("deprecated") == "Deprecated"

    def test_unknown_status_passthrough(self):
        assert status_display_name("something_else") == "something_else"
