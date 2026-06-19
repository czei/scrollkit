"""
Contract: Display Content Queue
Public API for priority-based display content management.
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


class DisplayQueueContract:
    """
    Priority-sorted queue of DisplayContent items.
    Higher priority items are shown before lower priority items.
    Items with duration expire automatically.
    """

    def add(self, content) -> bool:
        """
        Add content to the queue.
        Returns False if queue is full and content priority is too low to displace anything.
        """
        raise NotImplementedError

    def peek(self):
        """Return the highest-priority non-expired item without removing it."""
        raise NotImplementedError

    def pop(self):
        """Remove and return the highest-priority non-expired item."""
        raise NotImplementedError

    def expire(self) -> int:
        """Remove completed items. Returns count removed."""
        raise NotImplementedError

    def __len__(self) -> int:
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
    assert content.is_complete() is False


def test_content_completes_after_duration():
    """Content reports complete after its duration elapses."""
    import time
    from scrollkit.display.content import StaticText
    content = StaticText("Hello", duration=0.01)
    time.sleep(0.02)
    content.update()  # or update elapsed from loop
    assert content.is_complete() is True


def test_queue_respects_priority_order():
    """Higher priority items are returned first."""
    from scrollkit.display.queue import DisplayQueue
    from scrollkit.display.content import StaticText
    from scrollkit.display.strategy import Priority

    queue = DisplayQueue()
    low = StaticText("low", priority=Priority.LOW)
    high = StaticText("high", priority=Priority.HIGH)
    queue.add(low)
    queue.add(high)

    first = queue.pop()
    assert first.priority == Priority.HIGH


def test_queue_len():
    from scrollkit.display.queue import DisplayQueue
    from scrollkit.display.content import StaticText

    queue = DisplayQueue()
    queue.add(StaticText("a"))
    queue.add(StaticText("b"))
    assert len(queue) == 2


def test_queue_expire_removes_completed():
    """expire() removes items whose duration has elapsed."""
    import time
    from scrollkit.display.queue import DisplayQueue
    from scrollkit.display.content import StaticText

    queue = DisplayQueue()
    queue.add(StaticText("a", duration=0.01))
    time.sleep(0.02)
    removed = queue.expire()
    assert removed == 1
    assert len(queue) == 0
