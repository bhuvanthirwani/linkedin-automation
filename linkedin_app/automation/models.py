from django.db import models
from django.utils import timezone

class Job(models.Model):
    """Represents a background automation job."""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('RUNNING', 'Running'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('STOPPED', 'Stopped'),
    ]
    
    command = models.CharField(max_length=255)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.command} ({self.status}) - {self.created_at}"

class LogEntry(models.Model):
    """Stores logs for specific jobs or general system logs."""
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    level = models.CharField(max_length=10, default='INFO')
    message = models.TextField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

class LinkedInProfile(models.Model):
    """Stores scraped LinkedIn profile data."""
    public_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    url = models.URLField(unique=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    full_name = models.CharField(max_length=500, blank=True)
    headline = models.CharField(max_length=1000, blank=True)
    location = models.CharField(max_length=255, blank=True)
    about = models.TextField(blank=True)
    
    # Tracking
    is_connected = models.BooleanField(default=False)
    connection_request_sent = models.BooleanField(default=False)
    connection_sent_at = models.DateTimeField(null=True, blank=True)
    
    scraped_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.url

class Settings(models.Model):
    """Store global configuration."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Settings"

    def __str__(self):
        return self.key
