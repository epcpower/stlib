# For development and git commit, the __version__ variable below is set
# to the build placeholder "0.0.0". (In other words: leave alone!)
# For release/distribution, the __version__ variable below is modified
# during CI by poetry dynamic versioning with the github tagged version.


def serialize_pep440(
    base: str,
    stage: Optional[str] = None,
    revision: Optional[int] = None,
    post: Optional[int] = None,
    dev: Optional[int] = None,
    epoch: Optional[int] = None,
    metadata: Optional[Sequence[Union[str, int]]] = None,
) -> str:

__version__ = "0.0.0"

import epyqlib._build

__version_tag__ = "v{}".format(__version__)
__build_tag__ = epyqlib._build.job_id
