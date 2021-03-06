import random
import component as cp
from material import shipparts
from sets import Set
from engine.component import InfluenceDisc, Ship, DiscoveryTile

__author__="jglouis"
__date__ ="$Dec 21, 2011 10:49:19 AM$"

class Zone(object):
    def __init__(self, owner = None, *args):
        self.owner = owner
        self.components = []
        for c in args:
            self.components.add(c)

    def get_components(self, component_type = None, **kwargs):
        """Return either a list/dict of components or the number of components."""
        if component_type is not None:
            return [comp for comp in self.components if isinstance(comp, component_type)]        
        return self.components
    
    def add(self, component, **kwargs):
        """Add a component to the zone."""
        self.components.append(component)
        
    def take(self, component = None, component_type = None, **kwargs):
        """return a component and remove it from the zone."""
        if component is None:
            if component_type is None:
                return self.components.pop()
            for n, comp in enumerate(self.components):
                if isinstance(comp, component_type):
                    return self.components.pop(n)
        self.components.remove(component)
        return component

class Board(Zone):
    neighbours = ( (1, 1), (2, 0), (1, -1), (-1, -1), (-2, 0), (-1, 1) )

    def __init__(self, game):
        #super(Board, self).__init__()
        self.hex_grid = {} #a dictionary coord->Sector
        self.game = game

    def add(self, coord, component, rotation = 0):
        """Add the specified component to the given coordinates on the board."""
        if isinstance(component, cp.SectorTile):
            sector = Sector(component)
            self.hex_grid[coord] = sector
            #place discovery tiles
            if component.discovery:
                sector.add(self.game.discovery_tiles_draw_pile.draw())
            #place ancients ships/galactic center
            if component.n_ancients == -1:
                sector.add(cp.GalacticCenterDefenseSystem())
            else:
                for dummy in range(component.n_ancients):
                    sector.add(cp.AncientShip())
            #create resource slots
            for dummy in range(component.n_money):
                sector.add(ResourceSlot(resource_type = 'money'))
            for dummy in range(component.nr_money):
                sector.add(ResourceSlot(resource_type = 'money', advanced = 'True'))
            for dummy in range(component.n_science):
                sector.add(ResourceSlot(resource_type = 'science'))
            for dummy in range(component.nr_science):
                sector.add(ResourceSlot(resource_type = 'science', advanced = 'True'))
            for dummy in range(component.n_material):
                sector.add(ResourceSlot(resource_type = 'material'))
            for dummy in range(component.nr_material):
                sector.add(ResourceSlot(resource_type = 'material', advanced = 'True'))
            for dummy in range(component.n_wild):
                sector.add(ResourceSlot())
            #rotate the sector
            sector.rotate(rotation)
        elif isinstance(component, Sector):
            self.hex_grid[coord] = component
            sector = component
        else:
            self.hex_grid[coord].add(component)
            sector = self.hex_grid[coord]
        return sector

    def get_components(self, coord = None, component_type = None):
        """
        If coord is not given, then it returns the whole board dictionary.
        If coord is given, then it returns the content of the corresponding hex.
        The first item of the list is always the sector itself.
        """
        if coord is None:
            if component_type is None:
                return self.hex_grid
            return dict([(coord, sector.get_components(component_type)) for coord,sector in self.hex_grid.iteritems()])
        if coord not in self.hex_grid:
            return None
        if component_type is Sector:
            return self.hex_grid[coord]
        if component_type is not None:
            return self.hex_grid[coord].get_components(component_type)
        return [self.hex_grid[coord]] + self.hex_grid[coord].get_components()

    def get_coords_owned_by(self, player):
        result = []
        for coord in self.hex_grid:
            sector = self.hex_grid[coord]
            influence = sector.get_components(component_type = InfluenceDisc)
            if len(influence) > 0 and influence[0].owner == player:
                result.append(coord)
        return result
    
    def get_coords_with_ships_of(self, player):
        result = []
        for coord in self.hex_grid:
            sector = self.hex_grid[coord]
            ships = [ ship for ship in sector.get_components(component_type = Ship) if ship.owner == player ]
            if len(ships) > 0:
                result.append(coord)
        return result
    
    def get_exploration_options_for(self, player):
        result = Set()
        owned = self.get_coords_owned_by(player)
        ships = self.get_coords_with_ships_of(player)
        for coord in owned + ships:
            from_hex = self.hex_grid[coord]
            for wormhole_index in xrange(len(self.neighbours)):
                connected = (player.can_generate_wormholes() or
                             from_hex.wormholes[(wormhole_index - from_hex.rotation) % 6] == 1)
                if connected:
                    delta = self.neighbours[wormhole_index]
                    to_hex = (coord[0] + delta[0], coord[1] + delta[1])
                    if to_hex not in self.hex_grid:
                        result.add(to_hex)
        return result

    def get_explore_source_hex(self, player, coords):
        """
        Find all possible hexes the given player could explore the nominated coordinates from
        """
        result = []
        for neighbour_index in xrange(len(self.neighbours)):
            delta = self.neighbours[neighbour_index]
            from_hex_coords = (coords[0] + delta[0], coords[1] + delta[1])
            if from_hex_coords in self.hex_grid:
                from_hex = self.hex_grid[from_hex_coords]
                player_influence = [ disc for disc in from_hex.get_components(component_type = InfluenceDisc) if disc.owner == player ]
                player_ships = [ ship for ship in from_hex.get_components(component_type = Ship) if ship.owner == player ]
                connected = (player.can_generate_wormholes() or
                             from_hex.wormholes[(neighbour_index - from_hex.rotation + 3) % 6] == 1)
                if connected and len(player_influence) + len(player_ships) > 0:
                    result.append(from_hex_coords)
        return result

    def get_direction(self, from_hex_coords, to_hex_coords):
        for neighbour_index in xrange(len(self.neighbours)):
            delta = self.neighbours[neighbour_index]
            if from_hex_coords[0] + delta[0] == to_hex_coords[0] and from_hex_coords[1] + delta[1] == to_hex_coords[1]:
                return neighbour_index
        return None

    def has_wormhole_connection(self, from_hex_coords, to_hex_coords, player = None):
        direction = self.get_direction(from_hex_coords, to_hex_coords)
        from_hex = self.hex_grid[from_hex_coords]
        to_hex = self.hex_grid[to_hex_coords]
        from_wormhole = from_hex.wormholes[(direction - from_hex.rotation) % 6]
        to_wormhole = to_hex.wormholes[(direction - to_hex.rotation + 3) % 6]
        generator = 1 if player is not None and player.can_generate_wormholes() else 0
        return from_wormhole + to_wormhole + generator >= 2

class PlayerBoard(Zone):
    def __init__(self, owner):
        self.owner = owner
        self.blueprints = BlueprintBoard(owner)
        self.resource_track = ResourceTrack(owner)
        self.population_track = PopulationTrack(owner)
        self.population_cemetery = PopulationCemetery(owner)
        self.influence_track = InfluenceTrack(owner)
        self.action_board = ActionBoard(owner)
        self.technology_track = TechnologyTrack(owner)
        self.faction = owner.faction
    
class ResourceSlot(Zone):
    """A slot for a population cube."""
    def __init__(self, owner = None, resource_type = None, advanced = False):
        """If resource type is not given or None, the slot will be wild."""
        super(ResourceSlot, self).__init__(owner)
        self.resource_type = resource_type
        self.advanced = advanced
        
    def isEmpty(self):
        """Return True if no population cubes, False otherwise."""
        return not len(self.components)
    
    def isAllowed(self, player):
        """check if a player has the technology needed to exploit the slot."""
        if not self.advanced:
            return True
        if self.resource_type == 'money':
            return player.personal_board.technology_track.contains('advanced economy')
        if self.resource_type == 'science':
            return player.personal_board.technology_track.contains('advanced labs')
        if self.resource_type == 'material':
            return player.personal_board.technology_track.contains('advanced mining')
    
class Sector(Zone):
    """Represents a non-empty hex from the board"""
    def __init__(self, sector_tile):
        super(Sector, self).__init__(sector_tile)
        self.name = sector_tile.name
        self.id = sector_tile.id
        self.victory_points = sector_tile.victory_points
        self.artifact = sector_tile.artifact
        self.wormholes = sector_tile.wormholes
        self.rotation = 0 #define the orientation for wormholes
        
    def __str__(self):
        return 'Sector ' + self.id + ': ' + self.name
    
    def rotate(self, n = 1):
        """Rotate the sector n * 60 degrees clockwise. Default is 60."""
        self.rotation += n
        self.rotation %= 6

    def add(self, component, **kwargs):
        super(Sector, self).add(component, **kwargs)
        if isinstance(component, InfluenceDisc):
            if self.get_components(component_type = DiscoveryTile):
                discovery = self.take(component_type = DiscoveryTile)
                print "TODO pick up discovery tile", discovery.__dict__

class DrawPile(Zone):
    def __init__(self, components):
        super(DrawPile, self).__init__()
        self.content = components
        self.discard_pile = DiscardPile()
        self.shuffle()
        
    def draw(self):
        """
        Return the first item from the pile, removing the item from the pile.
        Return None if the drawpile was empty.
        """
        try :
            item = self.content.pop(0)
        except:
            return None
        #re-shuffle the discard pile to create a new drawpile if the last item was drawn
        if len(self.content) == 0 and len(self.discard_pile.content) != 0:
            self.content.extend(self.discard_pile.content)
            self.discard_pile.content = []
            self.shuffle()
        return item

    def shuffle(self):
        random.shuffle(self.content)

    def get_components(self):
        return len(self.content)
        

class DiscardPile(Zone):
    def __init__(self):
        super(DiscardPile, self).__init__()
        self.content = []

    def add(self, item):
        """Add an item in the discard pile."""
        self.content.append(item)
        
    def pop(self):
        return self.content.pop()

class Bag(Zone):
    def __init__(self, components):
        super(Bag, self).__init__()
        self.content = components
        self.shuffle()

    def draw(self):
        try:
            item = random.choice(self.content)
            self.remove(item)
            return item
        except:
            return None

    def shuffle(self):
        random.shuffle(self.content)

class BlueprintBoard(Zone):
    def __init__(self, owner):
        super(BlueprintBoard, self).__init__(owner)
        self.base_stats = {}
        self.ship_blueprints = {}
        self.stats = Set(('initiative', 'movement', 'computer', 'shield', 'hull', 'cannon1', 'cannon2', 'cannon4', 'missile2', 'energy'))
        for unit in owner.faction.blueprints:
            self.base_stats[unit] = {}
            for stat in owner.faction.blueprints[unit]:
                self.base_stats[unit][stat] = owner.faction.blueprints[unit][stat]
                if stat != 'default':
                    self.stats.add(stat)
            if 'default' in self.base_stats[unit]:
                self.ship_blueprints[unit] = [None for dummy in range(len(self.base_stats[unit]['default']))]

            
    def get_stats(self, ship_name):
        """Calculate the blueprint statistics for one particular ship type."""
        result = {}
        for stat in self.stats:
            result[stat] = self.base_stats[ship_name][stat] if stat in self.base_stats[ship_name] else 0
        ship_parts = self.get_ship_parts(ship_name)
        for sp in ship_parts:
            result['initiative'] += sp.initiative
            result['movement'] += sp.movement
            result['computer'] += sp.computer
            result['shield'] += sp.shield
            result['hull'] += sp.hull            
            if sp.missile:
                result['missile2'] += sp.n_dice
            elif sp.hits > 0:
                result['cannon' + str(sp.hits)] += sp.n_dice            
            result['energy'] += sp.energy
            
        return result
            
    def get_ship_parts(self, ship_name):
        """Get a list of all the active ship parts"""
        ship_parts = []
        for ship_part_tile_default, ship_part_tile in zip(self.base_stats[ship_name]['default'], 
                                                          self.ship_blueprints[ship_name]):
            if ship_part_tile is None:
                if ship_part_tile_default != 'Missing' and ship_part_tile_default != 'Empty':
                    sp = shipparts.ship_parts[ship_part_tile_default]
                else:
                    continue
            elif ship_part_tile_default != 'Missing':
                sp = ship_part_tile
            ship_parts.append(sp)
        return ship_parts        

class ResourceTrack(Zone):
    def __init__(self, owner):
        super(ResourceTrack, self).__init__(owner)
        self.money = owner.faction.starting_money
        self.science = owner.faction.starting_science
        self.material = owner.faction.starting_material
        
class PopulationTrack(Zone):
    def __init__(self, owner):
        #super(PopulationTrack, self).__init__(owner)
        self.owner = owner
        self.zones = {}
        for resource_type in ['money', 'science', 'material']:
            self.zones[resource_type] = PopulationResourceTrack(owner, resource_type)
            
    def add(self, population_cube, resource_type, **kwargs):
        self.zones[resource_type].add(population_cube)
        
    def take(self, resource_type, **kwargs):
        return self.zones[resource_type].take()
    
    def get_zones(self):
        return self.zones
        
class PopulationResourceTrack(Zone):
    def __init__(self, owner, resource_type):
        super(PopulationResourceTrack, self).__init__(owner)
        self.resource_type = resource_type

class PopulationCemetery(Zone):
    def __init__(self, owner):
        super(PopulationCemetery, self).__init__(owner)
        self.population_cemetery = {
            'money':[],
            'science':[],
            'material':[]
        }

class InfluenceTrack(Zone):
    pass

class ActionBoard(Zone):
    action_names = ('Explore', 'Influence', 'Research', 'Upgrade', 'Build', 'Move')
    
    def __init__(self, owner):
        super(ActionBoard, self).__init__(owner)
        self.places = {}
        for action in self.action_names:
            self.places[action] = Zone(owner)

    def add(self, action, component):
        self.places[action].add(component)
        
    def take(self, action, component = None, component_type = None):
        return self.places[action].take(component = component, component_type = component_type)
    
    def get_components(self, action, component_type = None):
        return self.places[action].get_components(component_type = component_type)

class TechnologyTrack(Zone):
    def __init__(self, owner):
        super(TechnologyTrack, self).__init__(owner)
        self.technologies = {
            'military':[],
            'grid':[],
            'nano':[]
        }
        starting_technologies = owner.faction.starting_technologies
        for tech in starting_technologies:
            self.technologies[tech.category].append(tech)
            
    def contains(self, name):
        """Return True if the technology track contains the named technology tile, False otherwise"""
        for techs in self.technologies.values():
            if name in [t.name for t in techs]:
                return True
        return False

class ReputationTrack(Zone):
    def __init__(self, owner):
        super(ReputationTrack, self).__init__(owner)
        self.track = {
            'diplomacy':[],
            'reputation':[]
        }
        self.reputation_max = owner.faction.reputation_only + owner.faction.reputation_diplomacy
        self.diplomacy_max = owner.faction.diplomacy_only + owner.faction.reputation_diplomacy
        self.tile_max = owner.faction.diplomacy_only + owner.faction.reputation_diplomacy + owner.faction.reputation_diplomacy

    def add(self, component):
        """
        Add a reputation tile or an ambassador to the track if there is space
        available.
        """
        if len(self.track['reputation']) + len(self.track['diplomacy']) < self.tile_max:
            if isinstance(component, cp.ReputationTile):
                if len(self.track['reputation']) < self.reputation_max:
                    self.track['reputation'].append(component)
            elif isinstance(component, cp.AmbassadorTile):
                if len(self.track['diplomacy']) < self.diplomacy_max:
                    self.track['diplomacy'].append(component)

    def is_diplomacy_full(self):
        """Return true if there is no more room for diplomacy components."""
        return (len(self.track['reputation']) + len(self.track['diplomacy']) >= self.tile_max or
                len(self.track['diplomacy']) >= self.diplomacy_max)

    def is_reputation_full(self):
        """Return true if there is no more room for reputation components."""
        return (len(self.track['reputation']) + len(self.track['diplomacy']) >= self.tile_max or
                len(self.track['reputation']) >= self.reputation_max)

    def remove(self, component):
        """Remove a component from the reputation track."""
        if isinstance(component, cp.AmbassadorTile):
            self.track['diplomacy'].remove(component)
        else:
            self.track['reputation'].remove(component)

    def get_components(self):
        return self.track

    
class PersonalSupply(Zone):
    """
    The personal supply is meant to contain all the components owned by a player
    that are not yet on the board nor on the player board. Components like
    ambassadors, ships, spare influence discs and colony ships are by default
    in this zone at the start of the game.
    """
    def take(self, component = None, component_type = None):
        if component is None and component_type is None:
            return self.components.pop()        
        if component_type is not None:
            #print [comp for comp in self.components if comp.type == component_type]
            component = [comp for comp in self.components if isinstance(comp, component_type)][0]
        self.components.remove(component)
        return component
