"""Geopolitical simulation game in a single Python file.

This script implements a simplified turn‑based geopolitical
simulation with a graphical interface using Pygame. The world
consists of four countries drawn on a grid; each country has its own
economy, resources, and policies. As the player you select one
country to control and make policy decisions such as adjusting tax
rates, tariffs, investing in infrastructure, and imposing sanctions.
The remaining countries are controlled by simple AI routines.

Run this file with Python to start the game. You must have the
`pygame` library installed (see the documentation at
https://www.pygame.org/wiki/GettingStarted for installation
instructions).

Usage
-----

```
python geopolitical_sim.py
```

Controls
--------

* Click a country on the map to select it. The first country you
  select becomes your player country.
* Press number keys (1–6) to enact policies for your country:

    1 – Lower taxes (reduces tax rate by 2 percentage points)
    2 – Raise taxes (increases tax rate by 2 percentage points)
    3 – Lower tariffs (reduces tariff rate by 5 percentage points)
    4 – Raise tariffs (increases tariff rate by 5 percentage points)
    5 – Invest in infrastructure (costs resources, boosts growth)
    6 – Sanction another country (press 6 then click a target)

After each policy choice, the AI countries make their choices and the
world updates. Watch how your policies affect GDP, resources, and
international relations!
"""

from __future__ import annotations

import random
import pygame
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Set, Optional


###############################################################################
# Model classes: Country and World
###############################################################################

@dataclass
class Country:
    """Represents a country in the simulation.

    Each country has a polygon shape for drawing, base colour, resource
    stockpiles, economic indicators, and policy settings. Countries can
    update their economy, produce resources, and apply policy actions.

    Parameters
    ----------
    name : str
        Name of the country.
    polygon : list of (x, y)
        Coordinates defining the shape of the country on the map.
    color : (r, g, b)
        Base RGB colour used for rendering the country.
    resources : dict[str, float]
        Quantities of resources (oil, minerals, agriculture).
    gdp : float
        Gross domestic product representing economic size.
    growth_rate : float
        Baseline GDP growth per turn.
    population : float
        Population in millions.
    tax_rate : float
        Fraction of GDP collected as taxes (0–1).
    tariff_rate : float
        Fraction applied to imports (0–1).
    sanctions : set[str]
        Countries that this country has sanctioned.
    """

    name: str
    polygon: List[Tuple[int, int]]
    color: Tuple[int, int, int]
    resources: Dict[str, float] = field(default_factory=lambda: {"oil": 0.0, "minerals": 0.0, "agriculture": 0.0})
    gdp: float = 100.0
    growth_rate: float = 0.02
    population: float = 10.0
    tax_rate: float = 0.2
    tariff_rate: float = 0.1
    sanctions: Set[str] = field(default_factory=set)
    new_sanctions: Set[str] = field(default_factory=set, init=False)

    def update_economy(self) -> None:
        """Update GDP based on growth rate, tax rate, and randomness."""
        tax_penalty = self.tax_rate * 0.5
        effective_growth = max(self.growth_rate - tax_penalty, -0.05)
        fluctuation = random.uniform(-0.01, 0.01)
        delta = self.gdp * (effective_growth + fluctuation)
        self.gdp = max(self.gdp + delta, 0.0)

    def produce_resources(self) -> None:
        """Produce resources based on population and existing stockpiles."""
        for key in self.resources:
            base_production = self.population * 0.1
            reserve_bonus = self.resources[key] * 0.02
            self.resources[key] += base_production + reserve_bonus

    def apply_policy(self, policy: str, target: Optional["Country"] = None) -> None:
        """Apply a policy action to the country.

        Supported policies:

        ``lower_taxes`` – decrease tax rate by 0.02
        ``raise_taxes`` – increase tax rate by 0.02
        ``lower_tariffs`` – decrease tariff rate by 0.05
        ``raise_tariffs`` – increase tariff rate by 0.05
        ``invest_in_infrastructure`` – spend resources to boost growth_rate
        ``sanction`` – add target to sanctions (trade halted)
        """
        if policy == "lower_taxes":
            self.tax_rate = max(self.tax_rate - 0.02, 0.0)
        elif policy == "raise_taxes":
            self.tax_rate = min(self.tax_rate + 0.02, 0.5)
        elif policy == "lower_tariffs":
            self.tariff_rate = max(self.tariff_rate - 0.05, 0.0)
        elif policy == "raise_tariffs":
            self.tariff_rate = min(self.tariff_rate + 0.05, 1.0)
        elif policy == "invest_in_infrastructure":
            can_invest = all(value >= 10 for value in self.resources.values())
            if can_invest:
                for key in self.resources:
                    self.resources[key] -= 10
                self.growth_rate += 0.005
        elif policy == "sanction" and target is not None:
            if target.name not in self.sanctions:
                self.sanctions.add(target.name)
                self.new_sanctions.add(target.name)

    def reset_temp(self) -> None:
        """Reset temporary flags such as new sanctions."""
        self.new_sanctions.clear()


@dataclass
class World:
    """Container class managing all countries and trade interactions."""

    countries: List[Country] = field(default_factory=list)

    def update(self) -> None:
        """Perform a single turn update: produce resources, update
        economies, resolve trade, and clear temporary flags."""
        for c in self.countries:
            c.produce_resources()
        for c in self.countries:
            c.update_economy()
        self.resolve_trade()
        for c in self.countries:
            c.reset_temp()

    def resolve_trade(self) -> None:
        """Trade resources to meet consumption needs.

        Countries consume resources at a rate of ``population * 0.2``
        units per turn. Surplus is exported proportionally to other
        countries' deficits. Tariffs reduce imports; sanctions
        eliminate trade between specific pairs.
        """
        if not self.countries:
            return
        resource_types = list(self.countries[0].resources.keys())
        for resource in resource_types:
            demands: Dict[str, float] = {}
            supplies: Dict[str, float] = {}
            total_demand = 0.0
            total_supply = 0.0
            for c in self.countries:
                consumption = c.population * 0.2
                available = c.resources.get(resource, 0.0)
                if available < consumption:
                    demands[c.name] = consumption - available
                    total_demand += consumption - available
                    supplies[c.name] = 0.0
                else:
                    supplies[c.name] = available - consumption
                    total_supply += available - consumption
                    demands[c.name] = 0.0
            if total_supply <= 0 or total_demand <= 0:
                continue
            for importer in self.countries:
                demand = demands[importer.name]
                if demand <= 0:
                    continue
                for exporter in self.countries:
                    supply = supplies[exporter.name]
                    if supply <= 0:
                        continue
                    if importer.name in exporter.sanctions or exporter.name in importer.sanctions:
                        continue
                    share = supply / total_supply
                    volume = share * demand
                    volume_after_tariff = volume * (1.0 - importer.tariff_rate)
                    exporter.resources[resource] -= volume
                    importer.resources[resource] += volume_after_tariff


###############################################################################
# Game class handling UI and game loop
###############################################################################

class Game:
    """Encapsulate the Pygame window and user interaction."""

    def __init__(self) -> None:
        self.width = 900
        self.height = 600
        self.map_width = 600
        self.panel_width = self.width - self.map_width
        pygame.init()
        pygame.display.set_caption("Geopolitical Simulator")
        self.screen = pygame.display.set_mode((self.width, self.height))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 14)
        self.title_font = pygame.font.SysFont("arial", 20, bold=True)
        self.world = self._create_world()
        self.player_country: Optional[Country] = None
        self.selected_country: Optional[Country] = None
        self.awaiting_sanction_target: bool = False
        self.turn_count: int = 1
        self.message: str = "Click a country to play."  # Status message

    def _create_world(self) -> World:
        countries: List[Country] = []
        poly_coords = [
            [(0, 0), (300, 0), (300, 300), (0, 300)],
            [(300, 0), (600, 0), (600, 300), (300, 300)],
            [(0, 300), (300, 300), (300, 600), (0, 600)],
            [(300, 300), (600, 300), (600, 600), (300, 600)]
        ]
        names = ["Albia", "Borovia", "Cyrenia", "Demeria"]
        base_colours = [(200, 90, 90), (90, 200, 90), (90, 90, 200), (200, 200, 90)]
        resource_sets = [
            {"oil": 50.0, "minerals": 20.0, "agriculture": 10.0},
            {"oil": 10.0, "minerals": 60.0, "agriculture": 20.0},
            {"oil": 20.0, "minerals": 10.0, "agriculture": 70.0},
            {"oil": 30.0, "minerals": 30.0, "agriculture": 30.0},
        ]
        for idx in range(4):
            c = Country(
                name=names[idx],
                polygon=poly_coords[idx],
                color=base_colours[idx],
                resources=resource_sets[idx].copy(),
                gdp=100.0 + idx * 50.0,
                growth_rate=0.02 + idx * 0.005,
                population=8.0 + idx * 2.0,
                tax_rate=0.15,
                tariff_rate=0.1,
            )
            countries.append(c)
        return World(countries)

    def draw_map(self) -> None:
        for country in self.world.countries:
            total_resources = sum(country.resources.values())
            brightness = min(1.0, total_resources / 300.0)
            r, g, b = country.color
            tinted = (int(r * brightness), int(g * brightness), int(b * brightness))
            scaled_poly = [(int(x), int(y)) for x, y in country.polygon]
            pygame.draw.polygon(self.screen, tinted, scaled_poly)
            if country is self.selected_country:
                pygame.draw.polygon(self.screen, (255, 255, 255), scaled_poly, 3)
        pygame.draw.rect(self.screen, (255, 255, 255), (0, 0, self.map_width, self.height), 2)

    def draw_panel(self) -> None:
        x_offset = self.map_width
        panel_rect = (x_offset, 0, self.panel_width, self.height)
        pygame.draw.rect(self.screen, (30, 30, 30), panel_rect)
        title_surf = self.title_font.render(f"Turn {self.turn_count}", True, (255, 255, 255))
        self.screen.blit(title_surf, (x_offset + 10, 10))
        msg_surf = self.font.render(self.message, True, (200, 200, 200))
        self.screen.blit(msg_surf, (x_offset + 10, 40))
        y = 70
        if self.selected_country:
            c = self.selected_country
            lines = [
                f"Country: {c.name}",
                f"GDP: {c.gdp:.1f}",
                f"Population: {c.population:.1f}M",
                f"Tax rate: {c.tax_rate*100:.0f}%",
                f"Tariff rate: {c.tariff_rate*100:.0f}%",
                f"Resources:",
                f"  Oil: {c.resources['oil']:.1f}",
                f"  Minerals: {c.resources['minerals']:.1f}",
                f"  Agriculture: {c.resources['agriculture']:.1f}",
            ]
            for line in lines:
                surf = self.font.render(line, True, (255, 255, 255))
                self.screen.blit(surf, (x_offset + 10, y))
                y += 18
        y = self.height - 150
        controls = [
            "Controls:",
            "1- Lower taxes", 
            "2- Raise taxes", 
            "3- Lower tariffs", 
            "4- Raise tariffs", 
            "5- Invest in infrastructure", 
            "6- Sanction country",
        ]
        for line in controls:
            surf = self.font.render(line, True, (200, 200, 200))
            self.screen.blit(surf, (x_offset + 10, y))
            y += 18

    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    self.handle_click(event.pos)
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
            self.screen.fill((0, 0, 0))
            self.draw_map()
            self.draw_panel()
            pygame.display.flip()
            self.clock.tick(30)
        pygame.quit()

    def handle_click(self, pos: Tuple[int, int]) -> None:
        x, y = pos
        if x < self.map_width:
            clicked_country = self.get_country_at((x, y))
            if self.awaiting_sanction_target and clicked_country and self.player_country:
                if clicked_country is not self.player_country:
                    self.player_country.apply_policy("sanction", clicked_country)
                    self.message = f"You sanctioned {clicked_country.name}."
                    self.awaiting_sanction_target = False
                    self.advance_turn()
                else:
                    self.message = "Cannot sanction your own country."
                    self.awaiting_sanction_target = False
            else:
                self.selected_country = clicked_country
                if not self.player_country and clicked_country:
                    self.player_country = clicked_country
                    self.message = f"You are now playing as {clicked_country.name}."
                else:
                    self.message = f"Selected {clicked_country.name}" if clicked_country else ""

    def handle_key(self, key: int) -> None:
        if not self.player_country or not self.selected_country:
            return
        if self.selected_country is not self.player_country:
            return
        if self.awaiting_sanction_target:
            return
        if key == pygame.K_1:
            self.player_country.apply_policy("lower_taxes")
            self.message = "Lowered taxes."
            self.advance_turn()
        elif key == pygame.K_2:
            self.player_country.apply_policy("raise_taxes")
            self.message = "Raised taxes."
            self.advance_turn()
        elif key == pygame.K_3:
            self.player_country.apply_policy("lower_tariffs")
            self.message = "Lowered tariffs."
            self.advance_turn()
        elif key == pygame.K_4:
            self.player_country.apply_policy("raise_tariffs")
            self.message = "Raised tariffs."
            self.advance_turn()
        elif key == pygame.K_5:
            self.player_country.apply_policy("invest_in_infrastructure")
            self.message = "Invested in infrastructure."
            self.advance_turn()
        elif key == pygame.K_6:
            self.awaiting_sanction_target = True
            self.message = "Click a country to sanction."

    def get_country_at(self, pos: Tuple[int, int]) -> Optional[Country]:
        x, y = pos
        for c in self.world.countries:
            xs = [p[0] for p in c.polygon]
            ys = [p[1] for p in c.polygon]
            if not (min(xs) <= x <= max(xs) and min(ys) <= y <= max(ys)):
                continue
            inside = False
            n = len(c.polygon)
            j = n - 1
            for i in range(n):
                xi, yi = c.polygon[i]
                xj, yj = c.polygon[j]
                if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-6) + xi):
                    inside = not inside
                j = i
            if inside:
                return c
        return None

    def ai_actions(self) -> None:
        for c in self.world.countries:
            if c is self.player_country:
                continue
            policy = random.choice([
                "lower_taxes", "raise_taxes", "lower_tariffs", "raise_tariffs",
                "invest_in_infrastructure", None
            ])
            if policy:
                if policy == "sanction":
                    targets = [cc for cc in self.world.countries if cc is not c]
                    if targets:
                        target = random.choice(targets)
                        c.apply_policy("sanction", target)
                else:
                    c.apply_policy(policy)

    def advance_turn(self) -> None:
        self.ai_actions()
        self.world.update()
        self.turn_count += 1
        sanctions_messages: List[str] = []
        for c in self.world.countries:
            for s in c.new_sanctions:
                sanctions_messages.append(f"{c.name} sanctioned {s}")
        if sanctions_messages:
            self.message = ", ".join(sanctions_messages)


if __name__ == "__main__":
    game = Game()
    game.run()
