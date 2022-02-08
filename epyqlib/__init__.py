# For development, the __version__ is set to the build placeholder 0.0.0
# For release, the __version__ is the actual released version
__version__ = "0.0.0"

__sha__ = "SHA_to_be_removed?"
__version_tag__ = "version_tag_to_be_removed?"
__build_tag__ = "build_tag_to_be_removed?"

# import operator
#
# import epyqlib._build
# import epyqlib._version
#
#
# __version__, __sha__ = operator.itemgetter("version", "full-revisionid")(
#     epyqlib._version.get_versions(),
# )
#
# __version_tag__ = "v{}-{}".format(__version__, __sha__)
# __build_tag__ = epyqlib._build.job_id
