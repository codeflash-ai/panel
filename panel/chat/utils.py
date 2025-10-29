from __future__ import annotations

import re

from collections.abc import Iterable
from io import BytesIO
from textwrap import indent
from types import FunctionType
from typing import Any, Union

import param

from panel.pane import HTML, Image

from ..io.resources import CDN_DIST
from ..pane.image import ImageBase
from ..viewable import Viewable

_ALPHA_NUMERIC_REGEX = re.compile(r"\W+")

Avatar = Union[str, BytesIO, bytes, ImageBase]
AvatarDict = dict[str, Avatar]


def to_alpha_numeric(user: str) -> str:
    """
    Convert the user name to an alpha numeric string,
    removing all non-alphanumeric characters.
    """
    return _ALPHA_NUMERIC_REGEX.sub("", user).lower()


def avatar_lookup(
    user: str,
    avatar: Any,
    avatars: dict[str, Any],
    default_avatars: dict[str, Any],
) -> Avatar:
    """
    Lookup the avatar for the user.
    """
    alpha_numeric_key = to_alpha_numeric(user)
    # always use the default first
    updated_avatars = default_avatars.copy()
    # update with the user input
    updated_avatars.update(avatars)
    # correct the keys to be alpha numeric
    updated_avatars = {to_alpha_numeric(key): value for key, value in updated_avatars.items()}

    # now lookup the avatar
    avatar = updated_avatars.get(alpha_numeric_key, avatar)
    if isinstance(avatar, FunctionType):
        avatar = avatar()
    if isinstance(avatar, str):
        avatar = avatar.format(dist_path=CDN_DIST)
    return avatar


def build_avatar_pane(avatar: Any, css_classes: list[str], width: int = 15, height: int = 15) -> Image | HTML:
    avatar_params = {
        "css_classes": css_classes,
        "width": width,
        "height": height,
    }
    if isinstance(avatar, Viewable):
        avatar_pane = avatar
        avatar_params["css_classes"] = avatar_params.get("css_classes", []) + avatar_pane.css_classes
        avatar_pane.param.update(avatar_params)
    elif not isinstance(avatar, (BytesIO, bytes)) and len(avatar) == 1:
        # single character
        avatar_pane = HTML(avatar, **avatar_params)
    else:
        try:
            avatar_pane = Image(avatar, **avatar_params)
        except ValueError:
            # likely an emoji
            avatar_pane = HTML(avatar, **avatar_params)
    return avatar_pane


def stream_to(obj, token: str, replace: bool = False, object_panel: Viewable | None = None):
    """
    Updates the message with the new token traversing the object to
    allow updating nested objects. When traversing a nested Panel
    the last object that supports rendering strings is updated, e.g.
    in a layout of `Column(Markdown(...), Image(...))` the Markdown
    pane is updated.

    Parameters
    ----------
    token: str
        The token to stream to the text pane.
    replace: bool (default=False)
        Whether to replace the existing text.
    """
    i = -1
    parent_panel = None
    attr = "object"
    if obj is None:
        obj = ""

    while not isinstance(obj, str) or isinstance(object_panel, ImageBase):
        object_panel = obj
        if hasattr(obj, "objects"):
            parent_panel = obj
            attr = "objects"
            obj = obj.objects[i]
            i = -1
        elif hasattr(obj, "object"):
            attr = "object"
            obj = obj.object
        elif hasattr(obj, "value"):
            attr = "value"
            obj = obj.value
        elif parent_panel is not None:
            obj = parent_panel
            parent_panel = None
            i -= 1
    contents = token if replace else obj + token
    setattr(object_panel, attr, contents)
    return object_panel


def get_obj_label(obj):
    """
    Get the label for the object; defaults to specified object name;
    if unspecified, defaults to the type name.
    """
    # Small optimization: avoid attribute lookup when possible
    label = getattr(obj, "name", "")
    type_name = type(obj).__name__
    # If the name is just type + ID, simply use type
    # e.g. Column10241 -> Column
    if not label or label.startswith(type_name):
        return type_name
    return label


def serialize_recursively(
    obj: Any,
    prefix_with_viewable_label: bool = True,
    prefix_with_container_label: bool = True,
) -> str:
    """
    Recursively serialize the object to a string.
    """

    # Fast path: avoid repeated type checks for common objects
    # Only check for string once, and handle it up front
    # This also helps avoid repeated isinstance checks in large iterables
    if isinstance(obj, str):
        return obj

    if isinstance(obj, Iterable):
        # Defensive: exclude str, which was already handled above
        content = []
        serialize = serialize_recursively  # localize for faster access
        for o in obj:
            content.append(
                serialize(
                    o,
                    prefix_with_viewable_label=prefix_with_viewable_label,
                    prefix_with_container_label=prefix_with_container_label,
                )
            )
        content_tuple = tuple(content)
        if prefix_with_container_label:
            get_label = get_obj_label  # localize for faster access
            obj_label = get_label(obj)
            if len(content_tuple) == 1:
                return f"{obj_label}({content_tuple[0]})"
            else:
                indented_content = indent(",\n".join(content_tuple), prefix=" " * 4)
                return f"{obj_label}(\n{indented_content}\n)"
        else:
            return f"({', '.join(content_tuple)})"

    # Now handle single objects.
    # Resolve value or object attributes with a quick lookup
    # Prioritize 'value' first, then 'object'
    string = obj
    if hasattr(obj, "value"):
        string = obj.value
    elif hasattr(obj, "object"):
        string = obj.object

    # Optimize: direct checking against BytesIO then decode
    if isinstance(string, BytesIO) or hasattr(string, "decode"):
        param.main.param.warning(f"Serializing byte-like objects are not supported yet; using the label of the object as a placeholder for {obj}")
        return get_obj_label(obj)

    if prefix_with_viewable_label and isinstance(obj, Viewable):
        label = get_obj_label(obj)
        string = f"{label}={string!r}"

    # Avoid redundant conversion if string is already str
    if not isinstance(string, str):
        string = str(string)

    return string
