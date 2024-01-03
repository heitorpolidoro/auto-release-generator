"""This file contains test cases for the Pull Request Generator application."""
from unittest import TestCase
from unittest.mock import Mock, patch

import pytest
import sentry_sdk

from app.app import app, get_command, release


@pytest.fixture
def commit():
    """
    This fixture returns a mocked commit object with default values for the attributes.
    :return: Mocked Commit
    """
    commit = Mock(message="[release:command]")
    return commit


@pytest.fixture
def repository():
    """
    This fixture returns a mocked repository object with default values for the attributes.
    :return: Mocked Repository
    """
    repository = Mock(
        default_branch="master", full_name="heitorpolidoro/auto-release-generator"
    )
    return repository


@pytest.fixture
def event(repository, commit):
    """
    This fixture returns a mocked event object with default values for the attributes.
    :return: Mocked Event
    """
    return Mock(repository=repository, commits=[commit], ref="issue-42")


class TestApp(TestCase):
    def setUp(self):
        self.app = app.test_client()

    def tearDown(self):
        sentry_sdk.flush()

    def test_root(self):
        """
        Test the root endpoint of the application.
        This test ensures that the root endpoint ("/") of the application is working correctly.
        It sends a GET request to the root endpoint and checks that the response status code is 200 and the response
        text is "Pull Request Generator App up and running!".
        """
        response = self.app.get("/")
        assert response.status_code == 200
        assert response.text == "Auto Release Generator App up and running!"

    def test_webhook(self):
        """
        Test the webhook handler of the application.
        This test ensures that the webhook handler is working correctly.
        It mocks the `handle` function of the `webhook_handler` module, sends a POST request to the root endpoint ("/")
        with a specific JSON payload and headers, and checks that the `handle` function is called with the correct
        arguments.
        """
        with patch("app.app.webhook_handler.handle") as mock_handle:
            request_json = {"action": "opened", "number": 1}
            headers = {
                "User-Agent": "Werkzeug/3.0.1",
                "Host": "localhost",
                "Content-Type": "application/json",
                "Content-Length": "33",
                "X-Github-Event": "pull_request",
            }
            self.app.post("/", headers=headers, json=request_json)
            mock_handle.assert_called_once_with(headers, request_json)


def test_get_command(commit):
    assert get_command(commit.message, "release") == "command"


def test_get_command_no_command(commit):
    assert get_command(commit.message, "prefix") is None


def test_get_command_multiple_commands():
    assert get_command("[release:command1][release:command2]", "release") == "command2"


def test_release(event, commit, repository):
    release(event)
    repository.update_file.assert_called_once_with()
