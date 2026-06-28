# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""ScrollKitApp render suspend/resume.

An app can pause queue rendering while it paints an off-queue status frame and
blocks on a fetch, without overriding prepare_display_content() or touching a
private flag. The queue is preserved (never blanked) and rendering always
resumes — even if the suspended block raises.
"""
from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import StaticText


class _App(ScrollKitApp):
    async def setup(self):
        pass


def _app_with_one_item():
    app = ScrollKitApp(enable_web=False)
    app.content_queue.add(StaticText("HI", x=0, y=12, color=0xFFFFFF))
    return app


async def test_prepare_returns_content_then_none_while_suspended():
    app = _app_with_one_item()
    assert await app.prepare_display_content() is not None      # normal
    app.suspend_render()
    assert app.render_suspended is True
    assert await app.prepare_display_content() is None          # skipped
    app.resume_render()
    assert app.render_suspended is False
    assert await app.prepare_display_content() is not None      # back


async def test_queue_items_preserved_while_suspended():
    app = _app_with_one_item()
    app.suspend_render()
    await app.prepare_display_content()
    # The point of suspend (vs clear): items survive, so no black screen on resume.
    assert not app.content_queue.is_empty
    assert app.content_queue.get_content_count() == 1


async def test_context_manager_suspends_and_resumes():
    app = _app_with_one_item()
    with app.suspended_render():
        assert app.render_suspended is True
        assert await app.prepare_display_content() is None
    assert app.render_suspended is False
    assert await app.prepare_display_content() is not None


async def test_context_manager_resumes_on_exception():
    app = _app_with_one_item()
    try:
        with app.suspended_render():
            raise RuntimeError("fetch blew up")
    except RuntimeError:
        pass
    # Must NOT be stuck suspended (that would blank the panel permanently).
    assert app.render_suspended is False
    assert await app.prepare_display_content() is not None


def test_default_is_not_suspended():
    """Existing apps/harness must be unaffected: default off."""
    app = ScrollKitApp(enable_web=False)
    assert app.render_suspended is False
