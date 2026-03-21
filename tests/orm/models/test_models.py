"""Tests for the ``Model`` class attribute of ``Entity`` subclasses."""

import datetime
import enum
import io

import pytest
from plumpy import get_object_loader
from pydantic import BaseModel

from aiida.common.datastructures import StashMode
from aiida.common.exceptions import UnsupportedConstructorModelError
from aiida.orm import AuthInfo, Comment, Computer, Entity, Group, Log, Node, User
from aiida.orm.nodes.data import (
    ArrayData,
    Bool,
    CifData,
    ContainerizedCode,
    Data,
    Dict,
    EnumData,
    Float,
    FolderData,
    InstalledCode,
    Int,
    JsonableData,
    List,
    PortableCode,
    RemoteData,
    RemoteStashCompressedData,
    RemoteStashData,
    SinglefileData,
    Str,
    StructureData,
)

orm_to_test = (
    # AuthInfo,
    # Comment,
    # Computer,
    # Group,
    # Log,
    # User,
    # ArrayData,
    # Bool,
    # CifData,
    # ContainerizedCode,
    # Data,
    # Dict,
    # EnumData,
    # Float,
    # FolderData,
    InstalledCode,
    # Int,
    # JsonableData,
    # List,
    # PortableCode,
    # SinglefileData,
    # Str,
    # StructureData,
    # RemoteData,
    # RemoteStashData,
    # RemoteStashCompressedData,
)

entities_to_test = tuple(orm_class for orm_class in orm_to_test if not issubclass(orm_class, Node))

nodes_to_test = tuple(orm_class for orm_class in orm_to_test if issubclass(orm_class, Node))


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
    if request.param is AuthInfo:
        return AuthInfo, {'user': default_user, 'computer': aiida_localhost}
    if request.param is Comment:
        return Comment, {'user': default_user, 'node': Data().store(), 'content': ''}
    if request.param is Computer:
        return Computer, {'label': 'localhost'}
    if request.param is Group:
        return Group, {'label': 'group'}
    if request.param is Log:
        return Log, {
            'time': datetime.datetime.now(),
            'loggername': 'logger',
            'levelname': 'REPORT',
            'message': 'message',
            'dbnode_id': Data().store().pk,
        }
    if request.param is User:
        return User, {'email': 'test@localhost'}
    if request.param is ArrayData:
        return ArrayData, {
            'attributes': {},
            'args': {'arrays': [1, 0, 0]},
        }
    if request.param is Bool:
        return Bool, {'attributes': {'value': True}}
    if request.param is CifData:
        return CifData, {
            'attributes': {},
            'args': {'filename': 'structure.cif', 'content': 'structure-content'},
        }
    if request.param is ContainerizedCode:
        return ContainerizedCode, {
            'attributes': {
                'computer': aiida_localhost.label,
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
    if request.param is Data:
        return Data, {'attributes': {'source': {'uri': 'http://127.0.0.1'}}}
    if request.param is Dict:
        return Dict, {
            'attributes': {'a': 1, 'b': 2},
            'args': {'value': {'a': 1, 'b': 2}},
        }
    if request.param is EnumData:
        return EnumData, {
            'attributes': {
                'name': 'OPTION_A',
                'value': 'a',
                'identifier': get_object_loader().identify_object(DummyEnum),
            },
            'args': {
                'member': DummyEnum.OPTION_A,
            },
        }
    if request.param is Float:
        return Float, {'attributes': {'value': 1.0}}
    if request.param is FolderData:
        (tmp_path / 'binary_file').write_bytes(b'byte content')
        (tmp_path / 'text_file').write_text('text content')
        return FolderData, {'attributes': {'tree': tmp_path}}
    if request.param is InstalledCode:
        return InstalledCode, {
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
    if request.param is Int:
        return Int, {'attributes': {'value': 1}}
    if request.param is JsonableData:
        return JsonableData, {
            'attributes': {
                'data': 1,
                '@class': 'JsonableClass',
                '@module': 'tests.orm.models.test_models',
            },
            'args': {
                'obj': JsonableClass(1),
            },
        }
    if request.param is List:
        return List, {'attributes': {'list': [1, 2, 3]}}
    if request.param is PortableCode:
        (tmp_path / 'code.sh').write_text('#!/bin/bash\necho "$@"\n')
        return PortableCode, {
            'attributes': {
                'filepath_executable': 'code.sh',
                'filepath_files': tmp_path,
            },
            'args': {
                'label': 'portable_code',
                'description': 'Portable code',
                'filepath_executable': 'code.sh',
                'filepath_files': str(tmp_path),
            },
        }
    if request.param is SinglefileData:
        return SinglefileData, {
            'attributes': {},
            'args': {'filename': 'file.txt', 'content': 'some-content'},
        }
    if request.param is Str:
        return Str, {'attributes': {'value': 'string'}}
    if request.param is StructureData:
        return StructureData, {
            'attributes': {
                'cell': [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                'pbc1': True,
                'pbc2': True,
                'pbc3': True,
                'sites': [{'kind_name': 'H', 'position': (0.0, 0.0, 0.0)}],
                'kinds': [{'name': 'H', 'mass': 1.0, 'symbols': ('H',), 'weights': (1.0,)}],
            }
        }
    if request.param is RemoteData:
        return RemoteData, {'attributes': {'remote_path': '/some/path'}}
    if request.param is RemoteStashData:
        return RemoteStashData, {'attributes': {'stash_mode': StashMode.COMPRESS_TAR}}
    if request.param is RemoteStashCompressedData:
        return RemoteStashCompressedData, {
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
    cls: type[Entity] = required_arguments[0]
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
    cls: type[Node] = required_arguments[0]

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


def _assert_roundtrip_field_values_equal(
    cls: type[Entity],
    original_model: BaseModel,
    roundtrip_entity: Entity,
    schema: type[BaseModel],
    tmp_path,
):
    context = {'repository_path': tmp_path} if issubclass(cls, Node) else None
    roundtrip_model = roundtrip_entity.to_model(context=context, schema=schema)
    original_field_values = cls._model_to_orm_field_values(original_model, schema)

    for key, value in cls._model_to_orm_field_values(roundtrip_model, schema).items():
        assert _validate_value(value) == _validate_value(original_field_values[key])


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


def _get_write_model(cls: type[Node], attributes: dict[str, object]):
    return cls.WriteModel(node_type=cls.class_node_type, attributes=attributes)


def _get_constructor_model(cls: type[Node], args: dict[str, object]):
    return cls.ConstructorModel(node_type=cls.class_node_type, args=args)


@pytest.mark.parametrize(
    'required_arguments',
    entities_to_test,
    indirect=True,
)
def test_roundtrip_entity_from_model(required_arguments, tmp_path):
    cls: type[Entity] = required_arguments[0]
    kwargs: dict = required_arguments[1]

    entity: Entity = cls(**kwargs)
    assert isinstance(entity, cls)

    context = {'repository_path': tmp_path} if issubclass(cls, Node) else None
    model = entity.to_model(context=context, schema=cls.WriteModel)
    assert isinstance(model, BaseModel)

    roundtrip = cls.from_model(model)
    assert isinstance(roundtrip, cls)

    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.WriteModel, tmp_path)


@pytest.mark.parametrize(
    'required_arguments',
    entities_to_test,
    indirect=True,
)
def test_roundtrip_entity_from_serialized(required_arguments, tmp_path):
    cls: type[Entity] = required_arguments[0]
    kwargs: dict = required_arguments[1]

    entity = cls(**kwargs)
    assert isinstance(entity, cls)

    try:
        entity.store()
    except Exception:
        pass

    serialized_entity = entity.serialize(mode='python', schema=cls.WriteModel)
    roundtrip = cls.from_serialized(serialized_entity)
    assert isinstance(roundtrip, cls)

    model = cls.WriteModel(**serialized_entity)
    _assert_roundtrip_field_values_equal(cls, model, roundtrip, cls.WriteModel, tmp_path)


@pytest.mark.parametrize(
    'required_arguments',
    nodes_to_test,
    indirect=True,
)
def test_roundtrip_node_from_model_attributes(required_arguments, tmp_path):
    cls: type[Node] = required_arguments[0]
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
    cls: type[Node] = required_arguments[0]
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
    cls: type[Node] = required_arguments[0]
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
    cls: type[Node] = required_arguments[0]
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
