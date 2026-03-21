"""Tests for the ``Model`` class attribute of ``orm.Entity`` subclasses."""

import datetime
import enum
import io

import pytest
from plumpy import get_object_loader
from pydantic import BaseModel

from aiida import orm
from aiida.common.datastructures import StashMode
from aiida.common.exceptions import UnsupportedConstructorModelError

orm_to_test = (
    orm.AuthInfo,
    orm.Comment,
    orm.Computer,
    orm.Group,
    orm.Log,
    orm.User,
    orm.ArrayData,
    orm.Bool,
    orm.CifData,
    orm.ContainerizedCode,
    orm.Data,
    orm.Dict,
    orm.EnumData,
    orm.Float,
    orm.FolderData,
    orm.InstalledCode,
    orm.Int,
    orm.JsonableData,
    orm.List,
    orm.PortableCode,
    orm.SinglefileData,
    orm.Str,
    orm.StructureData,
    orm.RemoteData,
    orm.RemoteStashData,
    orm.RemoteStashCompressedData,
)

entities_to_test = tuple(orm_class for orm_class in orm_to_test if not issubclass(orm_class, orm.Node))

nodes_to_test = tuple(orm_class for orm_class in orm_to_test if issubclass(orm_class, orm.Node))


class DummyEnum(enum.Enum):
    """Dummy enum for testing."""

    OPTION_A = 'a'
    OPTION_B = 'b'


class JsonableClass:
    """Dummy class that implements the required interface."""

    def __init__(self, data):
        """Construct a new object."""
        self._data = data

    @property
    def data(self):
        """Return the data of this instance."""
        return self._data

    def as_dict(self):
        """Represent the object as a JSON-serializable dictionary."""
        return {
            'data': self._data,
        }

    @classmethod
    def from_dict(cls, dictionary):
        """Reconstruct an instance from a serialized version."""
        return cls(dictionary['data'])


@pytest.fixture
def required_arguments(request, default_user, aiida_localhost, tmp_path):
    if request.param is orm.AuthInfo:
        return orm.AuthInfo, {'user': default_user, 'computer': aiida_localhost}
    if request.param is orm.Comment:
        return orm.Comment, {'user': default_user, 'node': orm.Data().store(), 'content': ''}
    if request.param is orm.Computer:
        return orm.Computer, {'label': 'localhost'}
    if request.param is orm.Group:
        return orm.Group, {'label': 'group'}
    if request.param is orm.Log:
        return orm.Log, {
            'time': datetime.datetime.now(),
            'loggername': 'logger',
            'levelname': 'REPORT',
            'message': 'message',
            'dbnode_id': orm.Data().store().pk,
        }
    if request.param is orm.User:
        return orm.User, {'email': 'test@localhost'}
    if request.param is orm.ArrayData:
        return orm.ArrayData, {
            'attributes': {},
            'args': {'arrays': {'test_array': [1, 0, 0]}},
        }
    if request.param is orm.Bool:
        return orm.Bool, {'attributes': {'value': True}}
    if request.param is orm.CifData:
        return orm.CifData, {
            'attributes': {},
            'args': {'filename': 'structure.cif', 'content': 'structure-content'},
        }
    if request.param is orm.ContainerizedCode:
        return orm.ContainerizedCode, {
            'attributes': {
                'filepath_executable': '/bin/echo',
                'image_name': 'docker://alpine:3',
                'engine_command': 'docker run {image_name}',
            },
            'args': {
                'label': 'containerized_echo',
                'description': 'Containerized echo code',
                'computer': aiida_localhost.label,
                'filepath_executable': '/bin/echo',
                'image_name': 'docker://alpine:3',
                'engine_command': 'docker run {image_name}',
            },
        }
    if request.param is orm.Data:
        return orm.Data, {'attributes': {'source': {'uri': 'http://127.0.0.1'}}}
    if request.param is orm.Dict:
        return orm.Dict, {
            'attributes': {'a': 1, 'b': 2},
            'args': {'value': {'a': 1, 'b': 2}},
        }
    if request.param is orm.EnumData:
        return orm.EnumData, {
            'attributes': {
                'name': 'OPTION_A',
                'value': 'a',
                'identifier': get_object_loader().identify_object(DummyEnum),
            },
            'args': {
                'member': DummyEnum.OPTION_A,
            },
        }
    if request.param is orm.Float:
        return orm.Float, {'attributes': {'value': 1.0}}
    if request.param is orm.FolderData:
        (tmp_path / 'binary_file').write_bytes(b'byte content')
        (tmp_path / 'text_file').write_text('text content')
        return orm.FolderData, {
            'attributes': {},
            'args': {
                'tree': tmp_path,
            },
        }
    if request.param is orm.InstalledCode:
        return orm.InstalledCode, {
            'attributes': {
                'input_plugin': 'core.arithmetic.add',
                'filepath_executable': '/bin/echo',
            },
            'args': {
                'label': 'echo',
                'description': 'Installed echo code',
                'computer': aiida_localhost.label,
                'filepath_executable': '/bin/echo',
            },
        }
    if request.param is orm.Int:
        return orm.Int, {'attributes': {'value': 1}}
    if request.param is orm.JsonableData:
        return orm.JsonableData, {
            'attributes': {
                'data': 1,
                '@class': 'JsonableClass',
                '@module': 'tests.orm.models.test_models',
            },
            'args': {
                'obj': JsonableClass(1),
            },
        }
    if request.param is orm.List:
        return orm.List, {'attributes': {'list': [1, 2, 3]}}
    if request.param is orm.PortableCode:
        (tmp_path / 'code.sh').write_text('#!/bin/bash\necho "$@"\n')
        return orm.PortableCode, {
            'attributes': {
                'filepath_executable': 'code.sh',
            },
            'args': {
                'label': 'portable_code',
                'description': 'Portable code',
                'filepath_executable': 'code.sh',
                'filepath_files': str(tmp_path),
            },
        }
    if request.param is orm.SinglefileData:
        return orm.SinglefileData, {
            'attributes': {},
            'args': {'filename': 'file.txt', 'content': 'some-content'},
        }
    if request.param is orm.Str:
        return orm.Str, {'attributes': {'value': 'string'}}
    if request.param is orm.StructureData:
        return orm.StructureData, {
            'attributes': {
                'cell': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'pbc1': True,
                'pbc2': True,
                'pbc3': True,
                'sites': [{'kind_name': 'H', 'position': (0.0, 0.0, 0.0)}],
                'kinds': [{'name': 'H', 'mass': 1.0, 'symbols': ('H',), 'weights': (1.0,)}],
            }
        }
    if request.param is orm.RemoteData:
        return orm.RemoteData, {'attributes': {'remote_path': '/some/path'}}
    if request.param is orm.RemoteStashData:
        return orm.RemoteStashData, {'attributes': {'stash_mode': StashMode.COMPRESS_TAR}}
    if request.param is orm.RemoteStashCompressedData:
        return orm.RemoteStashCompressedData, {
            'attributes': {
                'stash_mode': StashMode.COMPRESS_TAR,
                'target_basepath': '/some/path',
                'source_list': ['/some/file'],
                'dereference': True,
            }
        }
    raise NotImplementedError()


@pytest.mark.parametrize(
    'required_arguments',
    orm_to_test,
    indirect=True,
)
def test_model_overrides(required_arguments):
    cls: type[orm.Entity] = required_arguments[0]
    name = cls.__name__

    assert cls.ReadModel.__qualname__ == f'{name}.ReadModel'
    assert cls.ReadModel.model_config.get('title') == f'{name}ReadModel'

    assert cls.WriteModel.__qualname__ == f'{name}.WriteModel'
    assert cls.WriteModel.model_config.get('title') == f'{name}WriteModel'


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_attributes_model_overrides(required_arguments):
    cls: type[orm.Node] = required_arguments[0]

    name = cls.__name__

    AttributesModel = cls.ReadModel.model_fields['attributes'].annotation  # noqa: N806
    assert AttributesModel is cls.AttributesModel
    assert AttributesModel.__qualname__ == f'{name}.AttributesModel'
    assert AttributesModel.model_config.get('title') == f'{name}AttributesModel'

    AttributesWriteModel = cls.WriteModel.model_fields['attributes'].annotation  # noqa: N806
    assert AttributesWriteModel is cls.AttributesModel._as_write_model()
    assert AttributesWriteModel.__qualname__ == f'{name}.AttributesWriteModel'
    assert AttributesWriteModel.model_config.get('title') == f'{name}AttributesWriteModel'


def _validate_value(value):
    if isinstance(value, dict):
        return {k: _validate_value(v) for k, v in value.items()}
    if isinstance(value, io.BytesIO):
        value.seek(0)
        return value.read()
    return value


# NOTE: Logs are automatically stored, so `to_model` would default to `ReadModel`,
# blocking the roundtrip (read-only fields not accepted by write models). Hence,
# in the entity tests, we must explicitly specify the `WriteModel` schema.


@pytest.mark.parametrize(
    'required_arguments',
    entities_to_test,
    indirect=True,
)
def test_roundtrip_entity_from_model(required_arguments):
    cls: type[orm.Entity] = required_arguments[0]
    kwargs: dict = required_arguments[1]

    entity: orm.Entity = cls(**kwargs)
    assert isinstance(entity, cls)

    model = entity.to_model(schema=cls.WriteModel)
    assert isinstance(model, BaseModel)

    roundtrip = cls.from_model(model)
    assert isinstance(roundtrip, cls)

    roundtrip_model = roundtrip.to_model(schema=cls.WriteModel)
    assert _validate_value(roundtrip_model) == _validate_value(model)


@pytest.mark.parametrize(
    'required_arguments',
    entities_to_test,
    indirect=True,
)
def test_roundtrip_entity_from_serialized(required_arguments):
    cls: type[orm.Entity] = required_arguments[0]
    kwargs: dict = required_arguments[1]

    entity = cls(**kwargs)
    assert isinstance(entity, cls)

    serialized_entity = entity.serialize(schema=cls.WriteModel)

    roundtrip = cls.from_serialized(serialized_entity)
    assert isinstance(roundtrip, cls)

    roundtrip_serialized = roundtrip.serialize(schema=cls.WriteModel)
    assert roundtrip_serialized == serialized_entity


def _assert_roundtrip_field_values_equal(
    cls: type[orm.Node],
    original_model: orm.Node.BaseNodeModel,
    roundtrip_entity: orm.Node,
    schema: type[orm.Node.BaseNodeModel],
    tmp_path,
):
    context = {'repository_path': tmp_path}
    roundtrip_model = roundtrip_entity.to_model(context=context, schema=schema)

    assert roundtrip_model.node_type == original_model.node_type
    if isinstance(original_model, cls.WriteModel):
        assert _validate_value(roundtrip_model.attributes) == _validate_value(original_model.attributes)
    elif isinstance(original_model, cls.ConstructorModel):
        assert _validate_value(roundtrip_model.args) == _validate_value(original_model.args)


def _generate_files_dict_from_tree(tree_path):
    import os

    files_dict = {}
    for root, _, files in os.walk(tree_path):
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, tree_path)
            with open(file_path, 'rb') as handle:
                files_dict[relative_path] = io.BytesIO(handle.read())
    return files_dict


def _get_write_model(cls: type[orm.Node], attributes: dict[str, object]):
    return cls.WriteModel(node_type=cls.class_node_type, attributes=attributes)


def _get_constructor_model(cls: type[orm.Node], args: dict[str, object]):
    return cls.ConstructorModel(node_type=cls.class_node_type, args=args)


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_roundtrip_node_from_model_attributes(required_arguments, tmp_path):
    cls: type[orm.Node] = required_arguments[0]
    attributes: dict = required_arguments[1]['attributes']

    model = _get_write_model(cls, attributes)
    assert isinstance(model, BaseModel)

    roundtrip = cls.from_model(model)
    assert isinstance(roundtrip, cls)

    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.WriteModel, tmp_path)


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_roundtrip_node_from_model_constructor(required_arguments, tmp_path):
    cls: type[orm.Node] = required_arguments[0]
    args: dict | None = required_arguments[1].get('args')

    if args is None:
        with pytest.raises(UnsupportedConstructorModelError):
            cls.ConstructorModel
        return

    model = _get_constructor_model(cls, args)
    assert isinstance(model, BaseModel)

    roundtrip = cls.from_model(model)
    assert isinstance(roundtrip, cls)

    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.ConstructorModel, tmp_path)


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_roundtrip_node_from_serialized_attributes(required_arguments, tmp_path):
    cls: type[orm.Node] = required_arguments[0]
    attributes: dict = required_arguments[1]['attributes']

    entity = cls.from_model(_get_write_model(cls, attributes))
    assert isinstance(entity, cls)

    try:
        entity.store()
    except Exception:
        pass

    context = {'repository_path': tmp_path}
    serialized_entity = entity.serialize(context=context, mode='python', dump_repo=True, schema=cls.WriteModel)
    files_dict = _generate_files_dict_from_tree(tmp_path)
    roundtrip = cls.from_serialized(serialized_entity, files=files_dict)

    assert isinstance(roundtrip, cls)
    model = cls.WriteModel(**serialized_entity)
    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.WriteModel, tmp_path)


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_roundtrip_node_from_serialized_constructor(required_arguments, tmp_path):
    cls: type[orm.Node] = required_arguments[0]
    args: dict | None = required_arguments[1].get('args')

    if args is None:
        with pytest.raises(UnsupportedConstructorModelError):
            cls.ConstructorModel
        return

    model = _get_constructor_model(cls, args)
    serialized_entity = model.model_dump(mode='python', exclude_none=True)
    roundtrip = cls.from_serialized(serialized_entity)
    assert isinstance(roundtrip, cls)

    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.ConstructorModel, tmp_path)
