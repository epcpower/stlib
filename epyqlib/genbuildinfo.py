import os
import textwrap

import click


@click.command()
@click.argument("target", type=click.File("w"), default="-")
def write_build_file(target):
    template = textwrap.dedent(
        """\
    # This file has been generated


    """
    )

    target.write(template)

    values = {
        name: None
        for name in (
            "build_system",
            "build_id",
            "build_number",
            "build_version",
            "job_id",
            "job_url",
        )
    }

    if os.environ.get("APPVEYOR") == "True":
        values["build_system"] = "AppVeyor"
        mapping = {
            "build_id": "APPVEYOR_BUILD_ID",
            "build_number": "APPVEYOR_BUILD_NUMBER",
            "build_version": "APPVEYOR_BUILD_VERSION",
            "job_id": "APPVEYOR_JOB_ID",
        }
        values.update({k: os.environ[v] for k, v in mapping.items()})
        values[
            "job_url"
        ] = "https://ci.appveyor.com/" "project/{account}/{slug}/build/job/{id}".format(
            account=os.environ["APPVEYOR_ACCOUNT_NAME"],
            slug=os.environ["APPVEYOR_PROJECT_SLUG"],
            id=os.environ["APPVEYOR_JOB_ID"],
        )
    elif os.environ.get("GITHUB_ACTIONS") == "True":
        GITHUB_RUN_ID = os.environ.get("GITHUB_RUN_ID", "None")
        GITHUB_RUN_NUMBER = os.environ.get("GITHUB_RUN_NUMBER", "None")
        GITHUB_SERVER_URL = os.environ.get("GITHUB_SERVER_URL", "None")
        GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "None")
        values["build_system"] = "GitHub Actions"
        values["job_id"] = f"{GITHUB_RUN_ID}_{GITHUB_RUN_NUMBER}"
        mapping = {
            "build_id": "GITHUB_RUN_ID",
            "build_number": "GITHUB_RUN_NUMBER",
            # "build_version": "APPVEYOR_BUILD_VERSION",
            # "job_id": "GITHUB_JOB",
        }
        values.update({k: os.environ[v] for k, v in mapping.items()})
        values[
            "job_url"
        ] = f"{GITHUB_SERVER_URL}/{GITHUB_REPOSITORY}/actions/runs/{GITHUB_RUN_ID}"

    for k, v in values.items():
        target.write("{} = {}\n".format(k, repr(v)))
