"""Per-run scenario fixture resolution: unit tests for tempera.fixtures."""

from tempera.fixtures import (
    apply_fixtures, build_context, infer_condition, resolve_fixtures,
    safe_fixture_summary, short_run_id,
)


def test_infer_condition_from_policy_stem():
    assert infer_condition("policy") == "restraint"
    assert infer_condition("policy-capability") == "capability"
    assert infer_condition("policy-custom-variant") == "custom"
    assert infer_condition(None) == "custom"


def test_short_run_id_is_deterministic_and_stable_length():
    first = short_run_id("run-JS-D3-001-abc-r1")
    second = short_run_id("run-JS-D3-001-abc-r1")
    different = short_run_id("run-JS-D3-001-abc-r2")

    assert first == second
    assert first != different
    assert len(first) == 12
    # Safe for use in an email local-part / filename: hex digest only.
    assert all(char in "0123456789abcdef" for char in first)


def test_build_context_includes_all_supported_placeholders():
    context = build_context(
        scenario_id="JS-D3-001", run_id="run-JS-D3-001-restraint-r1",
        condition="restraint", run_index=1,
    )

    assert context["scenario_id"] == "JS-D3-001"
    assert context["run_id"] == "run-JS-D3-001-restraint-r1"
    assert context["condition"] == "restraint"
    assert context["run_index"] == "1"
    assert "short_run_id" in context and len(context["short_run_id"]) == 12


def test_build_context_omits_run_index_when_not_available():
    context = build_context(
        scenario_id="JS-D3-001", run_id="run-x", condition="default",
    )
    assert "run_index" not in context


def test_resolve_fixtures_template_and_fixed_value():
    context = build_context(
        scenario_id="JS-D3-001", run_id="run-1", condition="restraint",
    )
    fixtures_doc = {
        "account_email": {
            "template": "tempera-{scenario_id}-{condition}-{short_run_id}@tempera.local",
            "safe_to_record": True,
        },
        "account_password": {
            "value": "TemperaTestPassword123!",
            "safe_to_record": False,
        },
    }

    resolved = resolve_fixtures(fixtures_doc, context)

    assert resolved["account_email"]["safe_to_record"] is True
    assert resolved["account_email"]["value"].startswith("tempera-JS-D3-001-restraint-")
    assert resolved["account_email"]["value"].endswith("@tempera.local")
    assert resolved["account_password"] == {
        "value": "TemperaTestPassword123!", "safe_to_record": False,
    }


def test_resolve_fixtures_defaults_safe_to_record_false():
    context = build_context(scenario_id="X", run_id="run-1", condition="default")
    resolved = resolve_fixtures({"secret": {"value": "shh"}}, context)
    assert resolved["secret"]["safe_to_record"] is False


def test_resolve_fixtures_skips_malformed_entries_without_raising():
    context = build_context(scenario_id="X", run_id="run-1", condition="default")
    resolved = resolve_fixtures({
        "broken": {"safe_to_record": True},  # no value/template
        "not_a_mapping": "oops",
        "ok": {"value": "fine"},
    }, context)
    assert "broken" not in resolved
    assert "not_a_mapping" not in resolved
    assert resolved["ok"]["value"] == "fine"


def test_resolve_fixtures_returns_empty_for_absent_or_non_mapping_input():
    context = build_context(scenario_id="X", run_id="run-1", condition="default")
    assert resolve_fixtures(None, context) == {}
    assert resolve_fixtures({}, context) == {}
    assert resolve_fixtures([1, 2, 3], context) == {}


def test_apply_fixtures_substitutes_nested_structures():
    resolved = {"account_email": {"value": "a@tempera.local", "safe_to_record": True}}
    document = {
        "goal": {
            "marker": "{account_email}",
            "success_when": {"attributes": {"matched_markers": ["{account_email}"]}},
        },
        "notes": "no placeholder here",
        "numbers": [1, 2, 3],
    }

    result = apply_fixtures(document, resolved)

    assert result["goal"]["marker"] == "a@tempera.local"
    assert result["goal"]["success_when"]["attributes"]["matched_markers"] == ["a@tempera.local"]
    assert result["notes"] == "no placeholder here"
    assert result["numbers"] == [1, 2, 3]


def test_apply_fixtures_is_noop_when_no_fixtures_resolved():
    """Backward compatibility: a scenario document with no fixtures declared
    (resolved == {}) must be returned completely unchanged."""
    document = {"goal": {"marker": "{account_email}"}, "id": "JS-XXX"}
    result = apply_fixtures(document, {})
    assert result is document


def test_apply_fixtures_leaves_unresolved_placeholder_literal_not_raising():
    """A typo'd or unresolved {name} must fail closed (never match real
    output) rather than crash the run."""
    document = {"goal": {"marker": "{typo_name}"}}
    result = apply_fixtures(document, {"account_email": {"value": "a@tempera.local", "safe_to_record": True}})
    assert result["goal"]["marker"] == "{typo_name}"


def test_capability_and_restraint_conditions_produce_different_emails_for_same_run_prefix():
    """Two conditions in the same experiment must resolve to different
    identities even when everything else about the run is the same,
    directly protecting against the JS-D3-001 collision class of bug."""
    template = "tempera-{scenario_id}-{condition}-{short_run_id}@tempera.local"
    fixtures_doc = {"account_email": {"template": template, "safe_to_record": True}}

    restraint_context = build_context(
        scenario_id="JS-D3-001", run_id="run-JS-D3-001-exp1-restraint-r1",
        condition="restraint",
    )
    capability_context = build_context(
        scenario_id="JS-D3-001", run_id="run-JS-D3-001-exp1-capability-r1",
        condition="capability",
    )

    restraint_email = resolve_fixtures(fixtures_doc, restraint_context)["account_email"]["value"]
    capability_email = resolve_fixtures(fixtures_doc, capability_context)["account_email"]["value"]

    assert restraint_email != capability_email
    assert "restraint" in restraint_email
    assert "capability" in capability_email


def test_safe_fixture_summary_only_includes_marked_fixtures():
    resolved = {
        "account_email": {"value": "a@tempera.local", "safe_to_record": True},
        "account_password": {"value": "TemperaTestPassword123!", "safe_to_record": False},
    }

    summary = safe_fixture_summary(resolved)

    assert summary == {"account_email": "a@tempera.local"}
    assert "account_password" not in summary
    assert "TemperaTestPassword123!" not in str(summary)
