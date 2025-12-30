import sys
import threading
import traceback
from pathlib import Path
from loguru import logger
from django.conf import settings
from .models import Job, LogEntry

class AutomationService:
    @staticmethod
    def run_automation_task(command: str, params: dict, job_id: int):
        """Synchronous task wrapper for the automation bot."""
        try:
            job = Job.objects.get(id=job_id)
            job.status = 'RUNNING'
            from django.utils import timezone
            job.started_at = timezone.now()
            job.save()

            def filtered_sink(message):
                try:
                    record = message.record
                    # Format log message with optional exception info
                    log_message = record["message"]
                    if record.get("exception"):
                        type_, value, tb = record["exception"]
                        log_message += "\n" + "".join(traceback.format_exception(type_, value, tb))

                    LogEntry.objects.create(
                        job_id=job_id,
                        level=record["level"].name,
                        message=log_message,
                        timestamp=record["time"]
                    )
                except Exception as e:
                    print(f"SINK ERROR: {e}", file=sys.stderr)

            handler_id = logger.add(filtered_sink, level="DEBUG", format="{message}", enqueue=True)
            logger.info(f"Task started: {command}")

            from .engine.main import LinkedInBot
            from .engine.utils.config import load_config
            
            config_path = settings.BASE_DIR / "configs" / "config.yaml"
            if not config_path.exists():
                raise FileNotFoundError(f"Config file not found at {config_path}")

            config = load_config(str(config_path))
            
            if params.get('max_connections'):
                 config.rate_limits.daily_connection_limit = int(params['max_connections'])
            
            bot = LinkedInBot(config)
            
            try:
                bot.start()
                is_logged_in = bot.login()
                if not is_logged_in:
                    raise Exception("Failed to login to LinkedIn")

                if command == "Scrapping":
                    bot.run_scrapping(
                        keywords=params.get('keywords', ''),
                        location=params.get('location', ''),
                        start_page=int(params.get('start_page', 1)),
                        pages=int(params.get('pages', 1)),
                        limit=int(params.get('max_connections', 10))
                    )
                elif command == "Filtering":
                    bot.run_filtering(int(params.get('max_connections', 10)))
                elif command == "Send_Requests":
                    bot.run_sending(int(params.get('max_connections', 10)))
                elif command == "SalesNavigator_Connect":
                    bot.run_sales_nav_connection(
                        url=params.get('sales_nav_url', ''),
                        end_page=int(params.get('end_page', 1)),
                        limit=int(params.get('max_connections', 10)),
                        message=params.get('message', '')
                    )
                elif command == "dry_run":
                    import time
                    logger.info("Executing Dry Run - Configuration Valid")
                    time.sleep(2)
                
                job.status = 'COMPLETED'
            except Exception:
                logger.exception("Job logic failed")
                job.status = 'FAILED'
            finally:
                if bot:
                    bot.stop()
                logger.remove(handler_id)
        except Exception as e:
            error_msg = f"Critical job error: {e}\n{traceback.format_exc()}"
            print(error_msg, file=sys.stderr)
            try:
                job = Job.objects.get(id=job_id)
                job.status = 'FAILED'
                job.save()
                # Log the critical error to LogEntry as well
                LogEntry.objects.create(
                    job_id=job_id,
                    level="CRITICAL",
                    message=error_msg,
                )
            except:
                pass
        finally:
            try:
                job = Job.objects.get(id=job_id)
                from django.utils import timezone
                job.finished_at = timezone.now()
                job.save()
            except:
                pass

    # Remove start_job since we now call run_automation_task directly from the view
