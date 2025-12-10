import json
import time
import math
import threading
import tkinter as tk

try:
    with open('clash_royale_cards.json', 'r') as f:
        data = json.load(f)
    card_data = data['CARDDATA']
    card_names = data['METADATA']['card_names']
except FileNotFoundError:
    print("Error: json not found")
    exit()

ARENA_WIDTH, ARENA_HEIGHT, CELL_SIZE = 18, 32, 20

# TODO: Fix all positions because they are bound to 
# be incorrect once we add princess and king towers.
POSITIONS = {
    'blue': {
        'bl': (3, 17),  'br': (14, 17),   # Bridge
        'fl': (6, 26),  'fr': (11, 26),   # Far back
        'ml': (8, 20),  'mr': (9, 20),    # Middle
        'sl': (0, 24),  'sr': (17, 24),   # Sides
        'tl': (3, 25),  'tr': (14, 25),   # Near towers
        'pl': (8, 22),  'pr': (9, 22),    # Pocket
        'ol': (3, 21),  'or': (14, 21),   # Offense
        'kl': (8, 26),  'kr': (9, 26),    # King tower 
        'rl': (3, 23),  'rr': (14, 23)    # Princess tower 
    },
    'red': {
        'bl': (3, 14),  'br': (14, 14),   # Bridge
        'fl': (6, 5),   'fr': (11, 5),    # Far back
        'ml': (8, 11),  'mr': (9, 11),    # Middle
        'sl': (0, 7),   'sr': (17, 7),    # Sides
        'tl': (3, 6),   'tr': (14, 6),    # Near towers
        'pl': (8, 9),   'pr': (9, 9),     # Pocket
        'ol': (3, 10),  'or': (14, 10),   # Offense
        'kl': (8, 5),   'kr': (9, 5),     # King tower 
        'rl': (3, 8),   'rr': (14, 8)     # Princess tower 
    }
}

class Unit:
    def __init__(self, key, x, y, team):
        """
        Initializes variables we'll likely use in the future
        """
        self.key, self.x, self.y, self.team = key, float(x), float(y), team
        c = card_data[key]
        self.health = self.max_health = c['health']
        self.speed = c['speed'] / 3600
    
    def move(self, target_x, target_y):
        dx, dy = target_x - self.x, target_y - self.y
        dist = math.sqrt(dx*dx + dy*dy)
        if dist > 0:
            self.x += (dx / dist) * self.speed
            self.y += (dy / dist) * self.speed

class Arena:
    def __init__(self):
        self.units = []
        self.running = False
    
    def add_unit(self, key, pos, team):
        if key not in card_data or team not in POSITIONS or pos not in POSITIONS[team]:
            return False
        x, y = POSITIONS[team][pos]
        self.units.append(Unit(key, x, y, team))
        print(f"Added {card_names[key]} ({team}) at {pos}")
        return True
    
    def update(self):
        """ Movement toward princess towers """
        for u in self.units:
            target_y = ARENA_HEIGHT // 2 # TODO: create all towers and change the
                                         # cards to target each other and buildings 
            u.move(u.x, target_y)

class GUI:
    def __init__(self, arena):
        self.arena = arena
        self.root = tk.Tk()
        self.root.title("Arena")
        self.canvas = tk.Canvas(self.root, width=ARENA_WIDTH*CELL_SIZE, height=ARENA_HEIGHT*CELL_SIZE, bg='#2a2a2a')
        self.canvas.pack()
        self.loop()
    
    def draw(self):
        self.canvas.delete('all')
        
        # Grid
        for i in range(ARENA_WIDTH+1):
            self.canvas.create_line(i*CELL_SIZE, 0, i*CELL_SIZE, ARENA_HEIGHT*CELL_SIZE, fill='#444')
        for i in range(ARENA_HEIGHT+1):
            self.canvas.create_line(0, i*CELL_SIZE, ARENA_WIDTH*CELL_SIZE, i*CELL_SIZE, fill='#444')
        
        # Bridge placeholder
        # TODO: Add bridge itself (3x2 grid) and the center only flying troops can go over
        self.canvas.create_line(0, ARENA_HEIGHT*CELL_SIZE//2, ARENA_WIDTH*CELL_SIZE, ARENA_HEIGHT*CELL_SIZE//2, fill='#1e90ff', width=3)
        
        # Units
        for u in self.arena.units:
            x, y = u.x*CELL_SIZE, u.y*CELL_SIZE
            color = '#4169e1' if u.team == 'blue' else '#dc143c'
            self.canvas.create_oval(x-8, y-8, x+8, y+8, fill=color, outline='white')
    
    # --- Fancy TKinter stuff below we don't quite understand (yet) ---
    def loop(self):
        if self.arena.running:
            self.arena.update()
        self.draw()
        self.root.after(16, self.loop)
    
    def start(self):
        self.root.mainloop()

def main():
    arena = Arena()
    
    def start_gui():
        gui = GUI(arena)
        gui.start()
    
    threading.Thread(target=start_gui, daemon=True).start()
    
    # TODO: Add elixir counting w/ time and a way
    # to see how much has leaked for both sides.
    time.sleep(0.5)
    
    print("P.E.K.K.A Plus Arena")
    print("Commands:")
    print("  add <card> <pos> <team>  - Add unit (e.g. add kni bl blue)")
    print("  start - Start simulation")
    print("  quit - Exit\n")
    
    while True:
        cmd = input("> ").strip().lower().split()
        if not cmd: continue
        if cmd[0] == 'quit': break
        elif cmd[0] == 'add' and len(cmd) == 4:
            arena.add_unit(cmd[1], cmd[2], cmd[3])
        elif cmd[0] == 'start':
            arena.running = True
            print("START GAME")

if __name__ == "__main__":
    main()