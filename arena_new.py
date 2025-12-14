import json
import time
import math
import tkinter as tk


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


ARENA_WIDTH, ARENA_HEIGHT, CELL_SIZE = 18, 32, 20


POSITIONS = {
   'blue': {
       'bl': (3.5, 17),  'br': (14.5, 17),   # Bridge
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


class Tower:
   def __init__(self, x, y, hp, dmg, size):
       self.x, self.y = x, y
       self.health = self.max_health = hp
       self.damage = dmg
       self.size = size  # 3 for princess, 4 for king


class Arena:
   def __init__(self):
       self.units = []
       self.towers = {
           'blue': {
               'left': Tower(3, 24, 3052, 109, 3),
               'right': Tower(14, 24, 3052, 109, 3),
               'king': Tower(9, 29, 5000, 122, 4)
           },
           'red': {
               'left': Tower(3, 7, 3052, 109, 3),
               'right': Tower(14, 7, 3052, 109, 3),
               'king': Tower(9, 3, 5000, 122, 4)
           }
       }
       self.running = False
  
   def add_unit(self, key, pos, team):
       if key not in card_data or team not in POSITIONS or pos not in POSITIONS[team]:
           print(f"Error: Invalid card '{key}', position '{pos}', or team '{team}'")
           return False
       x, y = POSITIONS[team][pos]
       self.units.append(Unit(key, x, y, team))
       print(f"Added {card_names[key]} ({team}) at {pos}")
       return True
  
   def update(self):
       """ Movement toward enemy towers """
       for u in self.units:
           enemy_team = 'red' if u.team == 'blue' else 'blue'
           # Find nearest enemy tower
           nearest_tower = None
           min_dist = float('inf')
           for tower in self.towers[enemy_team].values():
               if tower.health > 0:
                   dist = math.sqrt((u.x - tower.x)**2 + (u.y - tower.y)**2)
                   if dist < min_dist:
                       min_dist = dist
                       nearest_tower = tower
           
           if nearest_tower:
               # Calculate distance to tower
               dist = math.sqrt((u.x - nearest_tower.x)**2 + (u.y - nearest_tower.y)**2)
               # Stop at tower edge (tower size/2)
               stop_distance = nearest_tower.size / 2 + 1
               
               if dist > stop_distance:
                   # Determine if unit should path through bridge center
                   bridge_y = 16  # Middle of bridge (y=15-16)
                   
                   # If unit is far from tower (hasn't crossed bridge yet)
                   if u.team == 'blue' and u.y > bridge_y + 2:
                       # Move toward bridge center aligned with tower x
                       u.move(nearest_tower.x, bridge_y)
                   elif u.team == 'red' and u.y < bridge_y - 2:
                       # Move toward bridge center aligned with tower x
                       u.move(nearest_tower.x, bridge_y)
                   else:
                       # Close to tower or past bridge, move directly
                       u.move(nearest_tower.x, nearest_tower.y)


class GUI:
   def __init__(self, arena):
       self.arena = arena
       self.root = tk.Tk()
       self.root.title("Arena")
      
       # Canvas for the arena visualization
       self.canvas = tk.Canvas(self.root,
                               width=ARENA_WIDTH*CELL_SIZE,
                               height=ARENA_HEIGHT*CELL_SIZE,
                               bg='#2a2a2a')
       self.canvas.pack(side=tk.TOP)
      
       # --- Frame for the integrated command console ---
       control_frame = tk.Frame(self.root)
       control_frame.pack(side=tk.BOTTOM, fill=tk.X)


       # 1. Input Field
       self.input_entry = tk.Entry(control_frame, width=50)
       self.input_entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
       # Bind the Enter key to the command processor
       self.input_entry.bind('<Return>', self.process_command)
      
       # 2. Submit Button
       submit_btn = tk.Button(control_frame,
                              text="Execute",
                              command=self.execute_button_wrapper)
       submit_btn.pack(side=tk.LEFT, padx=5, pady=5)
      
       print("Type commands (add <card> <pos> <team>, start, or quit) into the box in the window.")
      
       self.loop() # Start the draw loop


   def execute_button_wrapper(self):
       self.process_command(None)


   def process_command(self, event):
       """Processes the command entered in the text box."""
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
       self.canvas.delete('all')
      
       # Grid
       for i in range(ARENA_WIDTH+1):
           self.canvas.create_line(i*CELL_SIZE, 0, i*CELL_SIZE, ARENA_HEIGHT*CELL_SIZE, fill='#444')
       for i in range(ARENA_HEIGHT+1):
           self.canvas.create_line(0, i*CELL_SIZE, ARENA_WIDTH*CELL_SIZE, i*CELL_SIZE, fill='#444')
      
       # River
       self.canvas.create_rectangle(0, 15*CELL_SIZE, ARENA_WIDTH*CELL_SIZE, 17*CELL_SIZE, fill='#1e90ff')
       
       # Bridges
       self.canvas.create_rectangle(2*CELL_SIZE, 15*CELL_SIZE, 5*CELL_SIZE, 17*CELL_SIZE, fill='#8B4513')
       self.canvas.create_rectangle(13*CELL_SIZE, 15*CELL_SIZE, 16*CELL_SIZE, 17*CELL_SIZE, fill='#8B4513')
      
       # Towers
       for team, towers in self.arena.towers.items():
           for t in towers.values():
               if t.health <= 0:
                   continue
               sz = t.size * CELL_SIZE
               # Align to grid
               if t.size == 3:
                   x, y = (t.x-1)*CELL_SIZE, (t.y-1)*CELL_SIZE
               else:  # size 4
                   x, y = (t.x-2)*CELL_SIZE, (t.y-2)*CELL_SIZE
               
               color = '#4169e1' if team == 'blue' else '#dc143c'
               self.canvas.create_rectangle(x, y, x+sz, y+sz, fill=color, outline='white', width=2)
               
               # Health bar
               hp = t.health / t.max_health
               self.canvas.create_rectangle(x+5, y+sz+3, x+5+hp*(sz-10), y+sz+7, fill='#0f0' if hp>0.5 else '#f00')
      
       # Units
       for u in self.arena.units:
           x, y = u.x*CELL_SIZE, u.y*CELL_SIZE
           color = '#4169e1' if u.team == 'blue' else '#dc143c'
           self.canvas.create_oval(x-8, y-8, x+8, y+8, fill=color, outline='white')
  
   def loop_wrapper(self):
       """Call loop and schedule the next call"""
       self.loop()
       self.root.after(16, self.loop_wrapper)


   def loop(self):
       if self.arena.running:
           self.arena.update()
       self.draw()
  
   def start(self):
       self.root.after(16, self.loop_wrapper)
       self.root.mainloop()


def main():
   arena = Arena()
   gui = GUI(arena)
   gui.start()


if __name__ == "__main__":
   main()