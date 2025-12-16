import json
import time
import math
import tkinter as tk

"""
Clash Royale Arena Simulator
A simplified simulation of Clash Royale battles with visuals.
Supports troops, towers, and spells.
"""

# Load card data from JSON file
try:
   with open('clash_royale_cards.json', 'r') as f:
       data = json.load(f)
   card_data = data['CARDDATA']
   card_names = data['METADATA']['card_names']
except FileNotFoundError:
   print("Error: clash_royale_cards.json not found")
   root = tk.Tk()
   root.withdraw()
   tk.messagebox.showerror("Error", "Required JSON file not found!")
   exit()

# Arena configuration constants
ARENA_WIDTH, ARENA_HEIGHT, CELL_SIZE = 18, 32, 20

# Spawn positions for both teams
# Blue team spawns in bottom half (y > 16), Red team in top half (y < 16)
# Coordinates are in tile units (3.5 = center of tile 3)
POSITIONS = {
   'blue': {
       'bl': (3.5, 17),  'br': (14.5, 17),   # Bridge positions
       'fl': (6, 26),  'fr': (11, 26),       # Far back (near king tower)
       'ml': (8, 20),  'mr': (9, 20),        # Middle field
       'sl': (0, 24),  'sr': (17, 24),       # Sides (near edges)
       'tl': (3, 25),  'tr': (14, 25),       # Near towers
       'pl': (8, 22),  'pr': (9, 22),        # Pocket (behind princess towers)
       'ol': (3, 21),  'or': (14, 21),       # Offense (in front of princess towers)
       'kl': (8, 26),  'kr': (9, 26),        # King tower area
       'rl': (3, 23),  'rr': (14, 23)        # Princess tower area
   },
   'red': {
       'bl': (3.5, 14),  'br': (14.5, 14),   # Bridge positions (mirrored)
       'fl': (6, 5),   'fr': (11, 5),        # Far back
       'ml': (8, 11),  'mr': (9, 11),        # Middle field
       'sl': (0, 7),   'sr': (17, 7),        # Sides
       'tl': (3, 6),   'tr': (14, 6),        # Near towers
       'pl': (8, 9),   'pr': (9, 9),         # Pocket
       'ol': (3, 10),  'or': (14, 10),       # Offense
       'kl': (8, 5),   'kr': (9, 5),         # King tower area
       'rl': (3, 8),   'rr': (14, 8)         # Princess tower area
   }
}

# Multi-unit spawn counts for swarm troops
TROOP_COUNTS = {'arc': 2, 'mns': 3, 'gob': 3, 'spe': 3}


class Unit:
   """
   Represents a troop unit on the battlefield.
   Handles movement, combat, and targeting logic.
   """
   def __init__(self, key, x, y, team):
       self.key = key  # Card identifier (e.g., 'kni', 'arc')
       self.x, self.y = float(x), float(y)  # Position in tile coordinates
       self.team = team  # 'blue' or 'red'
       
       # Load stats from card data
       c = card_data[key]
       self.health = self.max_health = c['health']
       self.speed = c['speed'] / 3600  # Convert tiles/min to tiles/frame (60fps)
       self.damage = c['damage']
       self.hitspeed = c['hitspeed']  # Seconds between attacks
       self.attack_radius = c['attackradius']
       self.attack_cooldown = c['firsthit'] * 60  # Initial attack delay in frames
       self.flying = c['flying']
       self.targets = c['targets']  # ground, troops, or buildings
       self.waypoint = None  # Used for bridge pathing
  
   def move(self, target_x, target_y):
       """Move unit toward target position at its movement speed."""
       dx, dy = target_x - self.x, target_y - self.y
       dist = math.sqrt(dx*dx + dy*dy)
       if dist > 0:
           # Apply speed
           self.x += (dx / dist) * self.speed
           self.y += (dy / dist) * self.speed
   
   def distance_to(self, x, y):
       """Calculate Euclidean distance to a point."""
       return math.sqrt((self.x - x)**2 + (self.y - y)**2)


class Spell:
   """
   Represents a spell being cast on the battlefield.
   Spells have a delay before dealing area damage.
   """
   def __init__(self, key, x, y, team):
       self.key = key
       self.x, self.y = float(x), float(y)
       self.team = team
       
       c = card_data[key]
       self.damage = c['damage']
       self.radius = c['attackradius']  # Area of effect radius
       
       # Set delay based on spell type (in frames at 60fps)
       self.delay = 60 if key == 'arr' else 90  # Arrows = 1s, Fireball = 1.5s
       self.active = True
   
   def update(self):
       """
       Count down delay timer.
       Returns True when spell is ready to deal damage.
       """
       self.delay -= 1
       if self.delay <= 0:
           self.active = False
           return True  # Spell has landed
       return False


class Tower:
   """
   Represents a defensive tower (Princess or King tower).
   Towers automatically attack enemy units in range.
   """
   def __init__(self, x, y, hp, dmg, size):
       self.x, self.y = x, y
       self.health = self.max_health = hp
       self.damage = dmg
       self.size = size  # 3 for princess, 4 for king (in tiles)
       
       # Load tower combat stats from JSON (uses princess tower data)
       tower_data = card_data['pri']
       self.attack_radius = tower_data['attackradius']
       self.hitspeed = tower_data['hitspeed']
       self.attack_cooldown = 0


class Arena:
   """
   Main game state manager.
   Handles units, spells, towers, and combat logic.
   """
   def __init__(self):
       self.units = []
       self.spells = []
       
       # Initialize towers for both teams
       # Princess towers (3x3) guard the lanes, King tower (4x4) is in back
       self.towers = {
           'blue': {
               'left': Tower(3.5, 24.5, 3052, 109, 3),
               'right': Tower(14.5, 24.5, 3052, 109, 3),
               'king': Tower(9, 29, 5000, 122, 4)
           },
           'red': {
               'left': Tower(3.5, 7.5, 3052, 109, 3),
               'right': Tower(14.5, 7.5, 3052, 109, 3),
               'king': Tower(9, 3, 5000, 122, 4)
           }
       }
       self.running = False
  
   def add_unit(self, key, pos, team):
       """
       Spawn a unit or cast a spell at the specified position.
       Handles both single units and multi-unit spawns (swarms).
       """
       if key not in card_data or team not in POSITIONS or pos not in POSITIONS[team]:
           print(f"Error: Invalid card '{key}', position '{pos}', or team '{team}'")
           return False
       
       x, y = POSITIONS[team][pos]
       
       # Check if card is a spell
       if card_data[key]['spell']:
           self.spells.append(Spell(key, x, y, team))
           print(f"Cast {card_names[key]} ({team}) at {pos}")
           return True
       
       # Determine number of units to spawn
       count = TROOP_COUNTS.get(key, 1)
       
       # Spawn units in formation
       if count == 1:
           self.units.append(Unit(key, x, y, team))
       elif count == 2:
           # Two units side by side (Archers)
           offsets = [(-0.5, 0), (0.5, 0)]
           for dx, dy in offsets:
               self.units.append(Unit(key, x + dx, y + dy, team))
       else:  # 3 units
           # Triangle formation (Goblins, Minions, Spear Goblins)
           offsets = [(0, 0), (-0.5, 0.5), (0.5, 0.5)]
           for dx, dy in offsets:
               self.units.append(Unit(key, x + dx, y + dy, team))
       
       count_text = f"{count}x " if count > 1 else ""
       print(f"Added {count_text}{card_names[key]} ({team}) at {pos}")
       return True
   
   def find_target(self, unit):
       """
       Determine the best target for a unit based on proximity and targeting rules.
       Returns the nearest valid target (unit or tower) or None.
       """
       enemy_team = 'red' if unit.team == 'blue' else 'blue'
       nearest = None
       min_dist = float('inf')
       
       # Get unit's sight range from card data
       sight_range = card_data[unit.key]['sightrange']
       
       # Check enemy units first (unless this unit only targets buildings)
       if unit.targets != "buildings":
           for other in self.units:
               if other.team != unit.team and other.health > 0:
                   # Ground units cannot target flying units
                   if not unit.flying and other.flying:
                       continue
                   dist = unit.distance_to(other.x, other.y)
                   # Only target units within sight range
                   if dist < min_dist and dist <= sight_range:
                       min_dist = dist
                       nearest = other
       
       # Check enemy towers (all units can see and target towers)
       for tower in self.towers[enemy_team].values():
           if tower.health > 0:
               dist = unit.distance_to(tower.x, tower.y)
               if dist < min_dist:
                   min_dist = dist
                   nearest = tower
       
       return nearest
  
   def update(self):
       """
       Main game loop update function.
       Handles spells, unit movement/combat, and tower attacks.
       """
       # Process active spells
       for spell in self.spells[:]:
           if spell.update():  # Check if spell delay has finished
               enemy_team = 'red' if spell.team == 'blue' else 'blue'
               # Deal area damage to all enemy units in radius
               for unit in self.units:
                   if unit.team == enemy_team:
                       dist = math.sqrt((spell.x - unit.x)**2 + (spell.y - unit.y)**2)
                       if dist <= spell.radius:
                           unit.health -= spell.damage
               self.spells.remove(spell)
       
       # Update all units
       for u in self.units:
           if u.health <= 0:
               continue
           
           target = self.find_target(u)
           if not target:
               continue
           
           dist = u.distance_to(target.x, target.y)
           
           # Calculate stopping distance based on target type
           if hasattr(target, 'size'):  # Targeting a tower
               stop_distance = target.size / 2 + 0.5
           else:  # Targeting another unit
               stop_distance = 0.5
           
           # Attack if within attack range
           if dist <= u.attack_radius + stop_distance:
               if u.attack_cooldown <= 0:
                   target.health -= u.damage
                   u.attack_cooldown = u.hitspeed * 60  # Convert seconds to frames
           elif dist > stop_distance:
               # Implement waypoint pathing for ground units targeting towers
               # This creates lane-based movement through bridges
               if not u.flying and hasattr(target, 'size'):
                   bridge_y = 16 if u.team == 'blue' else 15
                   
                   # Check if unit needs to path through bridge
                   if u.team == 'blue' and u.y > bridge_y + 1:
                       # Unit is on blue side, needs to reach bridge
                       if not u.waypoint or u.distance_to(u.waypoint[0], u.waypoint[1]) < 0.5:
                           u.waypoint = (target.x, bridge_y)
                       u.move(u.waypoint[0], u.waypoint[1])
                   elif u.team == 'red' and u.y < bridge_y - 1:
                       # Unit is on red side, needs to reach bridge
                       if not u.waypoint or u.distance_to(u.waypoint[0], u.waypoint[1]) < 0.5:
                           u.waypoint = (target.x, bridge_y)
                       u.move(u.waypoint[0], u.waypoint[1])
                   else:
                       # Unit has crossed bridge, move directly to tower
                       u.waypoint = None
                       u.move(target.x, target.y)
               else:
                   # Flying units or units attacking other units use direct pathing
                   u.move(target.x, target.y)
           
           # Decrease attack cooldown
           if u.attack_cooldown > 0:
               u.attack_cooldown -= 1
       
       # Tower attack logic
       for team in ['blue', 'red']:
           enemy_team = 'red' if team == 'blue' else 'blue'
           for tower in self.towers[team].values():
               if tower.health <= 0:
                   continue
               
               # Find nearest enemy unit within attack range
               nearest_enemy = None
               min_dist = float('inf')
               
               for unit in self.units:
                   if unit.team == enemy_team and unit.health > 0:
                       dist = math.sqrt((tower.x - unit.x)**2 + (tower.y - unit.y)**2)
                       if dist <= tower.attack_radius and dist < min_dist:
                           min_dist = dist
                           nearest_enemy = unit
               
               # Tower attacks nearest enemy
               if nearest_enemy:
                   if tower.attack_cooldown <= 0:
                       nearest_enemy.health -= tower.damage
                       tower.attack_cooldown = tower.hitspeed * 60
               
               if tower.attack_cooldown > 0:
                   tower.attack_cooldown -= 1
       
       # Remove dead units from the battlefield
       self.units = [u for u in self.units if u.health > 0]


class GUI:
   """
   Graphical user interface for the arena.
   Handles rendering and user input with tkinter.
   """
   def __init__(self, arena):
       self.arena = arena
       self.root = tk.Tk()
       self.root.title("Arena")
      
       # Main canvas for arena visualization
       self.canvas = tk.Canvas(self.root,
                               width=ARENA_WIDTH*CELL_SIZE,
                               height=ARENA_HEIGHT*CELL_SIZE,
                               bg='#2a2a2a')
       self.canvas.pack(side=tk.TOP)
      
       # Command input frame at bottom
       control_frame = tk.Frame(self.root)
       control_frame.pack(side=tk.BOTTOM, fill=tk.X)

       # Text input field for commands
       self.input_entry = tk.Entry(control_frame, width=50)
       self.input_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
       self.input_entry.bind('<Return>', self.process_command)
      
       # Execute button
       submit_btn = tk.Button(control_frame,
                              text="Execute",
                              command=self.execute_button_wrapper)
       submit_btn.pack(side=tk.LEFT, padx=5, pady=5)
      
       print("Type commands (add <card> <pos> <team>, start, or quit) into the box in the window.")
      
       self.loop()  # Start draw loop

   def execute_button_wrapper(self):
       """Helper to process command from button click."""
       self.process_command(None)

   def process_command(self, event):
       """
       Parse and execute user commands from the input field.
       Supported commands: add, start, quit
       """
       cmd_text = self.input_entry.get().strip().lower()
       self.input_entry.delete(0, tk.END)
      
       if not cmd_text:
           return

       cmd = cmd_text.split()
      
       if cmd[0] == 'quit':
           self.root.quit()
       elif cmd[0] == 'add' and len(cmd) == 4:
           self.arena.add_unit(cmd[1], cmd[2], cmd[3])
       elif cmd[0] == 'start':
           self.arena.running = True
           print("START GAME")
       else:
           print(f"GUI: Unknown command or invalid format: {cmd_text}")
  
   def draw(self):
       """
       Render the entire arena state.
       Called every frame to update the screen.
       """
       self.canvas.delete('all')
      
       # Draw grid lines
       for i in range(ARENA_WIDTH+1):
           self.canvas.create_line(i*CELL_SIZE, 0, i*CELL_SIZE, ARENA_HEIGHT*CELL_SIZE, fill='#444')
       for i in range(ARENA_HEIGHT+1):
           self.canvas.create_line(0, i*CELL_SIZE, ARENA_WIDTH*CELL_SIZE, i*CELL_SIZE, fill='#444')
      
       # Draw river (2 tiles tall at y=15-16)
       self.canvas.create_rectangle(0, 15*CELL_SIZE, ARENA_WIDTH*CELL_SIZE, 17*CELL_SIZE, fill='#1e90ff')
       
       # Draw bridges (3 tiles wide each)
       self.canvas.create_rectangle(2*CELL_SIZE, 15*CELL_SIZE, 5*CELL_SIZE, 17*CELL_SIZE, fill='#8B4513')
       self.canvas.create_rectangle(13*CELL_SIZE, 15*CELL_SIZE, 16*CELL_SIZE, 17*CELL_SIZE, fill='#8B4513')
      
       # Draw active spells with countdown indicators
       for spell in self.arena.spells:
           x, y = spell.x*CELL_SIZE, spell.y*CELL_SIZE
           radius = spell.radius * CELL_SIZE / 2  # Visual radius (attackradius appears to be diameter)
           
           color = '#4169e1' if spell.team == 'blue' else '#dc143c'
           # Dashed circle showing area of effect
           self.canvas.create_oval(x-radius, y-radius, x+radius, y+radius, outline=color, width=2, dash=(5,5))
           # Center marker
           self.canvas.create_oval(x-5, y-5, x+5, y+5, fill=color, outline='white')
           # Countdown timer
           remaining = spell.delay / 60
           self.canvas.create_text(x, y-radius-10, text=f"{remaining:.1f}s", font=('Arial', 10, 'bold'), fill=color)
      
       # Draw towers
       for team, towers in self.arena.towers.items():
           for t in towers.values():
               if t.health <= 0:
                   continue
               
               sz = t.size * CELL_SIZE
               # Convert tower center position to top-left corner for drawing
               center_x = t.x * CELL_SIZE
               center_y = t.y * CELL_SIZE
               x = center_x - sz // 2
               y = center_y - sz // 2
               
               color = '#4169e1' if team == 'blue' else '#dc143c'
               self.canvas.create_rectangle(x, y, x + sz, y + sz, fill = color, outline = 'white', width = 2)
               
               # Tower health bar
               hp = t.health / t.max_health
               self.canvas.create_rectangle(x+5, y+sz+3, x+5+hp*(sz-10), y+sz+7, fill='#00ff00' if hp >0.5 else '#ff0000')
      
       # Draw units
       for u in self.arena.units:
           x, y = u.x*CELL_SIZE, u.y*CELL_SIZE
           color = '#4169e1' if u.team == 'blue' else '#dc143c'
           # Unit circle
           self.canvas.create_oval(x-8, y-8, x+8, y+8, fill=color, outline='white')
           
           # Unit identifier (3-letter code)
           self.canvas.create_text(x, y, text=u.key.upper(), font=('Arial', 8, 'bold'), fill='white')
           
           # Unit health bar
           hp = u.health / u.max_health
           self.canvas.create_rectangle(x-10, y-15, x-10+20*hp, y-12, fill='#00ff00' if hp > 0.5 else '#ff0000')
  
   def loop_wrapper(self):
       """Loop scheduler for consistent frame updates. Most of the methods below are from TKinter website and slightly modified"""
       self.loop()
       self.root.after(16, self.loop_wrapper)

   def loop(self):
       """Runs game logic and redraws"""
       if self.arena.running:
           self.arena.update()
       self.draw()
  
   def start(self):
       """Initialize the main loop"""
       self.root.after(16, self.loop_wrapper)
       self.root.mainloop()


def main():
   """Entry point for the application."""
   arena = Arena()
   gui = GUI(arena)
   gui.start()


if __name__ == "__main__":
   main()