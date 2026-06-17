"""
Generic message queue for ScrollKit display applications.
Manages a queue of display operations with parameters and delays.
Copyright 2024 3DUPFitters LLC
"""
import asyncio

from scrollkit.utils.error_handler import ErrorHandler

# Initialize logger
logger = ErrorHandler("error_log")


class MessageQueue:
    """
    Manages a queue of display operations.

    Each message consists of:
    - A callable (typically a display method)
    - Parameters for that callable
    - A delay after execution

    Messages are shown in order and the queue loops continuously.
    """

    def __init__(self, display, default_delay=4):
        """
        Initialize the message queue.

        Args:
            display: The display instance
            default_delay: Default delay between messages in seconds
        """
        self.display = display
        self.default_delay = default_delay
        self.init()

    def init(self):
        """Initialize (or clear) the message queue."""
        self.func_queue = []
        self.param_queue = []
        self.delay_queue = []
        self.index = 0
        self.has_completed_cycle = False
        # Stop any current display operation if the display supports it
        if hasattr(self.display, 'stop_current_operation'):
            self.display.stop_current_operation()

    async def add_message(self, func, params, delay=None):
        """
        Add a generic message to the queue.

        Args:
            func: The callable to invoke
            params: Single parameter or tuple of parameters to pass
            delay: Delay after execution (uses default_delay if None)
        """
        self.func_queue.append(func)
        self.param_queue.append(params)
        self.delay_queue.append(delay if delay is not None else self.default_delay)

    async def show(self):
        """Show the next message in the queue."""
        if not self.func_queue:
            return

        try:
            # Bounds check to prevent index errors during queue rebuilds
            if (self.index >= len(self.func_queue) or
                self.index >= len(self.param_queue) or
                self.index >= len(self.delay_queue)):
                self.index = 0
                return

            # Handle parameters - if tuple, unpack; otherwise pass as single param
            params = self.param_queue[self.index]
            if isinstance(params, tuple):
                await asyncio.create_task(self.func_queue[self.index](*params))
            else:
                await asyncio.create_task(self.func_queue[self.index](params))

            await asyncio.sleep(self.delay_queue[self.index])
            self.index += 1

            if self.index >= len(self.func_queue):
                self.index = 0
                self.has_completed_cycle = True

        except IndexError:
            # Queue was modified during execution - reset and continue
            self.index = 0
