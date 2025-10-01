import json
import math

with open('clash_royale_cards.json', 'r') as f:
    card_data = json.load(f)

rightpocket = False
leftpocket = False

# Position codes mapped to spreadsheet cells (18 wide x 15 tall, A-R cols, 1-15 rows)
POSITIONS = {
    'bl': 'D2',  'br': 'O2',   # Bridge
    'fl': 'G14', 'fr': 'L14',  # Far back
    'ml': 'I5',  'mr': 'J5',   # Middle
    'sl': 'A6',  'sr': 'R6',   # Sides
    'tl': 'D5',  'tr': 'O5',   # Behind towers
    'pl': 'I5',  'pr': 'J5'    # Pocket
}

def cell_to_coords(cell):
    """D2 -> (3, 1)"""
    return (ord(cell[0].upper()) - ord('A'), int(cell[1:]) - 1)

# Convert positions to numeric coords
COORDS = {}
for k, v in POSITIONS.items():
    COORDS[k] = cell_to_coords(v)
BRIDGE_L = cell_to_coords('D2')
BRIDGE_R = cell_to_coords('O2')

# Tower hitboxes
TOWERS = {
    'princess_l': {'center': cell_to_coords('D8'), 'size': 3},
    'princess_r': {'center': cell_to_coords('O8'), 'size': 3},
    'king': {'left': 7, 'right': 10, 'top': 9, 'bottom': 12}  # H10-K13
}

def distance(p1, p2):
    # Calculate distance
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

def get_arena_coordinates_v2():
    global leftpocket, rightpocket
    
    card = input("Enter card or event (rtd/ltd): ").lower()
    if card == 'rtd':
        rightpocket = True
        return "Right tower down"
    elif card == 'ltd':
        leftpocket = True
        return "Left tower down"
    
    loc = input("Enter location (bl, br, fl, fr, ml, mr, sl, sr, tl, tr): ").lower()
    
    if loc not in POSITIONS:
        return f"Unknown location: {loc}"
    if loc == 'pl' and not leftpocket:
        return "Left pocket locked"
    if loc == 'pr' and not rightpocket:
        return "Right pocket locked"
    
    result = f"Card: {card}, Position: {POSITIONS[loc]}"
    
    return result

print(get_arena_coordinates_v2())
print(get_arena_coordinates_v2())
print(get_arena_coordinates_v2())