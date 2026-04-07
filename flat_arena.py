"""
FlatBinsArena — BinsArena with all walls/dividers removed from both bins.
Only the flat base surface remains, so it looks like two open flat tables.
"""

from robosuite.models.arenas.bins_arena import BinsArena


class FlatBinsArena(BinsArena):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._strip_walls(self.bin1_body)
        self._strip_walls(self.bin2_body)

    def _strip_walls(self, body):
        """Remove all geoms except the two base geoms (collision + visual floor)."""
        geoms = body.findall("geom")
        # First two geoms are the base floor (collision + visual) — keep them.
        # Everything after that is walls, dividers, legs visual — remove.
        for geom in geoms[2:]:
            body.remove(geom)
