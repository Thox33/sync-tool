from contextlib import nullcontext as does_not_raise
from datetime import datetime

import pytest

from sync_tool.core.data.type.field_type import (
    FieldTypeInt,
    FieldTypeFloat,
    FieldTypeString,
    FieldTypeDatetime,
    FieldTypeReference,
    create_field_type,
)


@pytest.mark.parametrize(
    "input,expected",
    [
        (123, does_not_raise()),
        (123.456, pytest.raises(ValueError)),
        ("123", pytest.raises(ValueError)),
    ],
)
def test_field_type_int_validate(input, expected):
    field = FieldTypeInt(name="test", type="int")

    with expected:
        field.validate_value(input)


@pytest.mark.parametrize(
    "input,expected",
    [
        (123, pytest.raises(ValueError)),
        (123.456, does_not_raise()),
        ("123", pytest.raises(ValueError)),
    ],
)
def test_field_type_float_validate(input, expected):
    field = FieldTypeFloat(name="test", type="float")

    with expected:
        field.validate_value(input)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("hello", does_not_raise()),
        (123, does_not_raise()),
        ({}, pytest.raises(ValueError)),
    ],
)
def test_field_type_string_validate(input, expected):
    field = FieldTypeString(name="test", type="string")

    with expected:
        field.validate_value(input)


@pytest.mark.parametrize(
    "input,expected",
    [
        (datetime.now(), does_not_raise()),
        ("2022-01-01", pytest.raises(ValueError)),
    ],
)
def test_field_type_datetime_validate(input, expected):
    field = FieldTypeDatetime(name="test", type="datetime")

    with expected:
        field.validate_value(input)


@pytest.mark.parametrize(
    "input,expected",
    [
        ("123", does_not_raise()),
        (123, does_not_raise()),
        ({}, pytest.raises(ValueError)),
    ],
)
def test_field_type_reference_validate(input, expected):
    field = FieldTypeReference(name="test", type="reference", reference_type="users")

    with expected:
        field.validate_value(input)


def test_create_field_type_int():
    field = create_field_type(type="int", name="test")
    assert isinstance(field, FieldTypeInt)


def test_create_field_type_float():
    field = create_field_type(type="float", name="test")
    assert isinstance(field, FieldTypeFloat)


def test_create_field_type_string():
    field = create_field_type(type="string", name="test")
    assert isinstance(field, FieldTypeString)


def test_create_field_type_datetime():
    field = create_field_type(type="datetime", name="test")
    assert isinstance(field, FieldTypeDatetime)


def test_create_field_type_reference():
    field = create_field_type(type="reference", name="test", reference_type="users")
    assert isinstance(field, FieldTypeReference)


def test_create_field_type_unknown():
    with pytest.raises(ValueError):
        create_field_type(type="unknown", name="test")
