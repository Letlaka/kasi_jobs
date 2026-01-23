import pytest


@pytest.mark.skip("Template - copy/rename this test when adding a new workflow action")
@pytest.mark.django_db
def test_new_workflow_action_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """Template for new workflow action tests.

    Copy this file to create a concrete test for a new action (e.g., `withdraw`).
    Fill in the placeholders below:
      - `view_factory`: create an APIRequestFactory and request for the action
      - `user_fixture`: the actor allowed to perform the action (poster/staff)
      - `service_module`: import the service module and patch metric helpers

    Assertions you should include:
      - response status (200 or expected ApiError mapping)
      - that `self.throttle_scope` was set at runtime (mixin logs warn otherwise)
      - audit record persisted (ApplicationAction or equivalent)
      - metric helpers (`safe_inc`, `safe_observe`) invoked at least once
      - background dispatch attempted (patch `emit_background_task` to record calls)
    """

    raise NotImplementedError("Copy and implement this test for your new action")
