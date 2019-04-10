import json

import attr
import ccstudiodss.api
import ccstudiodss.cli
import click
import javabridge

import epyqlib.cmemoryparser
import epyqlib.variableselectionmodel


project_name = 'epyqlib'


@click.group()
def main():
    pass


@main.command()
@ccstudiodss.cli.create_binary_option(project_name=project_name)
@ccstudiodss.cli.create_ccxml_option(project_name=project_name)
@ccstudiodss.cli.ccs_base_path_option
def dss(binary, ccxml, ccs_base_path):
    ccstudiodss.api.add_jars(base_path=ccs_base_path)

    model = epyqlib.variableselectionmodel.VariableModel(
        nvs=None,
        nv_model=None,
        bus=None,
    )

    binary_info = epyqlib.cmemoryparser.process_file(binary)
    model.update_from_loaded_binary_without_threads(binary_info=binary_info)

    try:
        with ccstudiodss.api.Session(ccxml=ccxml) as session:
            session.load(binary=binary, timeout=10000)
            session.run()

            traverser = Traverser(session=session)

            try:
                model.root.traverse(call_this=traverser, internal_nodes=True)
            except Exception as e:
                print()

            for comparison in traverser.failures():
                print('FAILED:', comparison.node.qualified_name(), comparison)

            print()
    except Exception as e:
        print()


@main.command(name='json')
@ccstudiodss.cli.create_binary_option(project_name=project_name)
@click.option('--json', 'json_file', type=click.File('r'), required=True)
def json_command(binary, json_file):
    model = epyqlib.variableselectionmodel.VariableModel(
        nvs=None,
        nv_model=None,
        bus=None,
    )

    binary_info = epyqlib.cmemoryparser.process_file(binary)
    model.update_from_loaded_binary_without_threads(binary_info=binary_info)

    loaded = json.load(json_file)

    try:
        traverser = JsonTraverser(name_to_addresses=dict(loaded))

        try:
            model.root.traverse(call_this=traverser, internal_nodes=True)
        except Exception as e:
            print()

        for comparison in traverser.failures():
            print('FAILED:', comparison.node.qualified_name(), comparison)

        print()
    except Exception as e:
        print()


@attr.s
class Comparison:
    node = attr.ib(default=None)
    dss_address = attr.ib(default=None)
    exception = attr.ib(default=None)

    def matches(self):
        if self.node is None:
            return False

        # if isinstance(self.node.variable, epyqlib.cmemoryparser.Variable):
        #     address = self.node.variable.address
        # elif isinstance(self.node.variable, epyqlib.cmemoryparser.StructMember):
        #

        address = int(self.node.fields.address[2:], 16)

        return address == self.dss_address


@attr.s
class Traverser:
    session = attr.ib()
    collected = attr.ib(factory=list)

    def __call__(self, node, payload):
        if node.tree_parent is None:
            return

        # if node.tree_parent.tree_parent is not None:
        #     print()

        print(node.qualified_name())

        try:
            dss_address = self.session.debug_session.expression.evaluate(
                '&' + node.qualified_name()
            )
        except javabridge.JavaException as e:
            comparison = Comparison(node=node, exception=e)
        else:
            comparison = Comparison(node=node, dss_address=dss_address)

        self.collected.append(comparison)

    def failures(self):
        return [
            comparison
            for comparison in self.collected
            if not comparison.matches()
        ]


@attr.s
class JsonTraverser:
    name_to_addresses = attr.ib()
    collected = attr.ib(factory=list)

    def __call__(self, node, payload):
        if node.tree_parent is None:
            return

        # if node.tree_parent.tree_parent is not None:
        #     print()

        print(node.qualified_name())

        try:
            dss_address = self.name_to_addresses[node.qualified_name()]
        except KeyError as e:
            comparison = Comparison(node=node, exception=e)
        else:
            comparison = Comparison(node=node, dss_address=dss_address)

        self.collected.append(comparison)

    def failures(self):
        return [
            comparison
            for comparison in self.collected
            if not comparison.matches()
        ]
