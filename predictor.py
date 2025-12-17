# Made by Michael Hodis and Jonah Shatkin
# Clash Royale Predictor that recommends best card to play
import math, json

try:
    with open('clash_royale_cards.json', 'r') as f:
        data = json.load(f)
    CARDS, NAMES = data['CARDDATA'], data['METADATA']['card_names']
except: CARDS, NAMES = {}, {}

POSITIONS = {
    'blue': {
        'bl': (3.5, 17), 'br': (14.5, 17),
        'fl': (6, 26),   'fr': (11, 26),
        'ml': (8, 20),   'mr': (9, 20),
        'sl': (0, 24),   'sr': (17, 24),
        'tl': (3, 25),   'tr': (14, 25),
        'pl': (8, 22),   'pr': (9, 22),
        'ol': (3, 21),   'or': (14, 21),
        'kl': (8, 26),   'kr': (9, 26),
        'rl': (3, 23),   'rr': (14, 23)
    },
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

class Predictor:
    def __init__(self, arena, team='blue'):
        self.arena, self.team = arena, team
        self.enemy = 'red' if team == 'blue' else 'blue'
        self.hand, self.next_card = [], None
        self.last_update, self.recommendation = 0, None

    # Each clash game starts with your hand of 4 cards. 
    # The other 4 cards are also randomized so you don't 
    # know what you're going to start with each round.
    def set_hand(self, cards):
        self.hand = list(cards[:4])
        # Replaced list comprehension for printing
        card_names_list = []
        for c in self.hand:
            card_names_list.append(NAMES.get(c, c))
        print(f"Hand: {card_names_list}")

    # We could add a queue in the future in order to not have 
    # to keep calling this after the first 4 times, but we ran out of time.
    def set_next(self, card):
        self.next_card = card
        print(f"Next: {NAMES.get(card,card)}")

    def play_card(self, card):
        if card in self.hand:
            self.hand.remove(card)
            if self.next_card:
                self.hand.append(self.next_card)
                self.next_card = None
            
            # Replaced list comprehension for printing
            card_names_list = []
            for c in self.hand:
                card_names_list.append(NAMES.get(c, c))
            print(f"Played: {NAMES.get(card,card)} | Hand: {card_names_list}")

    # This is how we see what the threat it and use this as our heuristic in the future

    # Algorithm:
    # Loop through all enemy units
    # For each enemy, check distance to each of your alive towers
    # If enemy is within 12 tiles of a tower:
    # threat += enemy.damage * (12 - distance) / 12
    # Closer enemy = higher multiplier
    # Higher damage enemy = more threat

    def get_threat(self):
        threat = 0
        for u in self.arena.units:
            if u.team == self.enemy:
                for t in self.arena.towers[self.team].values():
                    if t.health > 0:
                        d = math.sqrt((u.x-t.x)**2 + (u.y-t.y)**2)
                        if d < 12: threat += u.damage * (12-d) / 12
        return min(100, threat/5)

    # Finds the best countering card to the incoming push.
    # This encourages positive elixir trades but is also greedy and could use a card 
    # Like arrows and leave us unprepared for another push
    def get_counter(self, enemy):
        etype, flying = CARDS.get(enemy.key,{}).get('type',''), enemy.flying
        elixir, best, best_score = self.arena.elixir[self.team], None, -999
        
        for card in self.hand:
            info = CARDS.get(card,{})
            cost = info.get('elixir',10)
            if isinstance(cost,str) or cost > elixir: 
                continue
            if flying and info.get('targets')=='ground': 
                continue
            
            ctype = info.get('type','')
            if etype in ['tank','minitank'] and ctype=='swarm': score = 50
            elif etype in ['swarm','rangedswarm'] and info.get('spell'): score = 50
            elif etype=='tank' and info.get('damage',0) > 300: score = 40
            else: score = info.get('damage',0) / 10
            score += (10-cost) * 3
            
            if score > best_score: best, best_score = card, score
        return best

    # Now that we know what card we're playing, where do we play it?
    # Suggests where to play a given card

    # Parameters:
    # card: the card code to place
    # defensive: True if we're defending (high threat level)

    # 1. Defensive placement (defending an attack):
    # Alternate between tl and tr based on time
    # Places troops near your princess towers to intercept

    # 2. Spells:
    # Look at where enemies are
    # bl if enemies are on left (x < 9)
    # br if enemies are on right
    # Default to bl if no enemies

    # 3. Tanks (Giant, Knight):
    # fl or fr (far back positions)
    # Alternates based on time
    # Back placement lets you build a push behind them

    # 4. Support troops:
    # bl or br (bridge positions)
    # Aggressive placement at the bridge
    def get_position(self, card, defensive=False):
        if defensive: 
            enemies = [u for u in self.arena.units if u.team == self.enemy]
            return ('tl' if enemies[0].x < 9 else 'tr') if enemies else 'tl'
        info = CARDS.get(card,{})
        if info.get('spell'):
            enemies = [u for u in self.arena.units if u.team == self.enemy]
            return ('bl' if enemies[0].x < 9 else 'br') if enemies else 'bl'
        if info.get('type')=='tank': return 'fl' if self.arena.match_time % 4 < 2 else 'fr'
        return 'bl' if self.arena.match_time % 2 < 1 else 'br'

    # Custom key function for sorting enemy units by nearest tower distance (Replaces lambda)
    def _sort_by_nearest_tower(self, u):
        min_d = float('inf')
        for t in self.arena.towers[self.team].values():
            if t.health > 0:
                d = math.sqrt((u.x-t.x)**2+(u.y-t.y)**2)
                if d < min_d:
                    min_d = d
        return min_d

    # Use a tree searching method to get the best reccomendation
    def get_recommendation(self, force=False):
        now = self.arena.match_time
        if not force and self.recommendation and now - self.last_update < 3: 
            return self.recommendation
        
        self.last_update = now
        elixir, threat = self.arena.elixir[self.team], self.get_threat()
        
        # Using this method, we can input any number of things into this method as we want!
        def create_recommendation(**kwargs):
            result = {'threat_level': threat}
            result.update(kwargs)
            return result

        if not self.hand:
            self.recommendation = create_recommendation(card=None,card_name='Set hand',position=None,elixir_cost=0,reason='Use: hand <4 cards>')
            return self.recommendation

        enemies = [u for u in self.arena.units if u.team == self.enemy]
        
        if threat > 50 and enemies:
            # Replaced sort key lambda with a custom method
            enemies.sort(key=self._sort_by_nearest_tower)
            card = self.get_counter(enemies[0])
            if card:
                self.recommendation = create_recommendation(card=card,card_name=NAMES.get(card,card),position=self.get_position(card,True),elixir_cost=CARDS[card]['elixir'],reason=f"Defend ({threat:.0f}%)")
                return self.recommendation

        if elixir >= 7:
            for card in ['gia','kni']:
                if card in self.hand and elixir >= CARDS[card]['elixir']:
                    self.recommendation = create_recommendation(card=card,card_name=NAMES.get(card,card),position=self.get_position(card),elixir_cost=CARDS[card]['elixir'],reason='Start push')
                    return self.recommendation

        self.recommendation = create_recommendation(card=None,card_name='Wait',position=None,elixir_cost=0,reason=f'Save elixir ({elixir:.1f})')
        return self.recommendation

    def on_card_played(self, card=None):
        if card: self.play_card(card)
        self.get_recommendation(force=True)

    def get_hand_display(self):
        if not self.hand: return "No hand set"
        
        hand_names = []
        for c in self.hand:
            hand_names.append(NAMES.get(c, c))

        return f"Hand: {', '.join(hand_names)}\nNext: {NAMES.get(self.next_card,'?')}"