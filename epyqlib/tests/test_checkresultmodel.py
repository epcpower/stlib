import epyqlib.attrsmodel


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=epyqlib.attrsmodel.check_result_types,
    root_type=epyqlib.attrsmodel.CheckResultRoot,
    columns=epyqlib.attrsmodel.check_result_columns,
)
