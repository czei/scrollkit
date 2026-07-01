"""
Contract: Display Content Queue
Public API for display content management (ContentQueue + DisplayContent).
"""


class DisplayContentContract:
    """
    A unit of content to be shown on the display.
    Tracks its own duration and elapsed time.
    """

    priority: int                  # Priority enum value
    duration: float                # seconds to display; None = indefinite

    def is_complete(self) -> bool:
        """True when elapsed >= duration (only if duration is set)."""
        raise NotImplementedError

    async def render(self, display) -> None:
        """Draw this content to the given display."""
        raise NotImplementedError


class ContentQueueContract:
    """
    Looping queue of DisplayContent items, cycled by the display loop.
    """

    def add(self, content) -> None:
        """Add content to the queue."""
        raise NotImplementedError

    def get_content_count(self) -> int:
        """Number of items currently queued."""
        raise NotImplementedError

    def clear(self) -> None:
        """Remove all queued content."""
        raise NotImplementedError

    async def get_current(self):
        """Return the content that should be shown this frame, advancing on completion."""
        raise NotImplementedError


# --- Contract tests ---

def test_static_text_is_display_content():
    from scrollkit.display.content import StaticText, DisplayContent
    content = StaticText("Hello", color=(255, 255, 255))
    assert isinstance(content, DisplayContent)


def test_scrolling_text_is_display_content():
    from scrollkit.display.content import ScrollingText, DisplayContent
    content = ScrollingText("Hello World", color=(0, 255, 0))
    assert isinstance(content, DisplayContent)


def test_content_is_not_complete_without_duration():
    """Content with no duration never expires."""
    from scrollkit.display.content import StaticText
    content = StaticText("Hello")
    # is_complete is a property (derived from elapsed vs duration)
    assert content.is_complete is False


def test_content_completes_after_duration():
    """Content reports complete after its duration elapses."""
    import time
    from scrollkit.display.content import StaticText
    content = StaticText("Hello", duration=0.01)
    time.sleep(0.02)
    content.update()  # optional per-frame tick hook
    assert content.is_complete is True


def test_content_default_priority_is_normal():
    """DisplayContent defaults to Priority.NORMAL, not a bare magic number."""
    from scrollkit.display.content import StaticText, Priority
    content = StaticText("Hello")
    assert content.priority == Priority.NORMAL


def test_queue_add_increments_count():
    from scrollkit.display.content import ContentQueue, StaticText

    queue = ContentQueue()
    queue.add(StaticText("a"))
    queue.add(StaticText("b"))
    assert queue.get_content_count() == 2


def test_queue_clear_empties_it():
    from scrollkit.display.content import ContentQueue, StaticText

    queue = ContentQueue()
    queue.add(StaticText("a"))
    queue.clear()
    assert queue.get_content_count() == 0
    assert queue.is_empty
