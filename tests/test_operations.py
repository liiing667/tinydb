import pytest

from tinydb import TinyDB, where
from tinydb.storages import JSONStorage
from tinydb.operations import delete, increment, decrement, add, subtract, set


def test_delete(db):
    db.update(delete('int'), where('char') == 'a')
    assert 'int' not in db.get(where('char') == 'a')


def test_add_int(db):
    db.update(add('int', 5), where('char') == 'a')
    assert db.get(where('char') == 'a')['int'] == 6


def test_add_str_raises(db):
    with pytest.raises(TypeError):
        db.update(add('char', 'xyz'), where('char') == 'a')


def test_subtract(db):
    db.update(subtract('int', 5), where('char') == 'a')
    assert db.get(where('char') == 'a')['int'] == -4


def test_set(db):
    db.update(set('char', 'xyz'), where('char') == 'a')
    assert db.get(where('char') == 'xyz')['int'] == 1


def test_increment(db):
    db.update(increment('int'), where('char') == 'a')
    assert db.get(where('char') == 'a')['int'] == 2


def test_decrement(db):
    db.update(decrement('int'), where('char') == 'a')
    assert db.get(where('char') == 'a')['int'] == 0


def test_set_nested_creates_intermediate_dicts(db):
    db.update(set('profile.name', 'x'), where('char') == 'a')
    doc = db.get(where('char') == 'a')
    assert doc['profile'] == {'name': 'x'}


def test_set_deeply_nested(db):
    db.update(set('a.b.c.d', 1), where('char') == 'a')
    assert db.get(where('char') == 'a')['a']['b']['c'] == {'d': 1}


def test_set_nested_overwrites_scalar_leaf(db):
    db.update(set('profile.name', 'old'), where('char') == 'a')
    db.update(set('profile.name', 'new'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile']['name'] == 'new'


def test_add_nested(db):
    db.update(set('stats.count', 1), where('char') == 'a')
    db.update(add('stats.count', 1), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 2


def test_subtract_nested(db):
    db.update(set('stats.count', 5), where('char') == 'a')
    db.update(subtract('stats.count', 2), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 3


def test_increment_nested(db):
    db.update(set('stats.count', 1), where('char') == 'a')
    db.update(increment('stats.count'), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 2


def test_decrement_nested(db):
    db.update(set('stats.count', 1), where('char') == 'a')
    db.update(decrement('stats.count'), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 0


def test_delete_nested(db):
    db.update(set('profile.name', 'x'), where('char') == 'a')
    db.update(delete('profile.name'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile'] == {}


def test_set_list_index(db):
    doc_id = db.insert({'items': ['a', 'b']})
    db.update(set('items.1', 'x'), doc_ids=[doc_id])
    assert db.get(doc_id=doc_id)['items'] == ['a', 'x']


def test_set_list_append(db):
    doc_id = db.insert({'items': ['a', 'b']})
    db.update(set('items.-', 'c'), doc_ids=[doc_id])
    assert db.get(doc_id=doc_id)['items'] == ['a', 'b', 'c']


def test_add_list_index(db):
    doc_id = db.insert({'items': [1, 2]})
    db.update(add('items.0', 4), doc_ids=[doc_id])
    assert db.get(doc_id=doc_id)['items'] == [5, 2]


def test_delete_list_index(db):
    doc_id = db.insert({'items': ['a', 'b']})
    db.update(delete('items.0'), doc_ids=[doc_id])
    assert db.get(doc_id=doc_id)['items'] == ['b']


def test_nested_list_of_dicts(db):
    doc_id = db.insert({'items': [{'name': 'a'}, {'name': 'b'}]})
    db.update(set('items.1.name', 'x'), doc_ids=[doc_id])
    assert db.get(doc_id=doc_id)['items'][1] == {'name': 'x'}


def test_escaped_separator_is_literal_key(db):
    db.update(set(r'profile\.name', 'x'), where('char') == 'a')
    doc = db.get(where('char') == 'a')
    assert doc['profile.name'] == 'x'
    assert 'profile' not in doc


def test_escaped_backslash(db):
    db.update(set(r'a\\b', 'x'), where('char') == 'a')
    assert db.get(where('char') == 'a')['a\\b'] == 'x'


def test_path_as_sequence_of_literal_segments(db):
    db.update(set(('profile.name',), 'x'), where('char') == 'a')
    doc = db.get(where('char') == 'a')
    assert doc['profile.name'] == 'x'


def test_custom_separator(db):
    db.update(set('profile/name', 'x', separator='/'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile']['name'] == 'x'


def test_custom_separator_does_not_split_on_dot(db):
    db.update(set('profile.name', 'x', separator='/'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile.name'] == 'x'


def test_custom_separator_literal_segments(db):
    db.update(set(('stats/count',), 1, separator='/'), where('char') == 'a')
    db.update(add(('stats/count',), 1, separator='/'), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats/count'] == 2


def test_list_index_out_of_range_raises(db):
    doc_id = db.insert({'items': ['a']})
    with pytest.raises(IndexError):
        db.update(set('items.5', 'x'), doc_ids=[doc_id])


def test_invalid_list_index_raises(db):
    doc_id = db.insert({'items': ['a']})
    with pytest.raises(ValueError):
        db.update(set('items.foo', 'x'), doc_ids=[doc_id])


def test_negative_list_index_raises(db):
    doc_id = db.insert({'items': ['a']})
    with pytest.raises(IndexError):
        db.update(set('items.-1', 'x'), doc_ids=[doc_id])


def test_traverse_into_non_container_raises(db):
    with pytest.raises(TypeError):
        db.update(set('char.first', 'x'), where('char') == 'a')


def test_add_to_string_nested_raises(db):
    db.update(set('profile.name', 'x'), where('char') == 'a')
    with pytest.raises(TypeError):
        db.update(add('profile.name', 1), where('char') == 'a')


def test_append_segment_only_allowed_at_end(db):
    doc_id = db.insert({'items': []})
    with pytest.raises(ValueError):
        db.update(set('items.-.name', 'x'), doc_ids=[doc_id])


def test_delete_append_segment_raises(db):
    doc_id = db.insert({'items': ['a']})
    with pytest.raises(ValueError):
        db.update(delete('items.-'), doc_ids=[doc_id])


def test_delete_missing_nested_raises(db):
    with pytest.raises(KeyError):
        db.update(delete('missing.deep'), where('char') == 'a')


def test_delete_missing_list_index_raises(db):
    doc_id = db.insert({'items': ['a']})
    with pytest.raises(IndexError):
        db.update(delete('items.2'), doc_ids=[doc_id])


def test_add_missing_leaf_raises(db):
    with pytest.raises(KeyError):
        db.update(add('stats.count', 1), where('char') == 'a')


def test_empty_path_segment_raises(db):
    with pytest.raises(ValueError):
        db.update(set('a..b', 'x'), where('char') == 'a')


def test_invalid_field_type_raises(db):
    with pytest.raises(TypeError):
        db.update(set(3, 'x'), where('char') == 'a')


def test_where_query_path_semantics_unchanged(db):
    # where('a.b') keeps treating 'a.b' as a single literal key and does
    # not adopt the path semantics of the update operations
    db.update(set('profile.name', 'x'), where('char') == 'a')
    assert db.get(where('profile.name').exists()) is None
    assert db.get(where('profile').name == 'x')['char'] == 'a'

    db.update(set(r'profile\.name', 'y'), where('char') == 'b')
    assert db.get(where('profile.name') == 'y')['char'] == 'b'


def test_json_storage_roundtrip(tmp_path):
    path = tmp_path / 'roundtrip.json'
    db = TinyDB(path, storage=JSONStorage)
    doc_id = db.insert({'id': 1, 'tags': ['a']})
    db.update(set('profile.name', 'x'), where('id') == 1)
    db.update(set('stats.count', 1), where('id') == 1)
    db.update(add('stats.count', 2), where('id') == 1)
    db.update(set('tags.-', 'b'), where('id') == 1)
    db.close()

    db2 = TinyDB(path, storage=JSONStorage)
    assert db2.get(doc_id=doc_id) == {
        'id': 1,
        'tags': ['a', 'b'],
        'profile': {'name': 'x'},
        'stats': {'count': 3},
    }
    db2.close()
