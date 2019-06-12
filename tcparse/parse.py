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
    'Decorator to register a TwincatItem-based class'
    TWINCAT_TYPES[cls.__name__] = cls
    return cls


def separate_children_by_tag(children):
    '''
    Take in a list of `TwincatItem`s, categorize each by their XML tag, and
    return a dictionary keyed on tag.

    For example::

        <a> <a> <b> <b>

        Would become:
        {'a': [<a>, <a>],
         'b': [<b>, <b>]
         }

    Parameters
    ----------
    children : list
        list of TwincatItem

    Returns
    -------
    dict
        Categorized children
    '''
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
    '''
    Determine the Python class name for an element

    Parameters
    ----------
    element : lxml.etree.Element

    Returns
    -------
    class_name : str
    base_class : class
    '''

    tag = strip_namespace(element.tag)
    if tag == 'TcSmItem':
        return f'{tag}_' + element.attrib['ClassName'], TcSmItem
    if tag == 'Symbol':
        base_type, = element.xpath('BaseType')
        return f'{tag}_' + base_type.text, Symbol
    return tag, TwincatItem


class TwincatItem:
    def __init__(self, element, *, parent=None, name=None, filename=None):
        '''
        Represents a single TwinCAT project XML Element, for either tsproj,
        xti, tmc, etc.

        Parameters
        ----------
        element : lxml.etree.Element
        parent : TwincatItem, optional
        name : str, optional
        filename : pathlib.Path, optional
        '''
        self.attributes = dict(element.attrib)
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
        'Hook for subclasses; called after __init__'
        ...

    @property
    def root(self):
        'The top-level TwincatItem'
        parent = self
        while parent.parent is not None:
            parent = parent.parent
        return parent

    @property
    def qualified_path(self):
        'Path of classes required to get to this instance'
        hier = [self]
        parent = self.parent
        while parent:
            hier.append(parent)
            parent = parent.parent
        return '/'.join(strip_namespace(item.__class__.__name__)
                        for item in reversed(hier))

    def find_ancestor(self, cls):
        '''
        Find an ancestor of this instance

        Parameters
        ----------
        cls : TwincatItem
        '''
        parent = self.parent
        while parent and not isinstance(parent, cls):
            parent = parent.parent
        return parent

    def get_relative_path(self, path):
        '''
        Get an absolute path relative to this item

        Returns
        -------
        path : pathlib.Path
        '''
        root = pathlib.Path(self.filename).parent
        rel_path = pathlib.PureWindowsPath(path)
        return (root / rel_path).absolute()

    def find(self, cls):
        '''
        Find any descendents that are instances of cls

        Parameters
        ----------
        cls : TwincatItem
        '''
        for child in self.children:
            if isinstance(child, cls):
                yield child
            yield from child.find(cls)

    def _add_children(self, element):
        'A hook for adding all children'
        for child in element.iterchildren():
            self._add_child(child)

        by_tag = separate_children_by_tag(self.children)
        self.children_by_tag = types.SimpleNamespace(**by_tag)
        for key, value in by_tag.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    def _add_child(self, element):
        'Add a single child to the list of children'
        if isinstance(element, lxml.etree._Comment):
            self.comments.append(element.text)
            return

        child = self.parse(element, parent=self, filename=self.filename)
        self.children.append(child)

        # Two ways for names to come in:
        # 1. the child has a tag of 'Name', with its text being our name
        if child.tag == 'Name' and child.text and self.parent:
            name = child.text.strip()
            self.name = name

        # 2. the child has an attribute key 'Name'
        try:
            name = child.attributes.pop('Name').strip()
        except KeyError:
            ...
        else:
            child.name = name

    @staticmethod
    def parse(element, parent=None, filename=None):
        '''
        Parse an XML element and return a TwincatItem

        Parameters
        ----------
        element : lxml.etree.Element
        parent : TwincatItem, optional
            The parent to assign to the new element
        filename : str, optional
            The filename the element originates from

        Returns
        -------
        item : TwincatItem
        '''

        classname, base = element_to_class_name(element)

        try:
            cls = TWINCAT_TYPES[classname]
        except KeyError:
            # Dynamically create and register new TwincatItem-based types!
            cls = type(classname, (base, ), {})
            _register_type(cls)
        return cls(element, parent=parent, filename=filename)

    def _repr_info(self):
        '__repr__ information'
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
    '''
    [TMC] A Module

    Contains generated symbols, data areas, and miscellaneous properties.
    '''

    @property
    def ads_port(self):
        'The ADS port assigned to the Virtual PLC'
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
    '''
    [TMC] A property containing a key/value pair

    Examples of TMC properties::

          ApplicationName (used for the ADS port)
          ChangeDate
          GeneratedCodeSize
          GlobalDataSize
    '''
    ...


@_register_type
class Link(TwincatItem):
    '[XTI] Links between NC/PLC/IO'
    ...


@_register_type
class Symbol(TwincatItem):
    '''
    [TMC] A basic Symbol type

    This is dynamically subclassed into new classes for ease of implementation
    and searching.  For example, a function block defined as `FB_DriveVirtual`
    will become `Symbol_FB_DriveVirtual`.
    '''
    @property
    def nested_project(self):
        'The nested project (i.e., virtual PLC project) associated with the symbol'
        return self.find_ancestor(TcSmItem_CNestedPlcProjDef)

    @property
    def module(self):
        'The Module containing the Symbol'
        return self.find_ancestor(Module)

    @property
    def info(self):
        return dict(name=self.name,
                    bit_size=self.BitSize[0].text,
                    base_type=self.BaseType[0].text,
                    bit_offs=self.BitOffs[0].text,
                    module=self.module.name,
                    )


@_register_type
class Symbol_FB_DriveVirtual(Symbol):
    '''
    [TMC] A customized Symbol, representing only FB_DriveVirtual
    '''
    def _repr_info(self):
        '__repr__ information'
        repr_info = super()._repr_info()
        # Add on the NC axis name
        repr_info.update(nc_axis=self.short_nc_axis_name)
        return repr_info

    @property
    def program_name(self):
        '`Main` of `Main.M1`'
        return self.name.split('.')[0]

    @property
    def motor_name(self):
        '`M1` of `Main.M1`'
        return self.name.split('.')[1]

    @property
    def pou(self):
        'The POU program associated with the Symbol'
        return self.nested_project.pou_by_name[self.program_name]

    @property
    def call_block(self):
        '''
        A dictionary representation of the call

        For example::
            M1(a := 1, b := 2);

        Becomes::
            {'a': '1', 'b': '2'}
        '''
        return self.pou.call_blocks[self.motor_name]

    @property
    def linked_to(self):
        '''
        Where the axis is linked to, determined by the call block in the POU
        where the AXIS_REF is defined

        Returns
        -------
        linked_to : str
            e.g., M1Link
        linked_to_full : str
            e.g., Main.M1Link
        '''
        linked_to = self.call_block['Axis']
        linked_to_full = f'{self.program_name}.{linked_to}'
        return linked_to, linked_to_full

    @property
    def nc_to_plc_link(self):
        '''
        The Link for NcToPlc

        That is, how the NC axis is connected to the FB_DriveVirtual
        '''
        _, linked_to_full = self.linked_to

        links = [
            link
            for link in self.nested_project.find(Link)
            if '^' + linked_to_full.lower() in link.attributes['VarA'].lower()
            and 'NcToPlc' in link.attributes['VarA']
        ]

        link, = links
        return link

    @property
    def short_nc_axis_name(self):
        'A/B/C/Axis 1.xti -> Axis 1.xti'
        return self.nc_axis.filename.parts[-1]

    @property
    def nc_axis(self):
        'The NC `Axis` associated with the FB_DriveVirtual'
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
    '''
    [XTI] A Program Organization Unit
    '''

    # TODO: may fail when mixed with ladder logic?

    @property
    def declaration(self):
        'The declaration code; i.e., the top portion in visual studio'
        return self.Declaration[0].text

    @property
    def implementation(self):
        'The implementation code; i.e., the bottom portion in visual studio'
        impl = self.Implementation[0]
        if hasattr(impl, 'ST'):
            return impl.ST[0].text

    @property
    def call_blocks(self):
        'A dictionary of all implementation call blocks'
        return get_pou_call_blocks(self.declaration, self.implementation)

    @property
    def program_name(self):
        'The program name, determined from the declaration'
        return program_name_from_declaration(self.declaration)

    @property
    def variables(self):
        'A dictionary of variables defined in the POU'
        return variables_from_declaration(self.declaration)


@_register_type
class AxisPara(TwincatItem):
    '''
    [XTI] Axis Parameters

    Has information on units, acceleration, deadband, etc.
    '''
    ...


@_register_type
class NC(TwincatItem):
    '''
    [XTI] Top-level NC (or a link to it)
    '''
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
