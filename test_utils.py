import pytest
from utils import normalize_player_name

def test_normalize_player_name():
    assert normalize_player_name("Nicolás Mardones") == "nicolas mardones"
    assert normalize_player_name("Nicolas Mardones") == "nicolas mardones"
    assert normalize_player_name("  Nicolás   Mardones  ") == "nicolas mardones"
    assert normalize_player_name("ALVARO rojas") == "alvaro rojas"
    assert normalize_player_name("Éric Mélo") == "eric melo"
    assert normalize_player_name("") == ""
    assert normalize_player_name("Johan Loza") == "johan loza"
