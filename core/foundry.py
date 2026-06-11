"""Foundry client — reads host + token from .env. One place for Foundry config."""
import os
from pathlib import Path

from dotenv import load_dotenv
from foundry_sdk import FoundryClient, UserTokenAuth

# Load .env from the project root regardless of where a script is run from.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

HOST = os.environ["FOUNDRY_HOST"]
TOKEN = os.environ["FOUNDRY_TOKEN"]
ONTOLOGY = os.environ.get("FOUNDRY_ONTOLOGY", "default")

client = FoundryClient(auth=UserTokenAuth(TOKEN), hostname=HOST)
