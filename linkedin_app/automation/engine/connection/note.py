"""
Personalized note composition for connection requests.
"""

import re
from typing import Dict

from loguru import logger

from ..utils.models import Profile


class NoteComposer:
    """
    Composes personalized notes for connection requests.
    """
    
    MAX_NOTE_LENGTH = 300
    
    def __init__(self, template: str = None):
        self.template = template or (
            "Hi {first_name}, I'd love to connect and learn more about your work at {company}!"
        )
    
    def compose(self, profile: Profile, custom_template: str = None) -> str:
        """
        Compose a personalized note for a profile.
        
        Args:
            profile: The profile to personalize for.
            custom_template: Optional custom template to use instead of default.
            
        Returns:
            Personalized note string (max 300 chars).
        """
        template = custom_template or self.template
        
        # Get template variables from profile
        variables = profile.get_template_vars()
        
        # Replace variables in template
        note = self._substitute_variables(template, variables)
        
        # Clean up the note
        note = self._clean_note(note)
        
        # Truncate if necessary
        if len(note) > self.MAX_NOTE_LENGTH:
            note = self._smart_truncate(note, self.MAX_NOTE_LENGTH)
        
        return note
    
    def _substitute_variables(self, template: str, variables: Dict[str, str]) -> str:
        """Substitute variables in the template."""
        result = template
        
        for key, value in variables.items():
            # Support both {var} and {{var}} syntax
            patterns = [
                f"{{{key}}}",
                f"{{{{{key}}}}}",
            ]
            
            for pattern in patterns:
                if pattern in result:
                    # Use a fallback if value is empty
                    replacement = value or self._get_fallback(key)
                    result = result.replace(pattern, replacement)
        
        return result
    
    def _get_fallback(self, key: str) -> str:
        """Get fallback value for an empty variable."""
        fallbacks = {
            "first_name": "there",
            "company": "your company",
            "title": "your work",
            "location": "your area",
        }
        return fallbacks.get(key, "")
    
    def _clean_note(self, note: str) -> str:
        """Clean up the note text."""
        # Remove extra whitespace
        note = re.sub(r'\s+', ' ', note)
        
        # Remove double punctuation
        note = re.sub(r'([.!?])\1+', r'\1', note)
        
        # Strip leading/trailing whitespace
        note = note.strip()
        
        return note
    
    def _smart_truncate(self, text: str, max_length: int) -> str:
        """Truncate text at a sentence or word boundary."""
        if len(text) <= max_length:
            return text
        
        # Try to truncate at sentence boundary
        truncated = text[:max_length]
        
        # Look for last sentence ending
        last_period = truncated.rfind('.')
        last_exclaim = truncated.rfind('!')
        last_question = truncated.rfind('?')
        
        last_sentence = max(last_period, last_exclaim, last_question)
        
        if last_sentence > max_length // 2:
            return truncated[:last_sentence + 1]
        
        # Fall back to word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length // 2:
            return truncated[:last_space] + "..."
        
        # Last resort: hard truncate
        return truncated[:max_length - 3] + "..."
    
    def validate_template(self, template: str) -> tuple:
        """
        Validate a template string.
        
        Returns:
            Tuple of (is_valid: bool, error_message: str)
        """
        if not template:
            return False, "Template cannot be empty"
        
        if len(template) > self.MAX_NOTE_LENGTH:
            return False, f"Template exceeds {self.MAX_NOTE_LENGTH} characters"
        
        # Check for valid variable syntax
        pattern = r'\{(\w+)\}'
        variables = re.findall(pattern, template)
        
        valid_vars = {"first_name", "last_name", "name", "company", "title", "location", "headline"}
        invalid_vars = set(variables) - valid_vars
        
        if invalid_vars:
            return False, f"Unknown variables: {invalid_vars}"
        
        return True, ""


def personalize_note(template: str, profile: Profile) -> str:
    """
    Convenience function to personalize a note.
    
    Args:
        template: The note template with {variables}.
        profile: The profile to personalize for.
        
    Returns:
        Personalized note string.
    """
    composer = NoteComposer(template)
    return composer.compose(profile)
