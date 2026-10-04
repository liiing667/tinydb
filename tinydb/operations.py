"""
A collection of update operations for TinyDB.

They are used for updates like this:

>>> db.update(delete('foo'), where('foo') == 2)

This would delete the ``foo`` field from all documents where ``foo`` equals 2.

All operations resolve their first argument as a *path* into nested
documents. Path segments are separated by ``.`` by default (configurable via
the ``separator`` keyword argument). Missing intermediate dictionaries are
created automatically, numeric segments index into lists and ``-`` appends a
new element to a list. Keys that literally contain the separator can be
addressed by escaping it with a backslash (``a\\.b``), by passing the path as
a tuple/list of literal segments, or by setting ``separator=None``.
"""


from collections.abc import Callable, MutableMapping
from typing import Any, Optional, Sequence, Union

__all__ = ('delete', 'add', 'subtract', 'set', 'increment', 'decrement')

#: The default separator used to split a field name into path segments.
DEFAULT_SEPARATOR = '.'

#: A field path: either a (possibly separated) string or a sequence of
#: literal path segments.
PathLike = Union[str, Sequence[str]]


def _split_path(field: PathLike, separator: Optional[str]) -> tuple:
    """
    Split ``field`` into path segments using ``separator``.

    A non-string ``field`` is treated as a sequence of literal segments.
    ``separator=None`` (or an empty separator) disables splitting so the
    field name is used literally. Occurrences of the separator escaped with
    a backslash are kept literally, as is an escaped backslash.
    """
    if isinstance(field, (tuple, list)):
        return tuple(field)
    if not separator:
        return (field,)

    segments = []
    buf = ''
    i = 0
    while i < len(field):
        if field[i] == '\\' and i + 1 < len(field):
            rest = field[i + 1:]
            if rest.startswith(separator):
                buf += separator
                i += 1 + len(separator)
                continue
            if rest[0] == '\\':
                buf += '\\'
                i += 2
                continue
        if field.startswith(separator, i):
            segments.append(buf)
            buf = ''
            i += len(separator)
            continue
        buf += field[i]
        i += 1
    segments.append(buf)
    return tuple(segments)


def _to_index(segment: Any) -> Optional[int]:
    """
    Interpret ``segment`` as a list index, returning ``None`` if it is not
    a valid index (``-`` alone means *append* and is not an index).
    """
    if isinstance(segment, bool):
        return None
    if isinstance(segment, int):
        return segment
    if isinstance(segment, str) and segment != '-' \
            and segment.lstrip('-').isdigit():
        return int(segment)
    return None


def _is_append(segment: Any) -> bool:
    return segment == '-'


def _new_container(next_segment: Any) -> Union[dict, list]:
    """
    Create the container to auto-fill a missing intermediate path segment,
    based on the segment that will be addressed inside it.
    """
    if _is_append(next_segment) or _to_index(next_segment) is not None:
        return []
    return {}


def _traverse(doc: MutableMapping, segments: tuple, path: PathLike):
    """
    Walk ``segments[:-1]`` starting at ``doc``, creating missing intermediate
    containers, and return ``(parent, segments[-1])`` where ``parent`` is the
    container holding the final segment.
    """
    current = doc
    for depth, segment in enumerate(segments[:-1]):
        next_segment = segments[depth + 1]
        if isinstance(current, MutableMapping):
            if segment not in current:
                current[segment] = _new_container(next_segment)
            child = current[segment]
        elif isinstance(current, list):
            if _is_append(segment):
                child = _new_container(next_segment)
                current.append(child)
            else:
                index = _to_index(segment)
                if index is None:
                    raise TypeError(
                        f'Cannot use {segment!r} as a list index while '
                        f'resolving path {path!r}'
                    )
                try:
                    child = current[index]
                except IndexError:
                    raise IndexError(
                        f'List index {index} out of range while resolving '
                        f'path {path!r}'
                    ) from None
        else:
            raise TypeError(
                f'Cannot descend into {type(current).__name__} value '
                f'{current!r} at segment {segment!r} of path {path!r}'
            )
        current = child
    return current, segments[-1]


def _read(parent: Any, segment: Any, path: PathLike) -> Any:
    """
    Read ``segment`` from its parent container.
    """
    if isinstance(parent, MutableMapping):
        try:
            return parent[segment]
        except KeyError:
            raise KeyError(
                f'No such key {segment!r} while resolving path {path!r}'
            ) from None
    if isinstance(parent, list):
        index = _to_index(segment)
        if index is None:
            raise TypeError(
                f'Cannot use {segment!r} as a list index while resolving '
                f'path {path!r}'
            )
        try:
            return parent[index]
        except IndexError:
            raise IndexError(
                f'List index {index} out of range while resolving '
                f'path {path!r}'
            ) from None
    raise TypeError(
        f'Cannot read segment {segment!r} of path {path!r} from '
        f'{type(parent).__name__} value {parent!r}'
    )


def _write(parent: Any, segment: Any, value: Any, path: PathLike,
           allow_append: bool) -> None:
    """
    Write ``value`` at ``segment`` of its parent container.
    """
    if isinstance(parent, MutableMapping):
        parent[segment] = value
        return
    if isinstance(parent, list):
        if _is_append(segment):
            if not allow_append:
                raise ValueError(
                    f'\'-\' (append) is not supported for this operation '
                    f'while resolving path {path!r}'
                )
            parent.append(value)
            return
        index = _to_index(segment)
        if index is None:
            raise TypeError(
                f'Cannot use {segment!r} as a list index while resolving '
                f'path {path!r}'
            )
        try:
            parent[index] = value
        except IndexError:
            raise IndexError(
                f'List index {index} out of range while resolving '
                f'path {path!r}'
            ) from None
        return
    raise TypeError(
        f'Cannot write segment {segment!r} of path {path!r} into '
        f'{type(parent).__name__} value {parent!r}'
    )


def delete(field: PathLike, *, separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Delete a given field from the document.

    :param field: the field path to delete
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    segments = _split_path(field, separator)

    def transform(doc: MutableMapping):
        parent, segment = _traverse(doc, segments, field)
        if isinstance(parent, MutableMapping):
            try:
                del parent[segment]
            except KeyError:
                raise KeyError(
                    f'No such key {segment!r} while resolving path {field!r}'
                ) from None
            return
        if isinstance(parent, list):
            index = _to_index(segment)
            if index is None:
                raise TypeError(
                    f'Cannot use {segment!r} as a list index while resolving '
                    f'path {field!r}'
                )
            try:
                del parent[index]
            except IndexError:
                raise IndexError(
                    f'List index {index} out of range while resolving '
                    f'path {field!r}'
                ) from None
            return
        raise TypeError(
            f'Cannot delete segment {segment!r} of path {field!r} from '
            f'{type(parent).__name__} value {parent!r}'
        )

    return transform


def add(field: PathLike, n: Union[int, float], *,
        separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Add ``n`` to a given field in the document.

    :param field: the field path to add to
    :param n: the value to add
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    segments = _split_path(field, separator)

    def transform(doc: MutableMapping):
        parent, segment = _traverse(doc, segments, field)
        current = _read(parent, segment, field)
        try:
            result = current + n
        except TypeError:
            raise TypeError(
                f'Cannot add {n!r} to {type(current).__name__} value '
                f'{current!r} at path {field!r}'
            ) from None
        _write(parent, segment, result, field, allow_append=False)

    return transform


def subtract(field: PathLike, n: Union[int, float], *,
             separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Subtract ``n`` from a given field in the document.

    :param field: the field path to subtract from
    :param n: the value to subtract
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    segments = _split_path(field, separator)

    def transform(doc: MutableMapping):
        parent, segment = _traverse(doc, segments, field)
        current = _read(parent, segment, field)
        try:
            result = current - n
        except TypeError:
            raise TypeError(
                f'Cannot subtract {n!r} from {type(current).__name__} value '
                f'{current!r} at path {field!r}'
            ) from None
        _write(parent, segment, result, field, allow_append=False)

    return transform


def set(field: PathLike, val: Any, *,
        separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Set a given field to ``val``.

    :param field: the field path to set
    :param val: the value to set
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    segments = _split_path(field, separator)

    def transform(doc: MutableMapping):
        parent, segment = _traverse(doc, segments, field)
        _write(parent, segment, val, field, allow_append=True)

    return transform


def increment(field: PathLike, *, separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Increment a given field in the document by 1.

    :param field: the field path to increment
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    return add(field, 1, separator=separator)


def decrement(field: PathLike, *, separator: Optional[str] = DEFAULT_SEPARATOR) \
        -> Callable[[MutableMapping], None]:
    """
    Decrement a given field in the document by 1.

    :param field: the field path to decrement
    :param separator: the path segment separator (``None`` disables
        path parsing)
    """
    return subtract(field, 1, separator=separator)
