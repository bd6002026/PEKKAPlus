import json
import math

try:
    with open('clash_royale_cards.json', 'r') as f:
        card_full_data = json.load(f)
    # card data dictionary
    card_data = card_full_data['CARDDATA']
except FileNotFoundError:
    # just in case json import does not work
    print("Error: 'clash_royale_cards.json' not found")
    exit()

rightpocket = False
leftpocket = False
currentinput = 'null'
# Position codes mapped to spreadsheet cells (18 wide x 32 tall, A-R cols, 1-32 rows, 2 for bridge)
POSITIONS = {
    'bl': 'D15',  'br': 'O15',   # Bridge
    'fl': 'G2', 'fr': 'L2',      # Far back
    'ml': 'I9',  'mr': 'J9',     # Middle
    'sl': 'A10',  'sr': 'R10',   # Sides
    'tl': 'D11',  'tr': 'O11',   # Towers
    'pl': 'I22',  'pr': 'J22',   # Pocket
    'ol': 'D21',  'or': 'O21',   # Offense (in front of your princess tower)
    'kl': 'I26', 'kr': 'J26',    # King tower
    'rl': 'D23', 'rr': 'O23'     # P*r*incess tower
}

def cell_to_coords(cell):
    """D2 -> (3, 1)"""
    return (ord(cell[0].upper()) - ord('A'), int(cell[1:]) - 1)

# Convert positions to coords
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
    # Calculate distance with Pythagorean Theorem
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

def get_arena_coordinates_v2():
    global leftpocket, rightpocket, currentinput
    card = input("Enter card or event (rtd/ltd): ").lower()
    
    if card == 'rtd':
        rightpocket = True
        return "Right tower down"
    elif card == 'ltd':
        leftpocket = True
        return "Left tower down"
    
    loc = input("Enter location (bl, br, fl, fr, ml, mr, sl, sr, tl, tr): ").lower()
    currentinput = loc # Setting currentinput to the location code for pathing logic
    
    if loc not in POSITIONS:
        return f"Unknown location: {loc}"
    if loc == 'pl' and not leftpocket:
        return "Left pocket locked"
    if loc == 'pr' and not rightpocket:
        return "Right pocket locked"
    
    return {'card': card, 'position': POSITIONS[loc], 'loc_code': loc}

def timeToDestination(card, start, end):
    # Get speed and flying status using key names
    try:
        is_flying = card_data[card]['flying']
        speed = card_data[card]['speed']
        
        # Handle non-numeric speed for spells/buildings
        if not isinstance(speed, (int, float)):
            return "N/A" # No spells/buildings
            
    except KeyError:
        # Card not found in json
        print(f"Error: '{card}' data not found.")
        return float('inf')
        
    total_distance = 0.0

    (x1,y1) = end
    
    if not is_flying:
        # Ground unit logic using the global currentinput (the location code)
        if(currentinput == 'fl'):
            if(x1 > 17):
                waypoint = cell_to_coords('G8')
                total_distance = distance(start, waypoint) + distance(waypoint, cell_to_coords('D15')) + distance(cell_to_coords('D15'), end)
            else:
                waypoint = cell_to_coords('G8')
                total_distance = distance(start, waypoint) + distance(waypoint, end)
        elif(currentinput == 'fr'):
            if(x1 > 17):
                waypoint = 'L8'
                total_distance = distance(start, waypoint) + distance(waypoint, cell_to_coords('O15')) + distance(cell_to_coords('O15'), end)
            else:
                waypoint = cell_to_coords('L8')
                total_distance = distance(start, waypoint) + distance(waypoint, end)
        else:
            total_distance = distance(start,end)
            
    else:
        # Flying units take the direct path
        total_distance = distance(start, end)
    
    # Calculate time: Time = Distance / Speed
    if speed > 0:
        time = total_distance / speed
    else:
        time = float('inf')
        
    return time * 60


currentinput = 'pl' 
card_key = 'mpk'
start_loc_code = 'pl'
end_loc_code = 'rr'

start_coords = COORDS[start_loc_code]  # Middle Left (I5 -> (8, 4))
end_coords = COORDS[end_loc_code]      # Bridge Left (D2 -> (3, 1))

travel_time = timeToDestination(card_key, start_coords, end_coords)
speed = card_data[card_key]['speed'] # 90
expected_distance = distance(start_coords, end_coords) 

print(f"TEST CASE: {card_key.upper()} from {start_loc_code.upper()} to {end_loc_code.upper()}")
print(f"  Card: {card_key.upper()} | Type: Ground | Speed: {speed} tiles/min")
print(f"  Start Coords ({start_loc_code.upper()}): {start_coords}")
print(f"  End Coords ({end_loc_code.upper()}): {end_coords}")


print(f"  Calculated Distance: {expected_distance:.3f} tiles")

print(f"   Time: {travel_time:.3f} seconds")

# print(get_arena_coordinates_v2())
# print(get_arena_coordinates_v2())
# print(get_arena_coordinates_v2())