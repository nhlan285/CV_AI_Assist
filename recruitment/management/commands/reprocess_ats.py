from django.core.management.base import BaseCommand

from recruitment.models import Application, CVDocument
from recruitment.services.ats import calculate_application_ats, ensure_cv_text


class Command(BaseCommand):
    help = "Parse lai CV va tinh lai ATS breakdown/summary cho application hien co."

    def add_arguments(self, parser):
        parser.add_argument(
            "--applications-only",
            action="store_true",
            help="Chi tinh lai application, bo qua CV khong duoc dung trong application.",
        )

    def handle(self, *args, **options):
        if not options["applications_only"]:
            for cv_document in CVDocument.objects.filter(is_deleted=False):
                try:
                    ensure_cv_text(cv_document)
                except Exception as exc:
                    self.stdout.write(self.style.WARNING(f"CV #{cv_document.pk}: {exc}"))

        updated = 0
        applications = Application.objects.select_related("cv", "job", "job__company")
        for application in applications:
            try:
                cv_text = ensure_cv_text(application.cv)
                if not cv_text:
                    continue
                result = calculate_application_ats(cv_text, application.job)
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Application #{application.pk}: {exc}"))
                continue

            application.ats_score = result["score"]
            application.ats_semantic_score = result["semantic_score"]
            application.ats_skill_score = result["skill_score"]
            application.ats_breakdown = result["breakdown"]
            application.matched_skills = result["matched_skills"]
            application.missing_skills = result["missing_skills"]
            application.ai_summary = result["summary"]
            application.ats_notes = result["notes"]
            application.save(
                update_fields=[
                    "ats_score",
                    "ats_semantic_score",
                    "ats_skill_score",
                    "ats_breakdown",
                    "matched_skills",
                    "missing_skills",
                    "ai_summary",
                    "ats_notes",
                    "updated_at",
                ]
            )
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"Da reprocess {updated} application."))
