import epyqlib.attrsmodel
import epyqlib.checkresultmodel


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=epyqlib.checkresultmodel.types,
    root_type=epyqlib.checkresultmodel.Root,
    columns=epyqlib.checkresultmodel.columns,
)
