from dataclasses import dataclass, field

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
  max_copies: int = 3

# placeholder catalog until backend/data/army.db exists; numbers are made up
CATALOG = {unit.id: unit for unit in [
  Unit("intercessors", "Intercessor Squad", "Space Marines", 80, max_copies=6),
  Unit("captain", "Captain", "Space Marines", 80, max_copies=1),
  Unit("redemptor", "Redemptor Dreadnought", "Space Marines", 210),
  Unit("boyz", "Boyz", "Orks", 85, max_copies=6),
  Unit("warboss", "Warboss", "Orks", 65, max_copies=1),
]}

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

        self.points_limit = points_limit

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
        new_count = self.units.get(unit_id, 0) + count
        if new_count > unit.max_copies:
            raise ValueError(f"{unit.name} is limited to {unit.max_copies} per army.")
        if self.total_points + unit.points * count > self.points_limit:
            raise ValueError(f"Adding {unit.name} would exceed {self.points_limit} points.")
        self.units[unit_id] = new_count

    def remove_unit(self, unit_id):
        """Remove copies of a unit."""
        if self.units.get(unit_id, 0) > 1:
            self.units[unit_id] -= 1
        else:
            self.units.pop(unit_id, None)
