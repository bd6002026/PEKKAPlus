# Made by Michael Hodis and Jonah Shatkin
# This program uses simple cards from the first few arenas and uses graphs (trees) # to find the optimal cards to play based on the "Threat Level" heuristic

import json, math, tkinter as tk

try:
    from predictor import Predictor
    HAS_PREDICTOR = True
except: HAS_PREDICTOR = False

# Load card data
with open('clash_royale_cards.json', 'r') as f:
    data = json.load(f)
card_data, card_names = data['CARDDATA'], data['METADATA']['card_names']

ARENA_W, ARENA_H, CELL = 18, 32, 20
LEFT_BRIDGE, RIGHT_BRIDGE = 3.5, 14.5

# Most troops are just one but these swarm troops are
# special so we just added them here. 
# Each troop of 3 spawns in a triangle and the archers spawn in a row.
TROOP_COUNTS = {
    'arc': 2,
    'mns': 3,
    'gob': 3,
    'spe': 3
}

# In order to simplify the placing process, we added shortcuts for the names of each location cards are frequently placed at. 
# This means that there's less controllability when playing but it is also easier to type each command out
POSITIONS = {
    'blue': {
        'bl': (3.5, 17), 'br': (14.5, 17), # Bridge 
        'fl': (6, 26),   'fr': (11, 26), # Far (back)
        'ml': (8, 20),   'mr': (9, 20), # Middle
        'sl': (0, 24),   'sr': (17, 24), # Sides
        'tl': (3, 25),   'tr': (14, 25), # By the tower
        'pl': (8, 22),   'pr': (9, 22), # Pocket
        'ol': (3, 21),   'or': (14, 21), # Offense
        'kl': (8, 26),   'kr': (9, 26), # King tower
        'rl': (3, 23),   'rr': (14, 23) # Princess tower (behind)
    },
    # Everything is mirrored for red team
    'red': {
        'bl': (3.5, 14), 'br': (14.5, 14),
        'fl': (6, 5),    'fr': (11, 5),
        'ml': (8, 11),   'mr': (9, 11),
        'sl': (0, 7),    'sr': (17, 7),
        'tl': (3, 6),    'tr': (14, 6),
        'pl': (8, 9),    'pr': (9, 9),
        'ol': (3, 10),   'or': (14, 10),
        'kl': (8, 5),    'kr': (9, 5),
        'rl': (3, 8),    'rr': (14, 8)
    }
}

# The Unit class that represents a troop on the field. 
# Each troop uses a 3 letter abbreviation that makes it easier to type out
class Unit:

    # Info taken from the JSON
    def __init__(self, key, x, y, team, spawn_pos=None):
        self.key, self.x, self.y, self.team, self.spawn_pos = key, float(x), float(y), team, spawn_pos
        c = card_data[key]
        self.health = self.max_health = c['health']
        self.speed, self.damage = c['speed']/3600, c['damage']
        self.hitspeed, self.attack_radius = c['hitspeed'], c['attackradius']
        self.attack_cooldown, self.flying = c['firsthit']*60, c['flying']
        self.targets = c['targets']

    # Every iteration move the troop in the direction it's pathing towards, calculated later on.
    def move(self, tx, ty):
        dx, dy = tx - self.x, ty - self.y
        d = math.sqrt(dx*dx + dy*dy)
        if d > 0: self.x += (dx/d)*self.speed; self.y += (dy/d)*self.speed

    # Euclidian distance between two points
    def dist(self, x, y): return math.sqrt((self.x-x)**2 + (self.y-y)**2)

# Separate class for spells only
class Spell:
    # Spells have a lot of stats like speed or attack speed that aren't necessary
    def __init__(self, key, x, y, team):
        self.key, self.x, self.y, self.team = key, float(x), float(y), team
        c = card_data[key]
        self.damage, self.radius = c['damage'], c['attackradius']
        self.delay = 60 if key == 'arr' else 90

    # Counts down until the spell hits the arena
    def update(self):
        self.delay -= 1
        return self.delay <= 0

# Represents the princess and king towers on the arena. Just stores info about them.
class Tower:
    def __init__(self, name, x, y, hp, dmg, size):
        self.name, self.x, self.y, self.size = name, x, y, size
        self.health = self.max_health = hp
        self.damage = dmg
        self.attack_radius, self.hitspeed = card_data['pri']['attackradius'], card_data['pri']['hitspeed']
        self.attack_cooldown = 0

# This is where most of the calculations occur
class Arena:
    def __init__(self):
        self.units, self.spells = [], []
        self.towers = {
            'blue': {'left':Tower('left',3.5,24.5,3052,109,3), 'right':Tower('right',14.5,24.5,3052,109,3), 'king':Tower('king',9,29,5000,122,4)},
            'red':  {'left':Tower('left',3.5,7.5,3052,109,3),  'right':Tower('right',14.5,7.5,3052,109,3),  'king':Tower('king',9,3,5000,122,4)}
        }
        self.elixir = {'blue':5.0, 'red':5.0}
        self.max_elixir, self.match_time, self.match_duration, self.running = 10.0, 0.0, 180.0, False

    # Update elixir based on how much time is left in the match.
    # Single elixir - 1 elixir every 2.8 seconds
    # Double elixir - 2 elixir every 2.8 seconds
    # Triple elixir - 3 elixir every 2.8 seconds
    def get_elixir_rate(self):
        if self.match_time < 120: 
            return (1.0/2.8)
        elif self.match_time < 180:
            return (2.0/2.8) 
        else:
            return (3.0/2.8)

    # Get the time so we can display it and use it for anything else
    def get_time_string(self):
        r = max(0, self.match_duration - self.match_time)
        return f"{int(r//60)}:{int(r%60):02d}"

    def get_elixir_mode(self):
        if self.match_time < 120: return "NORMAL"
        return "DOUBLE" if self.match_time < 180 else "TRIPLE"

    # Typing the word 'add' into the execute bar at the bottom of the
    # screen will use this method to add troops
    def add_unit(self, key, pos, team):
        if key not in card_data or team not in POSITIONS or pos not in POSITIONS[team]:
            print(f"Invalid: {key} {pos} {team}"); return False
        cost = card_data[key]['elixir']
        if isinstance(cost, str): cost = 0
        if self.elixir[team] < cost:
            print(f"Need {cost} elixir, have {self.elixir[team]:.1f}"); return False
        
        self.elixir[team] -= cost
        x, y = POSITIONS[team][pos]
        
        if card_data[key]['spell']:
            self.spells.append(Spell(key, x, y, team))
        else:
            count = TROOP_COUNTS.get(key, 1)
            offsets = [(0,0)] if count==1 else [(-0.5,0),(0.5,0)] if count==2 else [(0,0),(-0.5,0.5),(0.5,0.5)]
            for dx,dy in offsets:
                self.units.append(Unit(key, x+dx, y+dy, team, spawn_pos=pos))
        
        print(f"Added {card_names[key]} ({team}) at {pos} [-{cost}]")
        return True

    # We want to path to the bridge first, and then go to
    # the tower, just like what we found happens ingame.
    def get_bridge_x(self, unit):
        is_pocket = unit.spawn_pos in ['pl','pr']
        enemy = 'red' if unit.team == 'blue' else 'blue'

        # Pocket is special because if you place it there
        # it will either go to the other princess tower
        # or king tower if both princess towers are destroyed
        if is_pocket:
            l, r = self.towers[enemy]['left'].health > 0, self.towers[enemy]['right'].health > 0
            if l and r: return LEFT_BRIDGE if unit.x < 9 else RIGHT_BRIDGE
            if l: return LEFT_BRIDGE
            if r: return RIGHT_BRIDGE
        return LEFT_BRIDGE if unit.x < 9 else RIGHT_BRIDGE

    # If there's a troop in sight range, they will take precedence over buildings.
    def find_target(self, unit):
        enemy = 'red' if unit.team == 'blue' else 'blue'
        nearest, min_d = None, float('inf')
        sight = card_data[unit.key]['sightrange']

        # If it targets only buildings (Giant) then it will ignore all of this
        if unit.targets != "buildings":
            for o in self.units:
                if o.team != unit.team and o.health > 0:
                    # Check if one troop can target the other troop
                    if not unit.flying and o.flying and unit.targets == "ground": 
                        continue
                    d = unit.dist(o.x, o.y)
                    if d < min_d and d <= sight: min_d, nearest = d, o

        # Otherwise, if there's no troop in sight or if you only target buildings, go to the nearest tower.
        if nearest is None or unit.targets == "buildings":
            towers = self.towers[enemy]
            if unit.targets == "buildings":
                is_pocket = unit.spawn_pos in ['pl','pr']
                l, r, k = towers['left'], towers['right'], towers['king']
                if is_pocket:
                    if l.health > 0 and r.health > 0:
                        nearest = l if unit.dist(l.x,l.y) < unit.dist(r.x,r.y) else r
                    elif l.health > 0: nearest = l
                    elif r.health > 0: nearest = r
                    else: nearest = k
                else:
                    if unit.x < 9: nearest = l if l.health > 0 else k
                    else: nearest = r if r.health > 0 else k
            else:
                for t in towers.values():
                    if t.health > 0:
                        d = unit.dist(t.x, t.y)
                        if d < min_d: min_d, nearest = d, t
        return nearest

    # Uses delta time like we explained in class to update the time and elixir
    def update(self):
        self.match_time += 1/60
        rate = self.get_elixir_rate()
        for t in ['blue','red']: self.elixir[t] = min(self.max_elixir, self.elixir[t] + rate/60)

        for s in self.spells[:]:
            if s.update():
                enemy = 'red' if s.team == 'blue' else 'blue'
                for u in self.units:
                    if u.team == enemy and math.sqrt((s.x-u.x)**2+(s.y-u.y)**2) <= s.radius:
                        u.health -= s.damage
                self.spells.remove(s)

        for u in self.units:
            if u.health <= 0: 
                continue
            target = self.find_target(u)
            if not target: 
                continue
            
            d = u.dist(target.x, target.y)
            is_tower = hasattr(target, 'size')
            stop_d = (target.size/2 + 0.5) if is_tower else u.attack_radius
            can_attack = d <= u.attack_radius + (stop_d if is_tower else 0)
            
            if can_attack:
                if u.attack_cooldown <= 0:
                    target.health -= u.damage
                    u.attack_cooldown = u.hitspeed * 60
            elif d > stop_d:
                if not u.flying and is_tower:
                    bridge_y = 16 if u.team == 'blue' else 15
                    needs_cross = (u.team=='blue' and u.y > bridge_y+0.5) or (u.team=='red' and u.y < bridge_y-0.5)
                    if needs_cross: u.move(self.get_bridge_x(u), bridge_y)
                    else: u.move(target.x, target.y)
                else: u.move(target.x, target.y)
            
            if u.attack_cooldown > 0: u.attack_cooldown -= 1

        for team in ['blue','red']:
            enemy = 'red' if team == 'blue' else 'blue'
            for t in self.towers[team].values():
                if t.health <= 0: 
                    continue

                nearest, min_d = None, float('inf')
                
                for u in self.units:
                    if u.team == enemy and u.health > 0:
                        d = math.sqrt((t.x-u.x)**2 + (t.y-u.y)**2)
                        if d <= t.attack_radius and d < min_d: 
                            min_d = d
                            nearest = u
                if nearest and t.attack_cooldown <= 0:
                    nearest.health -= t.damage
                    t.attack_cooldown = t.hitspeed * 60
                if t.attack_cooldown > 0: t.attack_cooldown -= 1

        self.units = [u for u in self.units if u.health > 0]

# Draw everything using TKinter 
class GUI:
    def __init__(self, arena):
        self.arena = arena
        self.root = tk.Tk()
        self.root.title("Arena")
        
        main = tk.Frame(self.root)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(main, width=ARENA_W*CELL, height=ARENA_H*CELL, bg='#2a2a2a')
        self.canvas.pack(side=tk.LEFT)
        
        self.predictor = None
        if HAS_PREDICTOR:
            self.predictor = Predictor(arena, 'blue')
            panel = tk.Frame(main, width=180, bg='#1a1a2e')
            panel.pack(side=tk.RIGHT, fill=tk.Y)
            panel.pack_propagate(False)
            tk.Label(panel, text="PREDICTOR", font=('Arial',12,'bold'), bg='#1a1a2e', fg='#00ff88').pack(pady=5)
            self.hand_label = tk.Label(panel, text="No hand set", font=('Arial',9), bg='#1a1a2e', fg='#aaa', wraplength=160, justify=tk.LEFT)
            self.hand_label.pack(pady=5, padx=10)
            tk.Frame(panel, height=2, bg='#444').pack(fill=tk.X, padx=10, pady=5)
            self.rec_label = tk.Label(panel, text="Waiting...", font=('Arial',10), bg='#1a1a2e', fg='white', wraplength=160, justify=tk.LEFT)
            self.rec_label.pack(pady=10, padx=10)
            self.threat_label = tk.Label(panel, text="Threat: --", font=('Arial',10), bg='#1a1a2e', fg='#ffaa00')
            self.threat_label.pack(pady=5)
        
        ctrl = tk.Frame(self.root)
        ctrl.pack(side=tk.BOTTOM, fill=tk.X)
        self.entry = tk.Entry(ctrl, width=50)
        self.entry.pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)
        self.entry.bind('<Return>', self.cmd)
        
        # Lambda replaced with a helper method
        tk.Button(ctrl, text="Run", command=self.run_command).pack(side=tk.LEFT, padx=5, pady=5)
        
        print("Commands: hand/next/add/start/quit")

    # Helper function for the 'Run' button command
    def run_command(self):
        self.cmd(None)

    # Refresh the predictions and suggestions
    def update_predictor(self):
        if not self.predictor: return
        self.hand_label.config(text=self.predictor.get_hand_display())
        r = self.predictor.get_recommendation()
        if r:
            txt = f"Play: {r['card_name']}\nAt: {r['position']}\nCost: {r['elixir_cost']}\n\n{r['reason']}" if r['card'] else r['reason']
            self.rec_label.config(text=txt)
            self.threat_label.config(text=f"Threat: {r['threat_level']:.0f}%")

    # List of all of the commands you can use
    # Each one is based on the first word typed
    def cmd(self, e):
        txt = self.entry.get().strip().lower()
        self.entry.delete(0, tk.END)
        if not txt: return
        c = txt.split()
        
        if c[0] == 'quit': self.root.quit()
        elif c[0] == 'hand' and len(c) >= 5:
            if self.predictor: self.predictor.set_hand(c[1:5]); self.update_predictor()
        elif c[0] == 'next' and len(c) >= 2:
            if self.predictor: self.predictor.set_next(c[1]); self.update_predictor()
        elif c[0] == 'add' and len(c) == 4:
            card_key, team = c[1], c[3]
            if self.arena.add_unit(card_key, c[2], team):
                # BUG FIX: Only update the predictor's hand if the card was played by the predictor's team ('blue')
                if self.predictor and team == 'blue': 
                    self.predictor.on_card_played(card_key)
                    self.update_predictor()
        elif c[0] == 'start':
            self.arena.running = True; print("Started!"); self.update_predictor()
        else: print(f"Unknown: {txt}")

    # Create the entire arena using basic TKinter functions and some trial and error
    def draw(self):
        cv = self.canvas
        cv.delete('all')
        
        # Grid
        for i in range(ARENA_W+1): cv.create_line(i*CELL, 0, i*CELL, ARENA_H*CELL, fill='#444')
        for i in range(ARENA_H+1): cv.create_line(0, i*CELL, ARENA_W*CELL, i*CELL, fill='#444')
        
        # River & bridges
        cv.create_rectangle(0, 15*CELL, ARENA_W*CELL, 17*CELL, fill='#1e90ff')
        cv.create_rectangle(2*CELL, 15*CELL, 5*CELL, 17*CELL, fill='#8B4513')
        cv.create_rectangle(13*CELL, 15*CELL, 16*CELL, 17*CELL, fill='#8B4513')
        
        # Timer
        cv.create_rectangle(ARENA_W*CELL//2-40, 5, ARENA_W*CELL//2+40, 25, fill='#333', outline='white', width=2)
        cv.create_text(ARENA_W*CELL//2, 15, text=self.arena.get_time_string(), font=('Arial',12,'bold'), fill='white')
        mode = self.arena.get_elixir_mode()
        col = '#0f0' if mode=="NORMAL" else '#f90' if mode=="DOUBLE" else '#f00'
        cv.create_text(ARENA_W*CELL//2, 35, text=mode, font=('Arial',10,'bold'), fill=col)
        
        # Elixir
        cv.create_rectangle(10, ARENA_H*CELL-30, 80, ARENA_H*CELL-10, fill='#1a1a3e', outline='#4169e1', width=2)
        cv.create_text(45, ARENA_H*CELL-20, text=f"{self.arena.elixir['blue']:.1f}", font=('Arial',10,'bold'), fill='#4169e1')
        cv.create_rectangle(10, 10, 80, 30, fill='#3e1a1a', outline='#dc143c', width=2)
        cv.create_text(45, 20, text=f"{self.arena.elixir['red']:.1f}", font=('Arial',10,'bold'), fill='#dc143c')
        
        # Spells
        for s in self.arena.spells:
            x, y, r = s.x*CELL, s.y*CELL, s.radius*CELL/2
            col = '#4169e1' if s.team=='blue' else '#dc143c'
            cv.create_oval(x-r, y-r, x+r, y+r, outline=col, width=2, dash=(5,5))
            cv.create_oval(x-5, y-5, x+5, y+5, fill=col, outline='white')
            cv.create_text(x, y-r-10, text=f"{s.delay/60:.1f}s", font=('Arial',10,'bold'), fill=col)
        
        # Towers
        for team, towers in self.arena.towers.items():
            for t in towers.values():
                if t.health <= 0: continue
                sz = t.size * CELL
                cx, cy = t.x*CELL, t.y*CELL
                x, y = cx - sz//2, cy - sz//2
                col = '#4169e1' if team=='blue' else '#dc143c'
                cv.create_rectangle(x, y, x+sz, y+sz, fill=col, outline='white', width=2)
                hp = t.health / t.max_health
                # Add it so that if the health is low, it turns red!
                cv.create_rectangle(x+5, y+sz+3, x+5+hp*(sz-10), y+sz+7, fill='#00ff00' if hp>0.5 else '#ff0000')
        
        # Units
        for u in self.arena.units:
            x, y = u.x*CELL, u.y*CELL
            col = '#4169e1' if u.team=='blue' else '#dc143c'
            cv.create_oval(x-8, y-8, x+8, y+8, fill=col, outline='white')
            cv.create_text(x, y, text=u.key.upper(), font=('Arial',8,'bold'), fill='white')
            hp = u.health / u.max_health
            cv.create_rectangle(x-10, y-15, x-10+20*hp, y-12, fill='#0f0' if hp>0.5 else '#f00')

    def loop(self):
        if self.arena.running:
            self.arena.update()
            self.update_predictor()
        self.draw()
        self.root.after(16, self.loop)

    def start(self):
        self.root.after(16, self.loop)
        self.root.mainloop()

if __name__ == "__main__":
    GUI(Arena()).start()


# Although we did some testing using the methods below, we later 
# found it was easier to code the terminal into the TKinter window to test faster

# def test_arena():
#     """Test arena mechanics"""
#     arena = Arena()
#     
#     print(f"Blue elixir: {arena.elixir['blue']}")
#     print(f"Red elixir: {arena.elixir['red']}")
#     print(f"Match time: {arena.match_time}")
#     
#     arena.add_unit('kni', 'bl', 'blue')
#     arena.add_unit('gia', 'fl', 'blue')
#     print(f"Units on field: {len(arena.units)}")
#     print(f"Blue elixir after spawns: {arena.elixir['blue']}")
#     
#     arena.add_unit('arr', 'br', 'blue')
#     print(f"Spells on field: {len(arena.spells)}")
#     
#     arena.running = True
#     for i in range(60):  # 1 second of updates
#         arena.update()
#     print(f"Time after 60 frames: {arena.match_time:.2f}s")
#     print(f"Blue elixir after 1s: {arena.elixir['blue']:.2f}")
#     
#     for u in arena.units:
#         print(f"  {card_names[u.key]}: ({u.x:.1f}, {u.y:.1f}) HP: {u.health}")
#     
#     for team in ['blue', 'red']:
#         for name, tower in arena.towers[team].items():
#             print(f"  {team} {name}: {tower.health}/{tower.max_health}")
#     
#     arena.match_time = 0
#     print(f"  0s: {arena.get_elixir_mode()} ({arena.get_elixir_rate()}x)")
#     arena.match_time = 120
#     print(f"  120s: {arena.get_elixir_mode()} ({arena.get_elixir_rate()}x)")
#     arena.match_time = 180
#     print(f"  180s: {arena.get_elixir_mode()} ({arena.get_elixir_rate()}x)")
#     
#     arena2 = Arena()
#     arena2.add_unit('gia', 'fl', 'blue')  # Left side spawn
#     arena2.add_unit('gia', 'fr', 'blue')  # Right side spawn
#     arena2.add_unit('gia', 'pl', 'blue')  # Pocket left
#     for u in arena2.units:
#         bridge = arena2.get_bridge_x(u)
#         print(f"  Spawn {u.spawn_pos}: bridge_x = {bridge}")
#     

# def test_combat():
#     """Test combat mechanics"""
#     arena = Arena()
#     arena.running = True
#     
#     arena.add_unit('kni', 'bl', 'blue')
#     arena.add_unit('kni', 'bl', 'red')
#     
#     blue_kni = [u for u in arena.units if u.team == 'blue'][0]
#     red_kni = [u for u in arena.units if u.team == 'red'][0]
#     
#     print(f"Initial - Blue: {blue_kni.health} HP, Red: {red_kni.health} HP")
#     
#     # Simulate until one dies
#     frames = 0
#     while blue_kni.health > 0 and red_kni.health > 0 and frames < 600:
#         arena.update()
#         frames += 1
#     
#     print(f"After {frames} frames ({frames/60:.1f}s):")
#     print(f"  Blue Knight: {blue_kni.health} HP")
#     print(f"  Red Knight: {red_kni.health} HP")
#     print(f"  Units remaining: {len(arena.units)}")

# if __name__ == "__main__":
#     test_arena()
#     test_combat()