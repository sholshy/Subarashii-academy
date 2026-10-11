import sys

with open('tournament_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

target1 = """        late_loss.result_text = "LATE_LOSS"
        late_loss.note = "Perdida administrativa por ingreso atrasado."
        self.rounds[-1].append(late_loss)"""

replacement1 = """        late_loss.result_text = "LATE_LOSS"
        late_loss.note = "Perdida administrativa por ingreso atrasado."
        new_player.had_bye = True
        self.rounds[-1].append(late_loss)"""

content = content.replace(target1, replacement1)

target2 = """        elif result_type == "LATE_LOSS":
            if match.p2:
                if match.p2.match_results: match.p2.match_results.pop()"""

replacement2 = """        elif result_type == "LATE_LOSS":
            if match.p2:
                match.p2.had_bye = False
                if match.p2.match_results: match.p2.match_results.pop()"""

content = content.replace(target2, replacement2)

with open('tournament_manager.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied for late_bye")
