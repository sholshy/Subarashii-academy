import traceback
from tournament_manager import TournamentManager, Player, Match

def test_add_player():
    tm = TournamentManager()
    tm.add_player("Alice", "123")
    tm.add_player("Bob", "456")
    assert len(tm.players) == 2

def test_start_tournament():
    tm = TournamentManager()
    for i in range(8):
        tm.add_player(f"Player{i}", f"id{i}")
    tm.start_tournament(mode="swiss")
    assert tm.total_rounds == 3
    assert len(tm.get_current_matches()) == 4

def test_report_match():
    tm = TournamentManager()
    tm.add_player("Alice", "123")
    tm.add_player("Bob", "456")
    tm.start_tournament(mode="swiss", total_rounds_override=1)
    match = tm.get_current_matches()[0]
    match.report("P1_WIN")
    assert match.reported
    assert match.p1.points == 3
    assert match.p2.points == 0

def test_standings():
    tm = TournamentManager()
    for p in ["A", "B", "C", "D"]:
        tm.add_player(p, p)
    tm.start_tournament(mode="swiss", total_rounds_override=2)
    m1, m2 = tm.get_current_matches()
    m1.report("P1_WIN")
    m2.report("P1_WIN")
    standings = tm.get_standings()
    assert standings[0].points == 3
    assert standings[1].points == 3

def test_drop_player():
    tm = TournamentManager()
    tm.add_player("Alice", "1")
    tm.add_player("Bob", "2")
    tm.start_tournament(mode="swiss", total_rounds_override=2)
    tm.drop_player("Bob")
    match = tm.get_current_matches()[0]
    assert match.reported
    assert match.p1.points == 3 or match.p2.points == 3

def test_late_player():
    tm = TournamentManager()
    for p in ["A", "B", "C", "D"]: tm.add_player(p, p)
    tm.start_tournament(mode="swiss", total_rounds_override=2)
    
    player, status, match = tm.add_late_player("Late1", "L1", penalty=True)
    assert status == "ROUND_LOSS"
    assert match.result_text == "LATE_LOSS"

def test_two_late_players():
    tm = TournamentManager()
    for p in ["A", "B", "C", "D"]: tm.add_player(p, p)
    tm.start_tournament(mode="swiss", total_rounds_override=2)
    
    # First late player
    p1, s1, m1 = tm.add_late_player("Late1", "L1", penalty=True)
    assert s1 == "ROUND_LOSS"
    
    # Second late player - should pair with the first one
    p2, s2, m2 = tm.add_late_player("Late2", "L2", penalty=True)
    assert s2 == "PAIRED_WITH_LATE"
    assert m2.p1.name == "Late1" or m2.p2.name == "Late1"
    assert m2.p1.name == "Late2" or m2.p2.name == "Late2"
    assert m2.result_text == "Pendiente"
    assert m2.reported == False

def test_multiple_drops():
    tm = TournamentManager()
    for p in ["A", "B", "C", "D", "E", "F"]: tm.add_player(p, p)
    tm.start_tournament(mode="swiss", total_rounds_override=3)
    
    tm.drop_player("A")
    tm.drop_player("B")
    
    active_players = [p for p in tm.players if p.active]
    assert len(active_players) == 4
    
    # Next round should only pair the 4 active players
    for m in tm.get_current_matches():
        if not m.reported:
            m.report("DRAW")
            
    tm.generate_next_round()
    assert len(tm.get_current_matches()) == 2

def test_undo_and_rollback():
    tm = TournamentManager()
    for p in ["A", "B"]: tm.add_player(p, p)
    tm.start_tournament(mode="swiss", total_rounds_override=2)
    
    match = tm.get_current_matches()[0]
    match.report("P1_WIN")
    assert match.p1.points == 3
    
    tm.undo_match(match)
    assert not match.reported
    assert match.p1.points == 0
    
    tm.generate_next_round()
    assert tm.current_round == 2
    
    tm.rollback_round()
    assert tm.current_round == 1

if __name__ == "__main__":
    tests = [
        test_add_player, test_start_tournament, test_report_match, 
        test_standings, test_drop_player, test_late_player,
        test_two_late_players, test_multiple_drops, test_undo_and_rollback
    ]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"PASSED: {test.__name__}")
        except AssertionError:
            print(f"FAILED: {test.__name__}")
            traceback.print_exc()
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__} - {e}")
            traceback.print_exc()
            failed += 1
    
    if failed == 0:
        print("\nAll tests passed successfully!")
    else:
        print(f"\n{failed} tests failed.")

