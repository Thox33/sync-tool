from contextlib import nullcontext as does_not_raise
from datetime import datetime

import pytest

from sync_tool.core.types import (
    FieldTypeInt,
    FieldTypeFloat,
    FieldTypeString,
    FieldTypeDatetime,
    FieldTypeReference,
    create_field_type,
    extract_attachments,
    FieldTypeRichText,
    RichTextValue,
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
        ("2022-01-01", does_not_raise()),
        ("test", pytest.raises(ValueError)),
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


def test_extract_attachments_single_image():
    # Given
    value = '<img src="https://example.com/image.jpg" alt="image" />'

    # When
    attachments = extract_attachments(value)

    # Then
    assert attachments == ["https://example.com/image.jpg"]


def test_extract_attachments_multiple_images():
    # Given
    value = (
        '<img src="https://example.com/image1.jpg" alt="image1" />'
        '<img src="https://example.com/image2.jpg" alt="image2" />'
    )

    # When
    attachments = extract_attachments(value)

    # Then
    assert attachments == [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg",
    ]


def test_extract_attachments_no_images():
    # Given
    value = "No images in this text"

    # When
    attachments = extract_attachments(value)

    # Then
    assert attachments == []


def test_extract_attachments_empty_src_attribute():
    # Given
    value = '<img src="" alt="empty src" />'

    # When
    attachments = extract_attachments(value)

    # Then
    assert attachments == []


def test_extract_attachments_empty_img_tag():
    # Given
    value = "<img />"

    # When
    attachments = extract_attachments(value)

    # Then
    assert attachments == []


def test_validate_value_valid_rich_text():
    # Given
    field = FieldTypeRichText(name="test_field", type="richtext")
    value = '<p>This is a <strong>rich text</strong> value.</p><img src="https://example.com/image.jpg" alt="image" />'

    # When
    result = field.validate_value(value)

    # Then
    assert isinstance(result, RichTextValue)
    assert result.value == value
    assert result.attachments == ["https://example.com/image.jpg"]


def test_validate_value_rich_text_no_attachments():
    # Given
    field = FieldTypeRichText(name="test_field", type="richtext")
    value = "<p>This is a <strong>rich text</strong> value.</p>"

    # When
    result = field.validate_value(value)

    # Then
    assert isinstance(result, RichTextValue)
    assert result.value == value
    assert result.attachments == []


def test_validate_value_invalid_rich_text():
    # Given
    field = FieldTypeRichText(name="test_field", type="richtext")
    value = 123

    # When/Then
    with pytest.raises(ValueError) as context:
        field.validate_value(value)

    assert str(context.value) == "Field test_field value 123 is not a string"


def test_validate_value_empty_string():
    # Given
    field = FieldTypeRichText(name="test_field", type="richtext")
    value = ""

    # When
    result = field.validate_value(value)

    # Then
    assert isinstance(result, RichTextValue)
    assert result.value == value
    assert result.attachments == []


def test_validate_value_multiple_attachments():
    # Given
    field = FieldTypeRichText(name="test_field", type="richtext")
    value = (
        "<p>This is a <strong>rich text</strong> value.</p>"
        '<img src="https://example.com/image1.jpg" alt="image1" />'
        '<img src="https://example.com/image2.jpg" alt="image2" />'
    )

    # When
    result = field.validate_value(value)

    # Then
    assert isinstance(result, RichTextValue)
    assert result.value == value
    assert result.attachments == [
        "https://example.com/image1.jpg",
        "https://example.com/image2.jpg",
    ]


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


def test_create_field_type_rich_text():
    field = create_field_type(type="richtext", name="test")
    assert isinstance(field, FieldTypeRichText)


def test_create_field_type_unknown():
    with pytest.raises(ValueError):
        create_field_type(type="unknown", name="test")
