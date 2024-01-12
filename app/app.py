"""
This module contains the Flask application and routes for the auto release
generator app.
"""
import logging
import os
import re
import sys
from string import Template
from typing import Optional

import sentry_sdk
import yaml
from flask import Flask
from github import UnknownObjectException
from githubapp import webhook_handler
from githubapp.events import PushEvent

logging.basicConfig(
    stream=sys.stdout,
    format="%(levelname)s:%(module)s:%(funcName)s:%(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
APP_NAME = "Auto Release Generator"
__version__ = "0.1"
app = Flask(APP_NAME)


def sentry_init():
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


sentry_init()
webhook_handler.handle_with_flask(app, version=__version__, versions_to_show=["github-app-handler"])


def _escape_markdown(text):
    escape_chars = r"_*~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


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
    head_commit = event.head_commit
    head_commit.update()

    event.start_check_run(
        APP_NAME, head_commit.sha, title="Checking for release command"
    )

    last_command = None
    for commit in event.commits:
        last_command = last_command or get_command(commit.message, "release")
    if last_command is None:
        event.update_check_run(
            title="No release command found",
            conclusion="success",
        )
        return

    version_to_release = last_command
    event.update_check_run(
        title=f"Releasing {version_to_release}",
        summary=f"Checking for release command ✅\nReleasing {version_to_release}",
    )

    if event.ref.endswith(repository.default_branch):
        repository.create_git_release(
            tag=version_to_release, generate_release_notes=True
        )
        return

    try:
        config = (
            yaml.safe_load(
                repository.get_contents(
                    ".autoreleasegenerator.yml", ref=event.ref
                ).decoded_content
            )
            or {}
        )
    except UnknownObjectException:
        event.update_check_run(
            title=f"Releasing {version_to_release} ❌",
            summary=f"Checking for release command ✅\nReleasing {version_to_release} ❌",
            text="No .autoreleasegenerator.yml file found in the branch",
            conclusion="failure",
        )
        return

    if (version_file_path := config.get("file_path")) is None:
        event.update_check_run(
            title=f"Releasing {version_to_release} ❌",
            summary=f"Checking for release command ✅\nReleasing {version_to_release} ❌",
            text="Missing 'file_path' configuration in .autoreleasegenerator.yml file",
            conclusion="failure",
        )
        return

    try:
        original_file = repository.get_contents(
            version_file_path, ref=repository.default_branch
        )
    except UnknownObjectException:
        event.update_check_run(
            title=f"Releasing {version_to_release} ❌",
            summary=f"Checking for release command ✅\nReleasing {version_to_release} ❌",
            text=f"No {_escape_markdown(version_file_path)} file found in the branch",
            conclusion="failure",
        )
        return

    version_pattern = config.get("version_pattern", r"__version__ = \"$version\"")
    version_pattern = Template(version_pattern).substitute(version="(.+)")
    original_file_content = original_file.decoded_content.decode()
    if pattern_found := re.search(version_pattern, original_file_content):
        original_version_in_file = pattern_found.group(1)
    else:
        event.update_check_run(
            title=f"Releasing {version_to_release} ❌",
            summary=f"Checking for release command ✅\nReleasing {version_to_release} ❌",
            text=f"No version with the pattern '{_escape_markdown(version_pattern)}' "
            f"found in {_escape_markdown(version_file_path)}",
            conclusion="failure",
        )
        return

    file_to_update = repository.get_contents(version_file_path, ref=event.ref)
    file_to_update_current_content = file_to_update.decoded_content.decode()
    new_content = original_file_content.replace(
        original_version_in_file, version_to_release
    )
    if new_content != file_to_update_current_content:
        print(f"Updating {version_file_path} with {version_to_release}")
        repository.update_file(
            version_file_path,
            f"Release {last_command}",
            new_content,
            file_to_update.sha,
            branch=event.ref,
        )
        event.update_check_run(
            title="Release Complete ✅",
            summary=f"Released {version_to_release} ✅",
            text=f"Release version updated to '{version_to_release}' in {_escape_markdown(version_file_path)}",
            conclusion="success",
        )
