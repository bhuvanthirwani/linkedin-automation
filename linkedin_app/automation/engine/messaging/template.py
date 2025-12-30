"""
Message template engine.
"""

import random
import re
from typing import List, Dict

from loguru import logger

from ..utils.models import Profile


class TemplateEngine:
    """
    Renders message templates with dynamic variables.
    """
    
    def __init__(self, templates: List[str] = None):
        self.templates = templates or [
            "Hi {first_name}, thanks for connecting! I'd love to learn more about your experience at {company}.",
            "Great to connect, {first_name}! Looking forward to staying in touch.",
            "Thanks for connecting, {first_name}! I'm excited to have you in my network.",
        ]
        self.current_template = ""
        self._template_index = 0
    
    def render(self, profile: Profile, template: str = None) -> str:
        """
        Render a message template with profile data.
        
        Args:
            profile: Profile to personalize for.
            template: Optional specific template to use.
            
        Returns:
            Rendered message string.
        """
        if template:
            self.current_template = template
        else:
            self.current_template = self._get_next_template()
        
        # Get variables from profile
        variables = profile.get_template_vars()
        
        # Render template
        message = self._substitute(self.current_template, variables)
        
        return message
    
    def _get_next_template(self) -> str:
        """Get the next template in rotation."""
        if not self.templates:
            return ""
        
        template = self.templates[self._template_index]
        self._template_index = (self._template_index + 1) % len(self.templates)
        return template
    
    def get_random_template(self) -> str:
        """Get a random template."""
        if not self.templates:
            return ""
        return random.choice(self.templates)
    
    def _substitute(self, template: str, variables: Dict[str, str]) -> str:
        """Substitute variables in the template."""
        result = template
        
        for key, value in variables.items():
            patterns = [
                f"{{{key}}}",
                f"{{{{{key}}}}}",
            ]
            
            for pattern in patterns:
                if pattern in result:
                    # Use fallback if value is empty
                    replacement = value or self._get_fallback(key)
                    result = result.replace(pattern, replacement)
        
        return result
    
    def _get_fallback(self, key: str) -> str:
        """Get fallback value for empty variables."""
        fallbacks = {
            "first_name": "there",
            "company": "your company",
            "title": "your work",
            "location": "your area",
            "name": "friend",
        }
        return fallbacks.get(key, "")
    
    def add_template(self, template: str) -> None:
        """Add a new template to the rotation."""
        if self.validate_template(template):
            self.templates.append(template)
            logger.info(f"Added new template: {template[:50]}...")
    
    def validate_template(self, template: str) -> bool:
        """Validate a template string."""
        if not template:
            return False
        
        if len(template) > 1000:  # LinkedIn message limit
            return False
        
        # Check for balanced braces
        open_count = template.count("{")
        close_count = template.count("}")
        if open_count != close_count:
            return False
        
        return True
    
    def get_available_variables(self) -> List[str]:
        """Get list of available template variables."""
        return [
            "first_name",
            "last_name",
            "name",
            "company",
            "title",
            "location",
            "headline",
        ]


def create_template_engine(templates: List[str] = None) -> TemplateEngine:
    """Create a template engine with the given templates."""
    return TemplateEngine(templates)
