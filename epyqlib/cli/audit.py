import collections
import pathlib

import click
import dulwich.repo
import phabricator


def reference_to_sha(repository, reference):
    references = repository.get_refs()

    maybe_hash = references.get(reference)
    if maybe_hash is not None:
        return maybe_hash

    maybe_refs = {
        ref: hash
        for ref, hash in references.items()
        if ref.split(b"/")[-1] == reference
    }

    [hash] = maybe_refs.values()
    return hash


def get_hash_list(path, old_reference, new_reference):
    repository = dulwich.repo.Repo(path)

    old_hash = reference_to_sha(repository=repository, reference=old_reference)
    new_hash = reference_to_sha(repository=repository, reference=new_reference)

    old_walker = repository.get_walker(include=[old_hash])
    old_parents = next(iter(old_walker)).commit.parents

    walker = repository.get_walker(
        include=[new_hash],
        exclude=old_parents,
    )
    hashes = [entry.commit.id for entry in walker]

    return hashes


def get_all_commits(phab, hashes):
    after = None
    collected = []

    while True:
        result = phab.request(
            "diffusion.commit.search",
            {
                "after": after,
                "constraints": {
                    "identifiers": [hash.decode("ascii") for hash in hashes],
                },
            },
        )
        collected.extend(result["data"])
        after = result["cursor"]["after"]
        if after is None:
            break

    result = phab.request(
        "phid.lookup",
        {
            "names": [
                *[data["phid"] for data in collected],
                *[data["fields"]["repositoryPHID"] for data in collected],
            ],
        },
    )

    for data in collected:
        data["uri"] = result[data["phid"]]["uri"]
        data["fullName"] = result[data["fields"]["repositoryPHID"]]["fullName"]

    return collected


def create_command(default_phabricator_url=None):
    phabricator_option_extras = {}

    if default_phabricator_url is not None:
        phabricator_option_extras["default"] = default_phabricator_url

    @click.command()
    @click.option(
        "--target",
        "targets",
        help="path to the repository root, old reference, new reference",
        multiple=True,
        type=(
            click.Path(exists=True, file_okay=False, resolve_path=True),
            str,
            str,
        ),
        required=True,
    )
    @click.option(
        "--phabricator-url",
        help="The base URL for the Phabricator server.",
        type=str,
        required=True,
        **phabricator_option_extras,
    )
    @click.option(
        "--api-token",
        help="""
            Your phabricator API token.
            These are managed under your user settings then 'Conduit API Tokens'.
        """,
        type=str,
        required=True,
    )
    def cli(targets, phabricator_url, api_token):
        all_hashes = []

        for target_path, old_reference, new_reference in targets:
            target_path = pathlib.Path(target_path)

            old_reference = old_reference.encode("utf-8")
            new_reference = new_reference.encode("utf-8")

            all_hashes.extend(
                get_hash_list(
                    path=target_path,
                    old_reference=old_reference,
                    new_reference=new_reference,
                )
            )

        phab = phabricator.Phabricator(
            phabricator_url,
            "altendky",
            token=api_token,
        )

        results = collections.defaultdict(list)
        commits = get_all_commits(phab=phab, hashes=all_hashes)

        for commit in commits:
            fields = commit["fields"]
            full_hash = fields["identifier"]
            audit_status = fields["auditStatus"]["value"]
            full_name = commit["fullName"]
            uri = commit["uri"]

            link = f"[[ {uri} | {full_name} {full_hash} ]]"

            results[audit_status].append(link)

        sorted_results = dict(sorted(results.items()))
        for status, links in sorted_results.items():
            print(f"- {status}: {len(links)}")

        print()

        for status, links in sorted_results.items():
            print(f"- {status}:")

            for link in links:
                print(f"  - {link}")

            print()

    return cli
