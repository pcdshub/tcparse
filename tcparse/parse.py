import collections
import os
import pathlib
import re
import sys
import types

import lxml
import lxml.etree


TWINCAT_TYPES = {}


def _register_type(cls):
    TWINCAT_TYPES[cls.__name__] = cls
    return cls


def separate_children_by_tag(children):
    d = collections.defaultdict(list)
    for child in children:
        d[child.tag].append(child)

    return d


def strip_namespace(tag):
    '''
    Strip off {{namespace}} from: {{namespace}}tag
    '''
    return lxml.etree.QName(tag).localname


def element_to_class_name(element):
    tag = strip_namespace(element.tag)
    if tag == 'TcSmItem':
        return f'{tag}_' + element.attrib['ClassName'], TcSmItem
    if tag == 'Symbol':
        base_type, = element.xpath('BaseType')
        return f'{tag}_' + base_type.text, Symbol
    return tag, TwincatItem


class TwincatItem:
    def __init__(self, element, *, attributes, parent=None, name=None,
                 filename=None):
        if attributes is None:
            attributes = {}

        self.attributes = dict(attributes)
        self.children = []
        self.comments = []
        self.children_by_tag = None
        self.element = element
        self.filename = filename
        self.name = name
        self.parent = parent
        self.tag = element.tag
        self.text = element.text.strip() if element.text else None

        self._add_children(element)
        self.post_init()

    def post_init(self):
        'Hook for subclasses'
        ...

    @property
    def root(self):
        parent = self
        while parent.parent is not None:
            parent = parent.parent
        return parent

    @property
    def qualified_name(self):
        hier = [self]
        parent = self.parent
        while parent:
            hier.append(parent)
            parent = parent.parent
        return '/'.join(strip_namespace(item.__class__.__name__)
                        for item in reversed(hier))

    def find_ancestor(self, cls):
        parent = self.parent
        while parent and not isinstance(parent, cls):
            parent = parent.parent
        return parent

    def get_relative_path(self, path):
        root = pathlib.Path(self.filename).parent
        rel_path = pathlib.PureWindowsPath(path)
        return (root / rel_path).absolute()

    def find(self, cls):
        for child in self.children:
            if isinstance(child, cls):
                yield child
            yield from child.find(cls)

    def _add_children(self, element):
        for child in element.iterchildren():
            self._add_child(child)

        by_tag = separate_children_by_tag(self.children)
        self.children_by_tag = types.SimpleNamespace(**by_tag)
        for key, value in by_tag.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def _add_child(self, element):
        if isinstance(element, lxml.etree._Comment):
            self.comments.append(element.text)
            return

        child = self.parse(element, parent=self, filename=self.filename)
        self.children.append(child)

        if child.tag == 'Name' and child.text and self.parent:
            name = child.text.strip()
            self.name = name

        try:
            name = child.attributes.pop('Name').strip()
        except KeyError:
            ...
        else:
            child.name = name

    @staticmethod
    def parse(element, parent=None, filename=None):
        classname, base = element_to_class_name(element)

        try:
            cls = TWINCAT_TYPES[classname]
        except KeyError:
            # Dynamically create and register new TwincatItem-based types!
            cls = type(classname, (base, ), {})
            _register_type(cls)
        return cls(element, attributes=element.attrib, parent=parent,
                   filename=filename)

    def _repr_info(self):
        return {
            'name': self.name,
            'attributes': self.attributes,
            'children': self.children,
            'text': self.text,
        }

    def __repr__(self):
        info = ' '.join(f'{key}={value!r}'
                        for key, value in self._repr_info().items()
                        if value)

        return f'<{self.__class__.__name__} {info}>'


@_register_type
class Module(TwincatItem):
    @property
    def ads_port(self):
        try:
            return self._ads_port
        except AttributeError:
            app_prop, = [prop for prop in self.find(Property)
                         if prop.name == 'ApplicationName']
            port_text = app_prop.Value[0].text
            self._ads_port = int(port_text.split('Port_')[1])

        return self._ads_port


@_register_type
class Property(TwincatItem):
    ...


@_register_type
class Link(TwincatItem):
    ...


@_register_type
class Symbol(TwincatItem):
    @property
    def nested_project(self):
        return self.find_ancestor(TcSmItem_CNestedPlcProjDef)

    @property
    def module(self):
        return self.find_ancestor(Module)

    @property
    def info(self):
        return dict(name=self.name,
                    bit_size=self.BitSize[0].text,
                    base_type=self.BaseType[0].text,
                    bit_offs=self.BitOffs[0].text,
                    )


@_register_type
class Symbol_FB_DriveVirtual(Symbol):
    def _repr_info(self):
        repr_info = super()._repr_info()
        repr_info.update(nc_axis=self.short_nc_axis_name)
        return repr_info

    @property
    def program_name(self):
        return self.name.split('.')[0]

    @property
    def motor_name(self):
        return self.name.split('.')[1]

    @property
    def pou(self):
        return self.nested_project.pou_by_name[self.program_name]

    @property
    def call_block(self):
        return self.pou.call_blocks[self.motor_name]

    @property
    def linked_to(self):
        linked_to = self.call_block['Axis']
        linked_to_full = f'{self.program_name}.{linked_to}'
        return linked_to, linked_to_full

    @property
    def nc_to_plc_link(self):
        _, linked_to_full = self.linked_to

        links = [
            link
            for link in self.nested_project.find(TWINCAT_TYPES['Link'])
            if '^' + linked_to_full.lower() in link.attributes['VarA'].lower()
            and 'NcToPlc' in link.attributes['VarA']
        ]

        link, = links
        return link

    @property
    def short_nc_axis_name(self):
        return self.nc_axis.filename.parts[-1]

    @property
    def nc_axis(self):
        link = self.nc_to_plc_link
        parent_name = link.parent.name.split('^')
        if parent_name[0] == 'TINC':
            parent_name = parent_name[1:]

        task_name, axis_section, axis_name = parent_name

        nc, = list(nc for nc in self.root.find(NC)
                   if nc.Axis and nc.SafTask[0].name == task_name)
        nc_axis = nc.axis_by_name[axis_name].Axis[0]
        # link nc_axis and FB_DriveVirtual?
        return nc_axis


@_register_type
class POU(TwincatItem):
    @property
    def declaration(self):
        return self.Declaration[0].text

    @property
    def implementation(self):
        impl = self.Implementation[0]
        if hasattr(impl, 'ST'):
            return impl.ST[0].text

    @property
    def call_blocks(self):
        return get_pou_call_blocks(self.declaration, self.implementation)

    @property
    def program_name(self):
        return program_name_from_declaration(self.declaration)

    @property
    def variables(self):
        return variables_from_declaration(self.declaration)


@_register_type
class AxisPara(TwincatItem):
    ...


@_register_type
class NC(TwincatItem):
    def post_init(self):
        if 'File' in self.attributes:
            # just a link to NC, not containing axes
            self.Axis = []
            return

        self.axis_by_id = {
            int(axis.attributes['Id']): axis.axis
            for axis in self.Axis
        }

        self.axis_by_name = {
            os.path.splitext(axis.attributes['File'])[0]: axis.axis
            for axis in self.Axis
        }


@_register_type
class Axis(TwincatItem):
    def post_init(self):
        try:
            axis_filename = self.attributes['File']
        except KeyError:
            # Axis inside of an 'Axis 1.xti' file
            self.axis_filename = None
            self.axis = None
            return

        self.axes_path = self.get_relative_path('Axes')
        self.axis_filename = self.axes_path / axis_filename
        self.axis = parse(self.axis_filename, parent=self)

    def find(self, cls):
        yield from super().find(cls)
        if self.axis is not None:
            yield from self.axis.find(cls)

    def summarize(self):
        yield from self.attributes.items()
        for param in self.find(AxisPara):
            yield from param.attributes.items()
            for child in param.children:
                for key, value in child.attributes.items():
                    yield f'{child.tag}:{key}', value

        for encoder in getattr(self, 'Encoder', []):
            for key, value in encoder.summarize():
                yield f'Enc:{key}', value


@_register_type
class EncPara(TwincatItem):
    ...


@_register_type
class Encoder(TwincatItem):
    def summarize(self):
        yield 'EncType', self.attributes['EncType']
        for param in self.find(EncPara):
            yield from param.attributes.items()
            for child in param.children:
                for key, value in child.attributes.items():
                    yield f'{child.tag}:{key}', value


@_register_type
class Project(TwincatItem):
    def post_init(self):
        self.project_root = pathlib.Path(self.filename).parent
        self.files = collections.defaultdict(dict)
        for attr, file in self.filenames:
            self.files[attr][str(file)] = parse(self.project_root / file,
                                                parent=self)

        self.plc_projects = {}
        # self._load_plc_projects(self.files['Plc'])

    def find(self, cls):
        yield from super().find(cls)
        for attr, files in self.files.items():
            for fn, file in files.items():
                yield from file.find(cls)

    @property
    def ams_id(self):
        return self.attributes['TargetNetId']

    @property
    def target_ip(self):
        ams_id = self.ams_id
        if ams_id.endswith('.1.1'):
            return ams_id[:-4]
        return ams_id  # :(

    @property
    def filenames(self):
        for attr, root in [
                ('Motion', '_Config/NC'),
                ('Plc', '_Config/PLC'),
                ('Io', '_Config/IO')
                ]:
            if not hasattr(self, attr):
                continue

            for section in getattr(self, attr):
                for item in section.children:
                    yield attr, pathlib.Path(root) / item.attributes['File']


@_register_type
class TcSmItem(TwincatItem):
    ...


@_register_type
class TcSmItem_CNcSafTaskDef(TcSmItem):
    def post_init(self):
        self.axes = list(self.find(Axis))


@_register_type
class TcSmItem_CNestedPlcProjDef(TcSmItem):
    def post_init(self):
        proj = self.Project[0]
        project_path = self.get_relative_path(proj.attributes['PrjFilePath'])
        tmc_path = self.get_relative_path(proj.attributes['TmcFilePath'])
        self.project = (parse(project_path, parent=self)
                        if project_path.exists()
                        else None)
        self.tmc = (parse(tmc_path, parent=self)
                    if tmc_path.exists()
                    else None)

        self.source_filenames = [
            self.project.get_relative_path(compile.attributes['Include'])
            for compile in self.find(Compile)
            if 'Include' in compile.attributes
        ]
        self.source = {
            str(fn.relative_to(self.project.project_root)):
            parse(fn, parent=self)
            for fn in self.source_filenames
        }

        self.pou_by_name = {
            plc_obj.POU[0].program_name: plc_obj.POU[0]
            for plc_obj in self.source.values()
            if hasattr(plc_obj, 'POU')
            and plc_obj.POU[0].program_name
        }

    def find(self, cls):
        yield from super().find(cls)
        if self.project is not None:
            yield from self.project.find(cls)

        if self.tmc is not None:
            yield from self.tmc.find(cls)


@_register_type
class Compile(TwincatItem):
    ...


def program_name_from_declaration(declaration):
    for line in declaration.splitlines():
        line = line.strip()
        if line.lower().startswith('program '):
            return line.split(' ')[1]


def lines_between(text, start_marker, end_marker, *, include_blank=False):
    found_start = False
    start_marker = start_marker.lower()
    end_marker = end_marker.lower()
    for line in text.splitlines():
        if line.lower() == start_marker:
            found_start = True
        elif line.lower() == end_marker:
            break
        elif found_start and (line.strip() or include_blank):
            yield line


def variables_from_declaration(declaration):
    variables = {}
    in_struct = False
    for line in lines_between(declaration, 'var', 'end_var'):
        line = line.strip()
        if in_struct:
            if line.lower().startswith('end_struct'):
                in_struct = False
            continue

        name, dtype, *_ = line.split(':')
        if ' ' in name:
            name, specifier = name.split(' ', 1)
            if specifier.lower().startswith('at '):
                specifier = specifier[2:]
        else:
            specifier = ''

        if dtype.lower() == 'struct':
            in_struct = True

        variables[name] = {
            'type': dtype.strip('; '),
            'spec': specifier.strip(),
        }

    return variables


def get_pou_call_blocks(declaration, implementation):
    variables = variables_from_declaration(declaration)
    blocks = collections.defaultdict(dict)

    # Match two groups: (var) := (value)
    # Only works for simple variable assignments.
    arg_value_re = re.compile(r'([a-zA-Z0-9_]+)\s*:=\s*([a-zA-Z0-9_\.]+)')

    for var in variables:
        # Find: VAR(.*);
        reg = re.compile(var + r'\s*\(\s*((?:.*?\n?)+)\)\s*;', re.MULTILINE)
        for match in reg.findall(implementation):
            call_body = ' '.join(line.strip() for line in match.splitlines())
            blocks[var].update(**dict(arg_value_re.findall(call_body)))

    return dict(blocks)


def load_project(fn):
    project = parse(fn)
    project = project.Project[0]
    return project


def parse(fn, *, parent=None):
    with open(fn, 'rt') as f:
        tree = lxml.etree.parse(f)

    root = tree.getroot()
    return TwincatItem.parse(root, filename=fn, parent=parent)


if __name__ == '__main__':
    try:
        fn = sys.argv[1]
    except IndexError:
        fn = '/Users/klauer/Repos/vonhamos-motion/twincat/VonHamos01/VonHamos01/VonHamos01.tsproj'

    project = load_project(fn)
    motors = list(project.find(Symbol_FB_DriveVirtual))
