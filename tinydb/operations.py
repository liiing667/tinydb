"""
A collection of update operations for TinyDB.

They are used for updates like this:

>>> db.update(delete('foo'), where('foo') == 2)

This would delete the ``foo`` field from all documents where ``foo`` equals 2.

All operations interpret their ``field`` argument as a *path* into nested
documents: segments are split on ``separator`` (``.`` by default), missing
intermediate dictionaries are created on the fly, lists are addressed with
numeric indices and ``-`` as the final segment appends to a list:

>>> db.update(set('profile.name', 'x'), where('id') == 1)
>>> db.update(add('stats.count', 1), where('id') == 1)
>>> db.update(set('tags.-', 'new-tag'), where('id') == 1)

To address a key that literally contains the separator, escape it with a
backslash (e.g. ``'profile\\\\.name'``) or pass the path as a sequence of
segments (e.g. ``('profile.name',)``) which is used verbatim.
"""


from collections.abc import Callable, MutableMapping, Sequence
from typing import Any, Optional, Union

__all__ = ('delete', 'add', 'subtract', 'set', 'increment', 'decrement')

#: The default separator used to split a field path into segments
DEFAULT_SEPARATOR = '.'

#: The path segment that appends a new element to a list
APPEND_SEGMENT = '-'

#: A field path, either as a separator-joined string or as a sequence of
#: literal segments
PathLike = Union[str, Sequence[str]]


def _parse_path(field: PathLike, separator: str) -> list:
    """
    Split ``field`` into path segments.

    A sequence of segments is used verbatim. A string is split on
    ``separator``; a backslash escapes the separator (and itself) so keys
    that literally contain the separator can be addressed.
    """
    if isinstance(field, (list, tuple)):
        parts = [str(part) for part in field]
    elif isinstance(field, str):
        if not separator:
            raise ValueError('The path separator must not be empty')

        parts = []
        buf: list = []
        pos = 0
        while pos < len(field):
            if field[pos] == '\\' and pos + 1 < len(field):
                if field[pos + 1] == '\\':
                    buf.append('\\')
                    pos += 2
                    continue
                if field.startswith(separator, pos + 1):
                    buf.append(separator)
                    pos += 1 + len(separator)
                    continue
            if field.startswith(separator, pos):
                parts.append(''.join(buf))
                buf = []
                pos += len(separator)
                continue
            buf.append(field[pos])
            pos += 1
        parts.append(''.join(buf))
    else:
        raise TypeError(
            f'Field path must be a string or a sequence of segments, '
            f'got {type(field).__name__}'
        )

    if not parts or any(part == '' for part in parts):
        raise ValueError(f'Invalid empty path segment in {field!r}')

    return parts


def _list_index(segment: str, field: PathLike,
                allow_append: bool) -> Optional[int]:
    """
    Convert a path ``segment`` into a list index.

    Returns ``None`` for the append segment (``-``) if ``allow_append`` is
    set. Raises a clear error for anything that is not a valid,
    non-negative index.
    """
    if segment == APPEND_SEGMENT:
        if allow_append:
            return None
        raise ValueError(
            f'Invalid path {field!r}: {APPEND_SEGMENT!r} (append) is only '
            f'allowed as the final path segment'
        )

    try:
        index = int(segment)
    except ValueError:
        raise ValueError(
            f'Invalid path {field!r}: {segment!r} is not a valid list index'
        ) from None

    if index < 0:
        raise IndexError(
            f'Invalid path {field!r}: negative list index {index}'
        )

    return index


def _resolve_parent(doc: MutableMapping, parts: list, field: PathLike,
                    create: bool) -> Any:
    """
    Walk all but the last path segment and return the container holding
    the final segment.

    Missing intermediate dictionaries are created if ``create`` is set.
    """
    current: Any = doc
    for segment in parts[:-1]:
        if isinstance(current, list):
            index = _list_index(segment, field, allow_append=False)
            assert index is not None
            if index >= len(current):
                raise IndexError(
                    f'List index {index} out of range in path {field!r}'
                )
            child = current[index]
        else:
            if segment not in current:
                if not create:
                    raise KeyError(
                        f'No such field {segment!r} in path {field!r}'
                    )
                current[segment] = {}
            child = current[segment]

        if not isinstance(child, (MutableMapping, list)):
            raise TypeError(
                f'Cannot traverse into {type(child).__name__} value '
                f'{child!r} while resolving path {field!r}'
            )

        current = child

    return current


def _leaf_key(container: Any, segment: str, field: PathLike,
              allow_append: bool) -> Any:
    """
    Return the key (for a mapping) or index (for a list) that addresses
    the final path ``segment`` within ``container``.

    Returns ``None`` for the list append segment if ``allow_append`` is set.
    """
    if isinstance(container, list):
        index = _list_index(segment, field, allow_append=allow_append)
        if index is not None and index >= len(container):
            raise IndexError(
                f'List index {index} out of range in path {field!r}'
            )
        return index
    return segment


def delete(field: PathLike,
           separator: str = DEFAULT_SEPARATOR
           ) -> Callable[[MutableMapping], None]:
    """
    Delete a given field from the document.

    :param field: the path of the field to delete
    :param separator: the path segment separator (default: ``.``)
    """
    def transform(doc: MutableMapping):
        parts = _parse_path(field, separator)
        container = _resolve_parent(doc, parts, field, create=False)
        key = _leaf_key(container, parts[-1], field, allow_append=False)
        try:
            del container[key]
        except KeyError:
            raise KeyError(
                f'No such field {parts[-1]!r} in path {field!r}'
            ) from None

    return transform


def _arithmetic(field: PathLike, n: Union[int, float], op: Callable,
                op_name: str, separator: str
                ) -> Callable[[MutableMapping], None]:
    """
    Build a transform that applies a numeric operation to a field.
    """
    def transform(doc: MutableMapping):
        parts = _parse_path(field, separator)
        container = _resolve_parent(doc, parts, field, create=False)
        key = _leaf_key(container, parts[-1], field, allow_append=False)
        try:
            value = container[key]
        except KeyError:
            raise KeyError(
                f'No such field {parts[-1]!r} in path {field!r}'
            ) from None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                f'Cannot {op_name} non-numeric value {value!r} of type '
                f'{type(value).__name__} at path {field!r}'
            )
        container[key] = op(value, n)

    return transform


def add(field: PathLike, n: Union[int, float],
        separator: str = DEFAULT_SEPARATOR
        ) -> Callable[[MutableMapping], None]:
    """
    Add ``n`` to a given numeric field in the document.

    :param field: the path of the field to update
    :param n: the value to add
    :param separator: the path segment separator (default: ``.``)
    """
    return _arithmetic(field, n, lambda value, n: value + n, 'add to',
                       separator)


def subtract(field: PathLike, n: Union[int, float],
             separator: str = DEFAULT_SEPARATOR
             ) -> Callable[[MutableMapping], None]:
    """
    Subtract ``n`` from a given numeric field in the document.

    :param field: the path of the field to update
    :param n: the value to subtract
    :param separator: the path segment separator (default: ``.``)
    """
    return _arithmetic(field, n, lambda value, n: value - n,
                       'subtract from', separator)


def set(field: PathLike, val: Any,
        separator: str = DEFAULT_SEPARATOR
        ) -> Callable[[MutableMapping], None]:
    """
    Set a given field to ``val``.

    Missing intermediate dictionaries are created on the fly. If the final
    segment is ``-`` and the containing value is a list, ``val`` is
    appended to that list.

    :param field: the path of the field to set
    :param val: the value to set
    :param separator: the path segment separator (default: ``.``)
    """
    def transform(doc: MutableMapping):
        parts = _parse_path(field, separator)
        container = _resolve_parent(doc, parts, field, create=True)
        key = _leaf_key(container, parts[-1], field, allow_append=True)
        if key is None:
            container.append(val)
        else:
            container[key] = val

    return transform


def increment(field: PathLike,
              separator: str = DEFAULT_SEPARATOR
              ) -> Callable[[MutableMapping], None]:
    """
    Increment a given numeric field in the document by 1.

    :param field: the path of the field to increment
    :param separator: the path segment separator (default: ``.``)
    """
    return _arithmetic(field, 1, lambda value, n: value + n, 'increment',
                       separator)


def decrement(field: PathLike,
              separator: str = DEFAULT_SEPARATOR
              ) -> Callable[[MutableMapping], None]:
    """
    Decrement a given numeric field in the document by 1.

    :param field: the path of the field to decrement
    :param separator: the path segment separator (default: ``.``)
    """
    return _arithmetic(field, 1, lambda value, n: value - n, 'decrement',
                       separator)
