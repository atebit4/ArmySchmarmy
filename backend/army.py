from dataclasses import dataclass, field

import db

#Game sizes
POINTS_FORMATS = {
    1000: "Incursion",
    2000: "Strike Force",
    3000: "Onslaught"
}

@dataclass(frozen=True)
class Unit:
  id: str
  name: str
  faction: str
  points: int
  keywords: frozenset = frozenset()

# all buildable units from data/army.db; points are the base cost of the smallest unit size
CATALOG = {row["id"]: Unit(row["id"], row["name"], row["faction"], row["points"], frozenset(row["keywords"]))
           for row in db.load_units()}

# copies allowed per datasheet name, by points limit (core rules 25.03 Select Battle Size)
UNIT_LIMITS = db.load_unit_limits()
DOUBLED_LIMIT = {"BATTLELINE", "DEDICATED TRANSPORT"}

@dataclass
class Army:
    points_limit: int = 2000
    #unit id and number of copies
    units: dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.points_limit not in POINTS_FORMATS:
            raise ValueError(f"Points limit must be: {self.points_limit}.")

    @property
    def format_name(self):
        return POINTS_FORMATS[self.points_limit]

    def set_points_limit(self, points_limit: int):
        """Switch game size. Gives ValueError if army is over point limit."""
        if points_limit not in POINTS_FORMATS:
            raise ValueError(f"Points limit must be: {self.points_limit}.")
        if self.total_points > points_limit:
            raise ValueError(f"Points limit must not be greater than total points.")
        for unit_id in self.units:
            unit = CATALOG[unit_id]
            if self.copies_named(unit.name) > self.unit_limit(unit, points_limit):
                raise ValueError(f"{POINTS_FORMATS[points_limit]} allows only "
                                 f"{self.unit_limit(unit, points_limit)} {unit.name}; remove some first.")

        self.points_limit = points_limit

    def unit_limit(self, unit, points_limit=None):
        """Copies of a datasheet allowed at this battle size."""
        if "EPIC HERO" in unit.keywords:
            return 1
        points_limit = points_limit or self.points_limit
        # the rules list no 3000-point battle size, so Onslaught uses the largest size they do list
        limit = UNIT_LIMITS.get(points_limit, UNIT_LIMITS[max(UNIT_LIMITS)])
        return limit * 2 if DOUBLED_LIMIT & unit.keywords else limit

    def copies_named(self, name):
        # the limit is per datasheet name, so entries that share a name (e.g. two Gladiator Valiants) share it
        return sum(count for unit_id, count in self.units.items() if CATALOG[unit_id].name == name)

    @property
    def faction(self):
        return CATALOG[next(iter(self.units))].faction if self.units else None

    @property
    def total_points(self):
        return sum(CATALOG[unit_id].points * count for unit_id, count in self.units.items())

    def add_unit(self, unit_id, count = 1):
        """Add copies of a unit. Raise ValueError if the army becomes over point limit"""
        unit = CATALOG.get(unit_id)
        if unit is None:
            raise ValueError(f"Unit {unit_id} is not in CATALOG.")
        if count < 1:
            raise ValueError("Count must be over 1.")
        if self.faction and unit.faction != self.faction:
            raise ValueError(f"{unit.name} is {unit.faction}; this army is {self.faction}.")
        if self.copies_named(unit.name) + count > self.unit_limit(unit):
            raise ValueError(f"{unit.name} is limited to {self.unit_limit(unit)} per army in {self.format_name}.")
        if self.total_points + unit.points * count > self.points_limit:
            raise ValueError(f"Adding {unit.name} would exceed {self.points_limit} points.")
        self.units[unit_id] = self.units.get(unit_id, 0) + count

    def remove_unit(self, unit_id):
        """Remove copies of a unit."""
        if self.units.get(unit_id, 0) > 1:
            self.units[unit_id] -= 1
        else:
            self.units.pop(unit_id, None)
