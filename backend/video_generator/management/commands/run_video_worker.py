import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from video_generator.models import VideoJob
from video_generator.pipeline import run_video_job

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs a persistent background worker that polls and processes queued VideoJobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--poll-interval",
            type=float,
            default=2.0,
            help="Polling interval in seconds (default: 2.0)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single pass over queued jobs and exit.",
        )

    def handle(self, *args, **options):
        poll_interval = options["poll_interval"]
        once = options["once"]
        self.stdout.write(self.style.SUCCESS("Starting persistent Video Job Worker..."))

        while True:
            # Find next queued or interrupted processing job
            job = (
                VideoJob.objects.filter(status__in=[VideoJob.Status.QUEUED, VideoJob.Status.PROCESSING])
                .order_by("queued_at")
                .first()
            )
            if job:
                self.stdout.write(f"Processing VideoJob #{job.id} ({job.job_type}) for project '{job.project.title}'...")
                try:
                    run_video_job(job.id)
                    job.refresh_from_db()
                    self.stdout.write(self.style.SUCCESS(f"Finished VideoJob #{job.id} with status: {job.status}"))
                except Exception as exc:
                    self.stdout.write(self.style.ERROR(f"Error executing VideoJob #{job.id}: {exc}"))
            else:
                if once:
                    break
                time.sleep(poll_interval)
