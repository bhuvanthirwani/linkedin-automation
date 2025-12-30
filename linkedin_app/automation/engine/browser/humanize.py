"""
Human-like behavior patterns for browser automation.
"""

import time
import random
import math
from typing import List, Tuple

from playwright.sync_api import Page


class Humanizer:
    """
    Provides human-like behavior patterns for automation.
    """
    
    def __init__(self, seed: int = None):
        if seed:
            random.seed(seed)
    
    def random_delay(self, min_ms: int, max_ms: int) -> None:
        """Wait for a random duration between min and max milliseconds."""
        delay = random.randint(min_ms, max_ms)
        time.sleep(delay / 1000)
    
    def typing_delay(self) -> int:
        """Get a human-like typing delay in milliseconds."""
        # Average human types 40-60 WPM, roughly 100-200ms per character
        return random.randint(50, 150)
    
    def human_mouse_move(self, page: Page, target_x: float, target_y: float) -> None:
        """
        Move mouse to target position with human-like movement.
        Uses bezier curves for natural-looking paths.
        """
        # Get current mouse position (start from center if not available)
        try:
            current_pos = page.evaluate("""
                () => {
                    return {x: window.innerWidth / 2, y: window.innerHeight / 2};
                }
            """)
            start_x = current_pos.get("x", 960)
            start_y = current_pos.get("y", 540)
        except Exception:
            start_x, start_y = 960, 540
        
        # Generate bezier curve path
        path = self._generate_bezier_path(start_x, start_y, target_x, target_y)
        
        # Move along the path
        for point in path:
            page.mouse.move(point[0], point[1])
            time.sleep(random.randint(5, 15) / 1000)
    
    def _generate_bezier_path(
        self, 
        start_x: float, 
        start_y: float, 
        end_x: float, 
        end_y: float,
        num_points: int = 10
    ) -> List[Tuple[float, float]]:
        """Generate a bezier curve path between two points."""
        # Control point with some randomness
        control_x = (start_x + end_x) / 2 + random.randint(-50, 50)
        control_y = (start_y + end_y) / 2 + random.randint(-50, 50)
        
        path = []
        for i in range(num_points + 1):
            t = i / num_points
            
            # Quadratic bezier formula
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * control_x + t ** 2 * end_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * control_y + t ** 2 * end_y
            
            # Add small random jitter
            x += random.randint(-2, 2)
            y += random.randint(-2, 2)
            
            path.append((x, y))
        
        return path
    
    def human_scroll(self, page: Page, direction: str = "down") -> None:
        """Scroll with human-like behavior."""
        # Random scroll amount
        amount = random.randint(200, 500)
        if direction == "up":
            amount = -amount
        
        # Smooth scroll
        page.evaluate(f"""
            window.scrollBy({{
                top: {amount},
                behavior: 'smooth'
            }});
        """)
        
        # Random pause after scrolling
        self.random_delay(200, 500)
    
    def should_take_break(self, actions_performed: int) -> bool:
        """Determine if we should take a longer break."""
        # Take a break every 10-20 actions
        if actions_performed > 0:
            break_threshold = random.randint(10, 20)
            return actions_performed % break_threshold == 0
        return False
    
    def take_break(self) -> None:
        """Take a longer break to simulate human behavior."""
        # Break duration: 30-120 seconds
        duration = random.randint(30, 120)
        time.sleep(duration)
    
    def random_scroll_amount(self) -> int:
        """Get a random scroll amount in pixels."""
        return random.randint(200, 600)
    
    def should_scroll_up(self) -> bool:
        """Determine if we should occasionally scroll up."""
        # 15% chance to scroll up
        return random.random() < 0.15
    
    def simulate_reading(self, content_length: int) -> None:
        """
        Simulate reading content with appropriate delay.
        
        Args:
            content_length: Approximate length of content in characters.
        """
        # Average reading speed: 200-250 words per minute
        # Assuming 5 characters per word
        words = content_length / 5
        # 200 WPM = 3.33 words per second
        base_seconds = words / 3.33
        # Add some randomness
        variation = random.uniform(-0.2, 0.2)
        delay = base_seconds * (1 + variation)
        # Cap at reasonable limits
        delay = max(1, min(delay, 30))
        
        time.sleep(delay)
    
    def get_typing_mistake(self, char: str) -> str:
        """
        Get a typing mistake character (adjacent key).
        
        Args:
            char: The intended character.
            
        Returns:
            An adjacent key that could be a typo.
        """
        adjacent_keys = {
            'a': ['s', 'q', 'z'],
            'b': ['v', 'g', 'n'],
            'c': ['x', 'd', 'v'],
            'd': ['s', 'e', 'f', 'c'],
            'e': ['w', 'r', 'd'],
            'f': ['d', 'r', 'g', 'v'],
            'g': ['f', 't', 'h', 'b'],
            'h': ['g', 'y', 'j', 'n'],
            'i': ['u', 'o', 'k'],
            'j': ['h', 'u', 'k', 'm'],
            'k': ['j', 'i', 'l'],
            'l': ['k', 'o', 'p'],
            'm': ['n', 'j', 'k'],
            'n': ['b', 'h', 'm'],
            'o': ['i', 'p', 'l'],
            'p': ['o', 'l'],
            'q': ['w', 'a'],
            'r': ['e', 't', 'f'],
            's': ['a', 'w', 'd', 'x'],
            't': ['r', 'y', 'g'],
            'u': ['y', 'i', 'j'],
            'v': ['c', 'f', 'b'],
            'w': ['q', 'e', 's'],
            'x': ['z', 's', 'c'],
            'y': ['t', 'u', 'h'],
            'z': ['a', 'x'],
        }
        
        char_lower = char.lower()
        if char_lower in adjacent_keys:
            mistake = random.choice(adjacent_keys[char_lower])
            return mistake.upper() if char.isupper() else mistake
        return char
    
    def should_make_typo(self) -> bool:
        """Determine if we should simulate a typing mistake."""
        # 2% chance of making a typo
        return random.random() < 0.02
