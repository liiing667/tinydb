import pytest

from tinydb import where
from tinydb.operations import delete, increment, decrement, add, subtract, set


def test_delete(db):
    db.update(delete('int'), where('char') == 'a')
    assert 'int' not in db.get(where('char') == 'a')


def test_add_int(db):
    db.update(add('int', 5), where('char') == 'a')
    assert db.get(where('char') == 'a')['int'] == 6


def test_add_str(db):
    db.update(add('char', 'xyz'), where('char') == 'a')
    assert db.get(where('char') == 'axyz')['int'] == 1


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


def test_set_nested(db):
    db.update(set('profile.name', 'x'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile'] == {'name': 'x'}


def test_set_nested_creates_intermediate_dicts(db):
    db.update(set('a.b.c', 1), where('char') == 'a')
    assert db.get(where('char') == 'a')['a'] == {'b': {'c': 1}}


def test_add_nested(db):
    db.update(set('stats.count', 1), where('char') == 'a')
    db.update(add('stats.count', 5), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 6


def test_increment_decrement_nested(db):
    db.update(set('stats.count', 1), where('char') == 'a')
    db.update(increment('stats.count'), where('char') == 'a')
    db.update(decrement('stats.count'), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 1


def test_subtract_nested(db):
    db.update(set('stats.count', 10), where('char') == 'a')
    db.update(subtract('stats.count', 4), where('char') == 'a')
    assert db.get(where('char') == 'a')['stats']['count'] == 6


def test_delete_nested(db):
    db.update(set('profile.name', 'x'), where('char') == 'a')
    db.update(delete('profile.name'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile'] == {}


def test_list_index(db):
    db.update(set('tags', ['a', 'b']), where('char') == 'a')
    db.update(set('tags.1', 'z'), where('char') == 'a')
    assert db.get(where('char') == 'a')['tags'] == ['a', 'z']


def test_list_append(db):
    db.update(set('tags', ['a']), where('char') == 'a')
    db.update(set('tags.-', 'b'), where('char') == 'a')
    assert db.get(where('char') == 'a')['tags'] == ['a', 'b']


def test_list_index_out_of_range(db):
    db.update(set('tags', ['a']), where('char') == 'a')
    with pytest.raises(IndexError):
        db.update(set('tags.5', 'b'), where('char') == 'a')


def test_descend_into_non_container(db):
    with pytest.raises(TypeError):
        db.update(set('int.deeper', 1), where('char') == 'a')


def test_add_on_string_raises(db):
    with pytest.raises(TypeError):
        db.update(add('char', 1), where('char') == 'a')


def test_custom_separator(db):
    db.update(set('profile/name', 'x', separator='/'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile'] == {'name': 'x'}


def test_separator_none_disables_path_parsing(db):
    db.update(set('profile.name', 'x', separator=None), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile.name'] == 'x'


def test_literal_key_with_separator_via_tuple(db):
    db.update(set(('profile.name',), 'x'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile.name'] == 'x'


def test_literal_key_with_separator_via_escape(db):
    db.update(set(r'profile\.name', 'x'), where('char') == 'a')
    assert db.get(where('char') == 'a')['profile.name'] == 'x'
