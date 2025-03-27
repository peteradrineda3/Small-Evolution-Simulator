import random
from collections import defaultdict
import math
import heapq

class Organism:
    #class variable to track IDs
    _id_counter = 0  

    def __init__(self, genes, energy, position, species, birth_day):
        Organism._id_counter += 1
        self.id = Organism._id_counter
        self.genes = genes
        self.energy = energy
        self.position = position
        self.species = species
        self.birth_day = birth_day
        self.alive = True
        self.fought = False
        self.processed = False
        self.death_day = None
        self.cause_of_death = None
        self.killer_id = None
        self.age = 0
        self.parent = None
        self.children = []
        self.victims = []

    @property
    def diet(self): return self.genes['diet']
    @property
    def aggressiveness(self): return self.genes['aggressiveness']
    @property
    def sight_range(self): return self.genes['sight_range'] if not self.diet == 'carnivore' else self.genes['sight_range'] + 2
    @property
    def strength(self): return self.genes['strength']
    @property
    def defense(self): return self.genes['defense']
    @property
    def efficiency(self): return self.genes['efficiency']
    @property
    def energy_passed_on(self): return self.genes['energy_passed_on']

    def mutate(self):
        new_genes = self.genes.copy()
        #mutate numerical genes
        for key in ['aggressiveness', 'strength', 'defense', 'energy_passed_on']:
            new_genes[key] = max(0, min(1, new_genes[key] + random.gauss(0, 0.05)))
        new_genes['sight_range'] = max(1, min (7, new_genes['sight_range'] + random.randint(-1, 1)))
        new_genes['efficiency'] = max(1, min(2, new_genes['efficiency'] + random.gauss(0, 0.1)))
        
        #mutate diet with 2% chance
        if random.random() < 0.02:
            new_genes['diet'] = random.choice(['herbivore', 'carnivore', 'omnivore'])
        return new_genes

    def get_stats(self):
        stats = f"""
=== Organism {self.id} ({'Alive' if self.alive else 'Dead'}) ===
Species: {self.species}
Age: {self.age} days
Position: {self.position}
Energy: {self.energy:.2f}
Diet: {self.diet}
Parent: {'Organism ' + str(self.parent.id) if self.parent else 'None'}
Children: {[org.id for org in self.children] if self.children else 'None'}
Victims: {self.victims if self.victims else 'None'}
Genes:
  Aggressiveness: {self.aggressiveness:.2f}
  Sight Range: {self.sight_range}
  Strength: {self.strength:.2f}
  Defense: {self.defense:.2f}
  Efficiency: {self.efficiency:.2f}
  Energy Passed On: {self.energy_passed_on:.2f}""".strip()
        
        if not self.alive:
            stats += f"\nCause of Death: {self.cause_of_death}"
            if self.killer_id is not None:
                stats += f"\nKilled by: Organism {self.killer_id}"
            stats += f"\nDied on day {self.death_day}"
        return stats

class EvolutionSimulator:
    def __init__(self, params):
        self.params = params
        self.organisms = []
        self.food = set()
        self.day = 0
        self.dead_organisms = []
        
    def chebyshev_distance(self, pos1, pos2):
        return max(abs(pos1[0]-pos2[0]), abs(pos1[1]-pos2[1]))

    def spawn_food(self):
        self.food = set()
        possible_positions = [(x,y) for x in range(self.params['world_size']) 
                            for y in range(self.params['world_size'])]
        random.shuffle(possible_positions)
        self.food = set(possible_positions[:self.params['food_amount']])

    def place_organisms(self):
        positions = [pos for pos in [(x,y) for x in range(self.params['world_size'])
                    for y in range(self.params['world_size'])] 
                    if pos not in self.food]
        random.shuffle(positions)
        
        for i, org in enumerate(self.organisms):
            if i < len(positions):
                org.position = positions[i]
            else:
                org.alive = False

    def get_visible_entities(self, organism):
        visible = {'food': [], 'organisms': []}
        x, y = organism.position
        
        for dx in range(-organism.sight_range, organism.sight_range+1):
            for dy in range(-organism.sight_range, organism.sight_range+1):
                pos = (x+dx, y+dy)
                if pos in self.food and organism.diet in ['herbivore', 'omnivore']:
                    visible['food'].append(pos)
                
                if (0 <= x+dx < self.params['world_size'] and 
                    0 <= y+dy < self.params['world_size']):
                    for other in self.organisms:
                        if other is organism or not other.alive:
                            continue
                        if other.position == pos and organism.diet in ['carnivore', 'omnivore']:
                            visible['organisms'].append(other)
        return visible

    #handles the entire day cycle
    def process_day(self):
        #spawn food and place organisms
        self.spawn_food()
        self.place_organisms()

        #reset temporary states
        for org in self.organisms:
            org.fought = False
            org.processed = False
        
        #process organisms in random order
        random.shuffle(self.organisms)
        food_contenders = defaultdict(list)
        organism_targets = defaultdict(list)

        #collection phase
        for org in self.organisms:
            if not org.alive or org.processed:
                continue
                
            visible = self.get_visible_entities(org)
            targets = []
            
            #find closest food
            if visible['food']:
                closest_food = min(visible['food'], 
                                  key=lambda pos: self.chebyshev_distance(org.position, pos))
                targets.append(('food', closest_food))

            #find closest organism
            if visible['organisms']:
                closest_org = min(visible['organisms'],
                                 key=lambda o: self.chebyshev_distance(org.position, o.position))
                targets.append(('organism', closest_org))

            if targets:
                #select closest target overall
                target_type, target = min(targets, 
                    key=lambda t: self.chebyshev_distance(org.position, 
                        t[1].position if isinstance(t[1], Organism) else t[1]))
                
                if target_type == 'food':
                    food_contenders[target].append(org)
                else:
                    organism_targets[org].append(target)

        #process organism fights
        #could improve alg for this, currently O(n^2)
        for attacker, targets in organism_targets.items():
            for target in targets:
                if attacker.alive and target.alive and not attacker.fought and not target.fought:
                    if random.random() < attacker.aggressiveness:
                        self.resolve_fight(attacker, target)

        #processing food contention
        for food_pos, contenders in food_contenders.items():
            random.shuffle(contenders)
            survivors = []
            
            #fight for food
            for org in contenders:
                if not org.alive or org.fought:
                    continue
                
                #find nearest contender to fight
                others = [o for o in contenders if o is not org and o.alive and not o.fought]
                if others:
                    closest = min(others, key=lambda o: self.chebyshev_distance(org.position, o.position))
                    if random.random() < org.aggressiveness:
                        self.resolve_fight(org, closest)

            #splitting food among survivors
            eligible = [o for o in contenders if o.alive and o.diet in ['herbivore', 'omnivore']]
            if eligible:
                total = sum(1 if o.diet == 'herbivore' else self.params['omnivore_energy_proportion'] 
                           for o in eligible)
                for org in eligible:
                    portion = (1 if org.diet == 'herbivore' else self.params['omnivore_energy_proportion']) / total
                    org.energy += self.params['energy_per_food'] * portion

        #end of day processing
        new_organisms = []
        dead_today = []
        
        for org in self.organisms:
            if not org.alive:
                continue
                
            #daily energy loss
            org.energy -= self.params['energy_loss_per_day'] * (1 / org.efficiency)
            org.age = self.day - org.birth_day if org.alive else org.death_day - org.birth_day
            if org.energy <= 0:
                org.alive = False
                org.cause_of_death = "Starved"
                org.death_day = self.day
                dead_today.append(org)
            elif org.energy >= self.params['reproduction_energy_threshold']:
                #reproduction
                child_energy = org.energy * org.energy_passed_on
                org.energy -= child_energy
                new_genes = org.mutate()
                child = Organism(new_genes, child_energy, org.position, 
                                org.species, self.day)
                child.parent = org
                new_organisms.append(child)
                org.children.append(child)

        #updating organism lists
        self.dead_organisms.extend([org for org in self.organisms if not org.alive])
        self.organisms = [o for o in self.organisms if o.alive]
        self.organisms.extend(new_organisms)
        self.day += 1

    def resolve_fight(self, a, b):
        # a_score = a.strength * 1 + a.energy * 0.25
        # b_score = b.strength * 1 + b.energy * 0.25
        
        a_score = a.strength * a.energy if not a.diet == 'carnivore' else a.strength * a.energy * 1.5
        b_score = b.strength * b.energy if not b.diet == 'carnivore' else b.strength * b.energy * 1.5

        winner, loser = (a, b) if a_score > b_score else (b, a)
        if a_score == b_score:
            winner, loser = random.choice([(a, b), (b, a)])
        
        if random.random() > loser.defense:
            loser.alive = False
            loser.cause_of_death = "Killed in fight"
            loser.death_day = self.day + 1 #day is incremented at end of day so have to account for it for now
            loser.killer_id = winner.id
            winner.victims.append(loser.id)
            
            if winner.diet == 'carnivore':
                winner.energy += loser.energy * self.params['carnivore_energy_gain']
            elif winner.diet == 'omnivore':
                winner.energy += loser.energy * self.params['omnivore_energy_gain']
        else:
            loss = loser.energy * random.uniform(0, 1 - loser.defense)
            loser.energy -= loss
        
        a.fought = True
        b.fought = True

    def print_daily_summary(self):
        alive_ids = [org.id for org in self.organisms]
        dead_ids = [org.id for org in self.dead_organisms]
        
        print(f"\n=== Day {self.day} Summary ===")
        print(f"Alive organisms ({len(alive_ids)}): {', '.join(map(str, alive_ids))}")
        #print(f"Dead organisms ({len(dead_ids)}): {', '.join(map(str, dead_ids))}")
        print("Type an organism ID to inspect, or 'next' to continue")

    def inspect_organism(self, org_id):
        all_organisms = self.organisms + self.dead_organisms
        found = next((org for org in all_organisms if org.id == org_id), None)
        
        if found:
            print(found.get_stats())
        else:
            print(f"No organism found with ID {org_id}")

    def get_oldest(self, num):
        return [org.id for org in heapq.nlargest(num, self.organisms, key=lambda org: org.age)]
        #maybe add print function in here to avoid having to return values

    def print_diet_summary(self):
        herbivore_ids = [org.id for org in self.organisms if org.diet == 'herbivore']
        omnivore_ids = [org.id for org in self.organisms if org.diet == 'omnivore']
        carnivore_ids = [org.id for org in self.organisms if org.diet == 'carnivore']

        print(f"Herbivores ({len(herbivore_ids)}): {', '.join(map(str, herbivore_ids))}")
        print(f"Omnivores ({len(omnivore_ids)}): {', '.join(map(str, omnivore_ids))}")
        print(f"Carnivores ({len(carnivore_ids)}): {', '.join(map(str, carnivore_ids))}")


def run_interactive_simulation(params, initial_organisms, days):
    sim = EvolutionSimulator(params)
    sim.organisms = initial_organisms
    sim.day = 0
    
    for _ in range(days):
        # sim.process_day()
        sim.print_daily_summary()
        
        while True:
            user_input = input("> ").strip().lower()
            if user_input == 'next':
                break
            elif user_input == 'quit':
                print("\n=== Simulation ended early ===")
                print(f"Stopped after day {sim.day}")
                return
            elif user_input == 'oldest':
                print(sim.get_oldest(10))
            elif user_input == 'dead':
                dead_ids = [org.id for org in sim.dead_organisms]
                print(f"Dead organisms ({len(dead_ids)}): {', '.join(map(str, dead_ids))}")
            elif user_input == 'diets':
                sim.print_diet_summary()
            elif user_input.isdigit():
                sim.inspect_organism(int(user_input))
            else:
                print("Invalid input. Commands:")
                print("  [ID] - Inspect organism")
                print("  next - Continue to next day")
                print("  quit - End simulation early")

        sim.process_day()

    print("\n=== Simulation completed ===")
    print(f"Finished {days} days of simulation")

#example parameters
params = {
    'world_size': 20,
    'food_amount': 100,
    'energy_per_food': 35,
    'energy_loss_per_day': 50,
    'reproduction_energy_threshold': 60,
    'omnivore_energy_proportion': 0.6,
    'carnivore_energy_gain': 1,
    'omnivore_energy_gain': 0.7,
}

#initialising with some organisms
initial_organisms = []
for _ in range(20):
    genes = {
        'aggressiveness': random.uniform(0, 1),
        'sight_range': random.randint(1, 7),
        'strength': random.uniform(0, 1),
        'defense': random.uniform(0, 1),
        'diet': random.choice(['herbivore', 'carnivore', 'omnivore']),
        'efficiency': random.uniform(1, 2),
        'energy_passed_on': random.uniform(0.1, 0.5),
    }
    initial_organisms.append(Organism(genes, 100, (0,0), "species1", birth_day=0))

run_interactive_simulation(params, initial_organisms, days=100)

### ADD NEXT
# add 'oldest living ancestor' and 'oldest living child' to each organism
# add a way to move forward a set amount of days (maybe by doing 'next 20' means +20 days)
# different sized food
# different sized organisms
# different types of food
# parent/child dynamics (children follow parents)
# change all parameters to be tweakable constants
# show all organisms killed by certain organisms
# show all organisms killed in a certain day
# show the day that organism died on/was born
# add summary statistics
# display family tree for organism families
# add action history for each organism
# split into multiple files for each class
# add proper function commenting
# allow user to add an organism whenever they want
## maybe implement a statistical analysis model that shows which of the genes were the most impactful in current simulation
## visualisation of everything