"""
This file contains the main application logic for the Pull Request Generator,
including a webhook handler for creating pull requests when new branches are created.
"""
import json
import logging
import os
import re
import sys
from typing import Optional

import sentry_sdk
from flask import Flask, request
from github.Branch import Branch
from github.Commit import Commit
from github.GitCommit import GitCommit
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import webhook_handler
from githubapp.events import PushEvent

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

if sentry_dns := os.getenv("SENTRY_DSN"):  # pragma: no cover
    # Initialize Sentry SDK for error logging
    sentry_sdk.init(
        dsn=sentry_dns,
        # Set traces_sample_rate to 1.0 to capture 100%
        # of transactions for performance monitoring.
        traces_sample_rate=1.0,
        # Set profiles_sample_rate to 1.0 to profile 100%
        # of sampled transactions.
        # We recommend adjusting this value in production.
        profiles_sample_rate=1.0,
    )
    logger.info("Sentry initialized")

app = Flask("Auto Release Generator")
app.__doc__ = "This is a Flask application auto merging pull requests."


def get_command(text: str, command_prefix: str) -> Optional[str]:
    """
    Retrieve the command from the commit message.
    The command in the commit message must be in the format [command_prefix: command]

    :param text: The Commit object.
    :param command_prefix: The command prefix to look for in the commit message.
    :return: The extracted command or None if there is no command.
    :raises: ValueError if the command is not valid.
    """
    command_pattern = rf"\[{command_prefix}:(.+?)\]"
    commands_found = re.findall(command_pattern, text)
    if commands_found:
        return commands_found[-1].strip()
    return None


@webhook_handler.webhook_handler(PushEvent)
def release(event: PushEvent) -> None:
    repository = event.repository
    last_command = None
    for commit in event.commits:
        last_command = last_command or get_command(commit.message, "release")
    if last_command is None:
        return
    if event.ref.endswith(repository.default_branch):
        # create release
        return

    version_file_path = "app/__init__.py"
    original_file = repository.get_contents(version_file_path,
                                            ref=repository.get_commit(sha=event.after).get_pulls()[0].base.ref)
    original_file_content = original_file.decoded_content.decode()
    current_version_in_file = re.search(r"__version__ = \"(.+?)\"", original_file_content).group(1)

    file_to_update = repository.get_contents(version_file_path, ref=event.ref)
    new_content = original_file_content.replace(current_version_in_file, last_command)
    if new_content != original_file_content:
        print(f"Updating {version_file_path} with {last_command}")
        repository.update_file(
            version_file_path,
            f"Release {last_command}",
            new_content,
            file_to_update.sha,
            branch=event.ref,
        )


@app.route("/", methods=["GET"])
def root() -> str:
    """
    This route displays the welcome screen of the application.
    It uses the root function of the webhook_handler to generate the welcome screen.
    """
    return webhook_handler.root(app.name)()


@app.route("/", methods=["POST"])
def webhook() -> str:
    """
    This route is the endpoint that receives the GitHub webhook call.
    It handles the headers and body of the request, and passes them to the webhook_handler for processing.
    """
    headers = dict(request.headers)
    body = request.json
    webhook_handler.handle(headers, body)
    return "OK"
