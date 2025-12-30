from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Job, LogEntry, LinkedInProfile
from .services import AutomationService

def dashboard(request):
    """Render the main dashboard."""
    # Sync view is fine for dashboard read
    recent_jobs = Job.objects.order_by('-created_at')[:5]
    total_profiles = LinkedInProfile.objects.count()
    total_connections_sent = LinkedInProfile.objects.filter(connection_request_sent=True).count()
    
    context = {
        'jobs': recent_jobs,
        'stats': {
            'profiles': total_profiles,
            'connections_sent': total_connections_sent
        }
    }
    return render(request, 'automation/dashboard.html', context)

def start_task(request):
    """Start a new automation task in the background."""
    if request.method != 'POST':
         return redirect('dashboard')

    command = request.POST.get('command')
    # Filter out empty values and csrf token
    params = {k: v for k, v in request.POST.items() if v and k != 'csrfmiddlewaretoken'}
    
    # Create job entry
    from django.utils import timezone
    job = Job.objects.create(
        command=command,
        params=params,
        status='PENDING',
        created_at=timezone.now()
    )
    
    # Run in a background thread to avoid blocking the response
    import threading
    thread = threading.Thread(
        target=AutomationService.run_automation_task,
        args=(command, params, job.id),
        daemon=True
    )
    thread.start()
    
    if request.headers.get('HX-Request'):
        return HttpResponse(f'<div class="text-blue-500">Job {command} started (ID: {job.id})</div>')
    
    return redirect('dashboard')

def get_logs(request):
    """Get logs for the latest running job or a specific job."""
    # Log polling can remain sync, reading from DB is fast enough
    job_id = request.GET.get('job_id')
    
    if job_id:
        logs = LogEntry.objects.filter(job_id=job_id)
    else:
        latest_job = Job.objects.order_by('-created_at').first()
        if latest_job:
            logs = LogEntry.objects.filter(job_id=latest_job.id)
        else:
            logs = []
            
    context = {'logs': logs}
    return render(request, 'automation/partials/log_lines.html', context)

def profiles_view(request):
    """Render the profiles list page."""
    profiles = LinkedInProfile.objects.all().order_by('-scraped_at')
    return render(request, 'automation/profiles.html', {'profiles': profiles})

def stop_task(request, job_id):
    return HttpResponse("Stop not implemented yet")
