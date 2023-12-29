"""
This file contains the main application logic for the Pull Request Generator,
including a webhook handler for creating pull requests when new branches are created.
"""
import logging
import re
import sys
from typing import Optional

from flask import Flask, request
from github.Branch import Branch
from github.Commit import Commit
from github.GitCommit import GitCommit
from github.PullRequest import PullRequest
from github.Repository import Repository
from githubapp import webhook_handler
from githubapp.events import PushEvent

app = Flask("Auto Release Generator")
app.__doc__ = "This is a Flask application auto merging pull requests."

# if sentry_dns := os.getenv("SENTRY_DNS"):  # pragma: no cover
#     # Initialize Sentry SDK for error logging
#     sentry_sdk.init(sentry_dns)

logger = logging.getLogger(__name__)
logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)


def get_commit_message_command(commit: GitCommit, command_prefix: str) -> Optional[str]:
    """
    Retrieve the command from the commit message.
    The command in the commit message must be in the format [command_prefix: command]

    :param commit: The Commit object.
    :param command_prefix: The command prefix to look for in the commit message.
    :return: The extracted command or None if there is no command.
    :raises: ValueError if the command is not valid.
    """
    commit_message = commit.message
    command_pattern = rf"\[{command_prefix}:(.+?)\]"
    commands_found = re.findall(command_pattern, commit_message)
    if commands_found:
        return commands_found[-1].strip()
    return None


@webhook_handler.webhook_handler(PushEvent)
def release(event: PushEvent) -> None:
    last_command = None
    for commit in event.commits:
        last_command = last_command or get_commit_message_command(commit, "release")
    repository = event.repository
    version_file = repository.get_contents("app/__init__.py", ref=event.ref)
    version_file = version_file.decoded_content
    version_file = version_file.decode()
    print(last_command)


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