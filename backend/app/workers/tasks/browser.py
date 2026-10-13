from app.workers.celery_app import celery_app
from app.workers.pipeline import run_scrape


@celery_app.task(bind=True, name="app.workers.tasks.browser.scrape_url_browser")
def scrape_url_browser(self, job_id: str) -> dict:
    return run_scrape(job_id, self.request.id, use_browser=True)
