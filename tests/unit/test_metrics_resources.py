import pytest

from backend.metrics.events import EVENT_CATEGORY, EventCategory
from backend.metrics.resources import (
    API_ROUTE_PREFIX_TO_RESOURCE,
    EVENT_NAME_TO_RESOURCE,
    RESOURCE_BY_CATEGORY,
    Resource,
    resource_filter_clause,
)
from backend.models.anonymous_metrics import Anonymous_Metrics

pytestmark = pytest.mark.unit


def test_resource_values_are_lowercase_of_member_name():
    for resource in Resource:
        assert resource.value == resource.name.lower()


def test_every_non_api_event_name_has_a_resource():
    """Every UI + Domain EventName maps to exactly one Resource. API_HIT is the
    only event without an entry — its resource is derived from `endpoint`."""
    for event_name, category in EVENT_CATEGORY.items():
        if category is EventCategory.API:
            assert event_name not in EVENT_NAME_TO_RESOURCE
        else:
            assert event_name in EVENT_NAME_TO_RESOURCE


def test_resource_by_category_keys_are_the_three_event_categories():
    assert set(RESOURCE_BY_CATEGORY) == set(EventCategory)


def test_resource_by_category_api_includes_other_fallback():
    """The API tab's resource list always exposes OTHER for routes outside
    the known prefix set."""
    assert Resource.OTHER in RESOURCE_BY_CATEGORY[EventCategory.API]


def test_resource_by_category_ui_includes_all_ui_specific_resources():
    """UI tab contains the resources unique to UI events (Search, Form, Deck,
    Nav, Contact, Auth, Error) in addition to the shared CRUD resources."""
    ui_resources = set(RESOURCE_BY_CATEGORY[EventCategory.UI])
    expected_ui_specific = {
        Resource.SEARCH,
        Resource.FORM,
        Resource.DECK,
        Resource.NAV,
        Resource.CONTACT,
        Resource.AUTH,
        Resource.ERROR,
    }
    assert expected_ui_specific.issubset(ui_resources)


def test_resource_by_category_domain_is_crud_only():
    """Domain events are business-state transitions; they cover UTub, URL,
    Tag, Member, and Auth (account lifecycle signals — register, login
    success/failure, email verification, password-reset request/complete)."""
    assert set(RESOURCE_BY_CATEGORY[EventCategory.DOMAIN]) == {
        Resource.UTUB,
        Resource.URL,
        Resource.TAG,
        Resource.MEMBER,
        Resource.AUTH,
    }


def test_api_route_prefixes_end_with_dot():
    """Prefixes match Flask endpoint names (`<blueprint>.<view_function>`)
    as stored in `Anonymous_Metrics.endpoint`. The trailing `.` prevents
    `utubs.` from accidentally matching a future `utubstats.` blueprint."""
    for prefix, _resource in API_ROUTE_PREFIX_TO_RESOURCE:
        assert prefix.endswith(".")
        assert "/" not in prefix


def test_resource_filter_clause_ui_emits_event_name_in():
    """For UI/Domain the clause filters on `event_name`, listing every UI
    event mapped to the resource."""
    clause = resource_filter_clause(category=EventCategory.UI, resource=Resource.UTUB)
    rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert '"eventName" IN' in rendered
    assert "'ui_utub_select'" in rendered
    assert "'ui_utub_delete_confirm'" in rendered
    assert "'ui_url_access'" not in rendered


def test_resource_filter_clause_domain_filters_on_event_name():
    clause = resource_filter_clause(
        category=EventCategory.DOMAIN, resource=Resource.TAG
    )
    rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert '"eventName" IN' in rendered
    assert "'tag_applied'" in rendered
    assert "'tag_deleted'" in rendered
    assert "'utub_created'" not in rendered


def test_resource_filter_clause_api_emits_endpoint_like():
    """For API the clause filters on the flat `endpoint` column via LIKE
    against the Flask endpoint-name prefix (`utubs.%`, not `/utubs/%`)."""
    clause = resource_filter_clause(category=EventCategory.API, resource=Resource.UTUB)
    rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "endpoint LIKE 'utubs.%'" in rendered


def test_resource_filter_clause_api_tag_covers_both_utub_and_url_tags_prefixes():
    """`TAG` maps to two Flask blueprints (`utub_tags` + `utub_url_tags`); the
    OR clause must include LIKE patterns for both."""
    clause = resource_filter_clause(category=EventCategory.API, resource=Resource.TAG)
    rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "endpoint LIKE 'utub_tags.%'" in rendered
    assert "endpoint LIKE 'utub_url_tags.%'" in rendered


def test_resource_filter_clause_api_other_is_negation_of_known_prefixes():
    clause = resource_filter_clause(category=EventCategory.API, resource=Resource.OTHER)
    rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "NOT (" in rendered
    for prefix, _resource in API_ROUTE_PREFIX_TO_RESOURCE:
        assert f"endpoint LIKE '{prefix}%'" in rendered


def test_resource_filter_clause_returns_sqlalchemy_expression():
    """Clause is a real SQLAlchemy ColumnElement, not a raw bool/string —
    so it composes with `.filter(...)` chains in the query layer."""
    clause = resource_filter_clause(category=EventCategory.UI, resource=Resource.URL)
    assert hasattr(clause, "compile")
    # Trivially composable with the model — confirms the clause carries
    # the right binding context, not just a free-floating literal.
    composed = clause & (Anonymous_Metrics.count > 0)
    assert hasattr(composed, "compile")
