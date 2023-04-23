import main

tests = [
    ["16:9", 3, "Win"],
    ["9:3", 7, "Lose"],
    ["15:15", 1, "Draw"],
    ["8:8", 5, "Draw"],
    ["16:9", 2, "Win"],
    ["4:16", 0, "Lose"],
    ["10:10", 8, "Surrender"],
    ["15:12", 2, "Surrender"],
    ["2:16", 1, "Lose"],
    ["16:3", 7, "Lose"],
    ["0:15", 6, "Surrender"],
    ["7:20", 9, "Surrender"],
    ["0:16", 2, "Lose"],
    ["16:0", 3, "Win"],
    ["11:16", 8, "Win"],
    ["16:13", 4, "Win"],
    ["16:13", 5, "Lose"],
    ["3:5", 6, "Surrender"],
    ["8:8", 4, "Draw"],
    ["16:12", 1, "Win"],
    ["10:16", 7, "Win"],
    ["16:6", 8, "Lose"],
    ["14:16", 2, "Lose"],
    ["16:4", 6, "Lose"],
    ["3:9", 8, "Win"],
    ["9:3", 3, "Win"],
    ["8:8", 9, "Draw"],
    ["16:9", 7, "Lose"],
    ["9:16", 7, "Win"],
    ["7:16", 0, "Lose"]
]

err = 0
for test in tests:
    outcome = main.check_winning(match_score=test[0], player_index=test[1])
    if outcome != test[2]:
        print(f"Failure on {test} -> {outcome}")
        err += 1

if err > 0:
    print(f"{err} tests failed!")
else:
    print("No tests failed!")
