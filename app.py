"""
This file contains the main application logic for the Pull Request Generator,
including a webhook handler for creating pull requests when new branches are created.
"""
import logging
import sys

from flask import Flask, request
from github.Branch import Branch
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


@webhook_handler.webhook_handler(PushEvent)
def release(event: PushEvent) -> None:
    print(event)


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
