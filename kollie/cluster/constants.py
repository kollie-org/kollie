import json
import os

KOLLIE_NAMESPACE = os.environ.get("KOLLIE_NAMESPACE", "kollie")

common_substitutions_path = os.getenv("KOLLIE_COMMON_SUBSTITUTIONS_JSON_PATH", "common_substitutions.json")
with open(common_substitutions_path, "r") as common_substitutions_file:
    KOLLIE_COMMON_SUBSTITUTIONS = json.loads(common_substitutions_file.read())

DEFAULT_FLUX_REPOSITORY = os.environ.get("KOLLIE_DEFAULT_FLUX_REPOSITORY")
