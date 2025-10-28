from typing import Any

from bokeh.core.properties import List, String
from bokeh.events import ModelEvent

from .layout import Column


class ScrollLatestEvent(ModelEvent):
    event_name = "scroll_latest_event"

    def __init__(self, model, rerender=False, scroll_limit=None):
        super().__init__(model=model)
        self.rerender = rerender
        self.scroll_limit = scroll_limit

    def event_values(self) -> dict[str, Any]:
        # Avoid an intermediate dict copy by updating in-place
        values = super().event_values()
        values["rerender"] = self.rerender
        values["scroll_limit"] = self.scroll_limit
        return values


class ScrollButtonClick(ModelEvent):
    event_name = "scroll_button_click"

    def __init__(self, model, data=None):
        self.data = data
        super().__init__(model=model)


class Feed(Column):
    visible_children = List(String())
