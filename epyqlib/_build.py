# This file should be overwritten when a distribution build is done


try:
    from epyqlib._build_generated import *
except ImportError:
    build_system = None
    build_id = None
    build_number = None
    build_version = None
    job_id = None
    job_url = None
