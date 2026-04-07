from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AppState:
    plan: List[str] = field(default_factory=list)
    conversation_history: List[dict] = field(default_factory=list)

    # Robot execution state
    drawer_open: bool = False
    holding: Optional[str] = None
    red_in_drawer: bool = False
    green_in_drawer: bool = False
    yellow_in_drawer: bool = False
    blue_in_drawer: bool = False

    def reset_robot_state(self):
        self.drawer_open = False
        self.holding = None
        self.red_in_drawer = False
        self.green_in_drawer = False
        self.yellow_in_drawer = False
        self.blue_in_drawer = False

    def is_complete(self) -> bool:
        return self.red_in_drawer and self.green_in_drawer and self.yellow_in_drawer and self.blue_in_drawer


state = AppState()
