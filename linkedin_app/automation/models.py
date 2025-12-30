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
        ordering = ['timestamp']

class LinkedInProfile(models.Model):
    """Stores scraped LinkedIn profile data (Matches linkedin_db_network_data)."""
    linkedin_url = models.URLField(unique=True)
    name = models.CharField(max_length=500, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    location = models.CharField(max_length=500, blank=True)
    
    # Activity and Status
    recent_activity_raw = models.TextField(blank=True, null=True)
    scrape_status = models.CharField(max_length=50, default='not_scraped')
    request_status = models.CharField(max_length=50, default='not_sent')
    
    scraped_at = models.DateTimeField(null=True, blank=True)
    request_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'linkedin_db_network_data'
        managed = False # Managed by the automation engine's raw SQL usually, but we can query it

    def __str__(self):
        return self.name or self.linkedin_url

class DailyStats(models.Model):
    """Daily metrics for automation actions."""
    date = models.DateField(unique=True, default=timezone.now)
    connections_sent = models.IntegerField(default=0)
    connections_accepted = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    profiles_searched = models.IntegerField(default=0)
    errors = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Daily Stats"

    def __str__(self):
        return str(self.date)

class ConnectionTracking(models.Model):
    """History of sent connection requests."""
    profile_url = models.URLField()
    profile_name = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, default='pending')
    note = models.TextField(blank=True)
    error = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['profile_url']),
            models.Index(fields=['sent_at']),
        ]

class MessageTracking(models.Model):
    """History of sent messages."""
    recipient_url = models.URLField()
    recipient_name = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    sent_at = models.DateTimeField(default=timezone.now)
    template_used = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['recipient_url']),
            models.Index(fields=['sent_at']),
        ]

class Settings(models.Model):
    """Store global configuration."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Settings"

    def __str__(self):
        return self.key
